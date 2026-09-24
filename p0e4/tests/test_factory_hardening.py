import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hardening.execution_context import build_context, governed_task_prompt
from hardening.post_ready import assemble, authorize_bounded_repair, digest, seal
from hardening.raw_drop import SyntheticDirectoryWatcher, SyntheticRawDropIntake
from hardening.shadow_distribution import dispatch, project, verify_readback


def h(value):
    return hashlib.sha256(value).hexdigest()


def video(role, name, source="1" * 64, duration=15000):
    return {"role": role, "uri": f"synthetic/{name}.mp4", "sha256": h(name.encode()), "bytes": 100,
            "technical": {"width": 1080, "height": 1920, "fps": 30, "duration_ms": duration,
                          "audio_tracks": 1, "decode": "COMPLETE"},
            "provenance": {"source_sha256": source, "operation": "SYNTHETIC_FIXTURE"}}


def still(name, source="1" * 64):
    return {"role": "still", "uri": f"synthetic/{name}.png", "sha256": h(name.encode()), "bytes": 50,
            "technical": {"width": 1080, "height": 1920, "decode": "COMPLETE"},
            "provenance": {"source_sha256": source, "operation": "SYNTHETIC_FRAME_EXTRACT"}}


def safe(asset_sha):
    return {"asset_sha256": asset_sha, "performer_box": {"x": .2, "y": .1, "w": .6, "h": .5},
            "overlays": [{"kind": "title", "rect": {"x": .1, "y": .75, "w": .35, "h": .1}, "non_lyric": True}],
            "platform_ui_exclusions": [{"x": .85, "y": .2, "w": .1, "h": .6}]}


class RawDropHardening(unittest.TestCase):
    def observation(self, content=b"synthetic-video", key="drop/a.mov"):
        return {"schema": "SYNTHETIC_RAW_DROP_OBSERVATION_V01", "scope": "SYNTHETIC_DISPOSABLE_ONLY",
                "drop_key": key, "basename": Path(key).name, "bytes": len(content), "sha256": h(content),
                "stable_reads": 2, "source_mutations": 0}

    def test_accept_replay_and_duplicate_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            intake = SyntheticRawDropIntake(directory)
            first = intake.observe(self.observation(), b"synthetic-video")
            again = SyntheticRawDropIntake(directory).observe(self.observation(), b"synthetic-video")
            self.assertEqual(first["intake_id"], again["existing_intake_id"])
            self.assertEqual(again["status"], "DUPLICATE_SUPPRESSED")
            before = intake.replay()["event_count"]
            intake.observe(self.observation(), b"synthetic-video")
            self.assertEqual(intake.replay()["event_count"], before)

    def test_same_bytes_new_path_is_one_intake_with_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            intake = SyntheticRawDropIntake(directory)
            first = intake.observe(self.observation(), b"synthetic-video")
            duplicate = intake.observe(self.observation(key="other/copy.mov"), b"synthetic-video")
            self.assertEqual(duplicate["existing_intake_id"], first["intake_id"])
            self.assertEqual(len(intake.replay()["accepted_by_hash"]), 1)
            changed = b"changed-alias"
            held = intake.observe(self.observation(changed, key="other/copy.mov"), changed)
            self.assertEqual(held["status"], "HOLD_SOURCE_DRIFT")

    def test_same_path_changed_bytes_holds(self):
        with tempfile.TemporaryDirectory() as directory:
            intake = SyntheticRawDropIntake(directory)
            intake.observe(self.observation(), b"synthetic-video")
            changed = b"changed-video"
            held = intake.observe(self.observation(changed), changed)
            self.assertEqual(held["status"], "HOLD_SOURCE_DRIFT")

    def test_real_scope_unstable_mutation_or_wrong_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            intake = SyntheticRawDropIntake(directory)
            for key, value in (("scope", "REAL"), ("stable_reads", 1), ("source_mutations", 1), ("sha256", "0" * 64)):
                observation = self.observation(); observation[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    intake.observe(observation, b"synthetic-video")

    def test_ledger_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            intake = SyntheticRawDropIntake(directory)
            intake.observe(self.observation(), b"synthetic-video")
            event = json.loads(intake.ledger_path.read_text()); event["payload"]["bytes"] += 1
            intake.ledger_path.write_text(json.dumps(event) + "\n")
            with self.assertRaises(ValueError): intake.replay()

    def test_directory_watcher_waits_for_two_stable_polls_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); drop = root / "drop"; state = root / "state"; drop.mkdir()
            (drop / ".synthetic_disposable_scope").write_text("SYNTHETIC_ONLY\n")
            (drop / "fixture.mov").write_bytes(b"fixture")
            watcher = SyntheticDirectoryWatcher(drop, state)
            self.assertEqual(watcher.poll()[0]["status"], "PENDING_STABILITY")
            accepted = SyntheticDirectoryWatcher(drop, state).poll()[0]
            self.assertEqual(accepted["status"], "SYNTHETIC_RAW_ACCEPTED")
            duplicate = SyntheticDirectoryWatcher(drop, state).poll()[0]
            self.assertEqual(duplicate["status"], "DUPLICATE_SUPPRESSED")

    def test_directory_watcher_requires_disposable_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); drop = root / "drop"; drop.mkdir()
            with self.assertRaises(ValueError): SyntheticDirectoryWatcher(drop, root / "state")


class PostReadyHardening(unittest.TestCase):
    def package(self):
        outputs = [video("master", "master", duration=214400)] + [video("derivative", f"d{x}") for x in range(1, 5)]
        stills = [still(f"s{x}") for x in range(1, 4)]
        platforms = {"youtube_hero": outputs[0]["sha256"], "youtube_shorts": outputs[1]["sha256"],
                     "instagram_reels": outputs[2]["sha256"], "facebook_reels": outputs[3]["sha256"],
                     "tiktok": outputs[4]["sha256"]}
        qc = {"verdict": "PASS", "checked_assets": [x["sha256"] for x in outputs]}
        return assemble("SYNTHETIC_001", {"raw_sha256": "1" * 64, "audio_sha256": "2" * 64},
                        outputs, stills, qc, [safe(x["sha256"]) for x in outputs], platforms)

    def test_complete_package_seals_deterministically(self):
        one = seal(self.package()); two = seal(self.package())
        self.assertEqual(one, two)
        self.assertEqual(one["status"], "POST_READY_WAITING_FOR_NITIN")
        self.assertEqual(one["rights_status"], "UNKNOWN_RIGHTS_HOLD")
        self.assertFalse(one["publication_authorized"])

    def test_partial_qc_or_platform_coverage_fails(self):
        package = self.package(); outputs = package["outputs"]; stills = package["stills"]
        bad_qc = {"verdict": "PASS", "checked_assets": [outputs[0]["sha256"]]}
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], outputs, stills, bad_qc, package["safe_areas"], package["platform_map"])
        mapping = dict(package["platform_map"]); mapping.pop("tiktok")
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], outputs, stills, package["qc"], package["safe_areas"], mapping)

    def test_overlay_on_performer_and_lyric_claim_fail(self):
        package = self.package(); area = copy.deepcopy(package["safe_areas"])
        area[0]["overlays"][0]["rect"] = {"x": .3, "y": .2, "w": .2, "h": .1}
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], package["outputs"], package["stills"], package["qc"], area, package["platform_map"])
        area = copy.deepcopy(package["safe_areas"])
        area[0]["overlays"][0]["rect"] = {"x": .86, "y": .3, "w": .05, "h": .1}
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], package["outputs"], package["stills"], package["qc"], area, package["platform_map"])
        area = copy.deepcopy(package["safe_areas"]); area[0]["overlays"][0]["non_lyric"] = False
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], package["outputs"], package["stills"], package["qc"], area, package["platform_map"])

    def test_bad_technical_output_fails(self):
        package = self.package(); outputs = copy.deepcopy(package["outputs"]); outputs[0]["technical"]["decode"] = "PARTIAL"
        with self.assertRaises(ValueError):
            assemble("S", package["inputs"], outputs, package["stills"], package["qc"], package["safe_areas"], package["platform_map"])

    def test_bounded_repair_locks_source_and_scope(self):
        outputs = self.package()["outputs"]
        request = {"schema": "BOUNDED_REPAIR_REQUEST_V01", "attempt": 1, "trigger_qc_sha256": "3" * 64,
                   "defect_ids": ["face_overlap"], "operations": ["OVERLAY_REPOSITION"],
                   "input_hashes": [x["sha256"] for x in outputs], "production_deployment_authorized": False,
                   "publication_authorized": False, "first_real_poster": "PAUSED_BY_NITIN"}
        self.assertEqual(authorize_bounded_repair(request, outputs)["status"], "AUTHORIZED_PRIVATE_REPAIR_ONLY")
        for key, value in (("attempt", 3), ("operations", ["MELODY_REWRITE"]), ("publication_authorized", True)):
            bad = copy.deepcopy(request); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): authorize_bounded_repair(bad, outputs)


class ShadowAndContextHardening(unittest.TestCase):
    def package(self):
        return PostReadyHardening().package()

    def refs(self):
        return {name: {"uri": f"evidence/{name}.json", "sha256": value * 64}
                for name, value in (("field_map", "a"), ("live_headers", "b"), ("make_boundary", "c"))}

    def test_shadow_projection_is_inert_and_replayable(self):
        package = seal(self.package()); shadow = project(package, self.refs())
        self.assertEqual(verify_readback(shadow, package, self.refs()), package)
        self.assertTrue(all(x["publish_to_platform"] == "FALSE" for x in shadow["rows"]))
        self.assertEqual(shadow["external_writes"], 0)

    def test_shadow_tamper_or_dispatch_fails(self):
        package = seal(self.package()); shadow = project(package, self.refs()); shadow["rows"][0]["publish_to_platform"] = "TRUE"
        with self.assertRaises(ValueError): verify_readback(shadow, package, self.refs())
        with self.assertRaises(ValueError): dispatch(package)

    def test_unsealed_or_authority_drift_fails(self):
        with self.assertRaises(ValueError): project(self.package(), self.refs())
        package = seal(self.package()); package["publication_authorized"] = True
        with self.assertRaises(ValueError): project(package, self.refs())

    def test_context_and_prompt_use_hash_references(self):
        master = {"uri": "p0e4/MASTER_STATE_LATEST.json", "sha256": "a" * 64}
        task = {"uri": "p0e4/evidence/aakhri_factory_realization_v01/POST_READY_MANIFEST.json", "sha256": "b" * 64}
        context = build_context("c" * 40, master, [task])
        governed = governed_task_prompt("CODEX", "Harden synthetic intake without external actions", [master, task])
        self.assertIn("REAL_RAW_DROP", context["forbidden_operations"])
        self.assertEqual(governed["acceptance"]["semantic_equivalence"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
