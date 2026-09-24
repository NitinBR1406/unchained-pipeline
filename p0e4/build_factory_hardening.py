#!/usr/bin/env python3
"""Build deterministic evidence for the synthetic P0-E4 hardening slice."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from hardening.execution_context import build_context, governed_task_prompt
from hardening.post_ready import assemble, authorize_bounded_repair, seal
from hardening.raw_drop import SyntheticDirectoryWatcher
from hardening.shadow_distribution import project, verify_readback


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "p0e4/evidence/factory_hardening_v01"


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    return sha_bytes(path.read_bytes())


def write(name, value):
    path = OUT / name
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def asset(role, name, source, duration=15000):
    return {"role": role, "uri": f"synthetic-disposable/{name}.mp4", "sha256": sha_bytes(name.encode()), "bytes": 100,
            "technical": {"width": 1080, "height": 1920, "fps": 30, "duration_ms": duration,
                          "audio_tracks": 1, "decode": "COMPLETE"},
            "provenance": {"source_sha256": source, "operation": "SYNTHETIC_FIXTURE"}}


def still(name, source):
    return {"role": "still", "uri": f"synthetic-disposable/{name}.png", "sha256": sha_bytes(name.encode()), "bytes": 50,
            "technical": {"width": 1080, "height": 1920, "decode": "COMPLETE"},
            "provenance": {"source_sha256": source, "operation": "SYNTHETIC_FRAME_EXTRACT"}}


def safe(value):
    return {"asset_sha256": value, "performer_box": {"x": .2, "y": .1, "w": .6, "h": .5},
            "overlays": [{"kind": "title", "rect": {"x": .1, "y": .75, "w": .35, "h": .1}, "non_lyric": True}],
            "platform_ui_exclusions": [{"x": .85, "y": .2, "w": .1, "h": .6}]}


def main(tested_sha):
    OUT.mkdir(parents=True, exist_ok=True)
    pointer_path = ROOT / "p0e4/MASTER_STATE_LATEST.json"
    pointer = json.loads(pointer_path.read_text())
    master_path = ROOT / pointer["path"]
    master = json.loads(master_path.read_text())
    assert pointer["master_state_version"] == "V16.3" and pointer["state_version"] >= 29
    assert master["authorizations"]["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is False
    assert master["authorizations"]["PUBLICATION_AUTHORIZED"] is False

    authorization = {
        "schema": "P0E4_SYNTHETIC_HARDENING_AUTHORIZATION_V01", "scope": "SYNTHETIC_DISPOSABLE_AND_SHADOW_ONLY",
        "real_raw_drop_authorized": False, "production_deployment_authorized": False,
        "publication_authorized": False, "first_real_poster": "PAUSED_BY_NITIN",
        "forbidden": ["REAL_AAKHRI_RAW_DROP", "LIVE_MAKE_MUTATION", "SOCIAL_UPLOAD", "SCHEDULE", "PUBLISH", "PURCHASE"],
    }
    write("AUTHORIZATION.json", authorization)
    write("RECONCILIATION.json", {
        "schema": "P0E4_SYNTHETIC_HARDENING_RECONCILIATION_V01", "remote_parent_sha": tested_sha,
        "master_state_version": pointer["master_state_version"], "state_version": pointer["state_version"],
        "aakhri_post_ready_sha256": sha_file(ROOT / "p0e4/evidence/aakhri_factory_realization_v01/POST_READY_MANIFEST.json"),
        "real_aakhri_workload_triggered": False, "status": "RECONCILED",
    })

    fixture = b"P0E4-SYNTHETIC-DISPOSABLE-RAW-V01"
    observed = {"schema": "SYNTHETIC_RAW_DROP_OBSERVATION_V01", "scope": "SYNTHETIC_DISPOSABLE_ONLY",
                "drop_key": "drop-001.mov", "basename": "drop-001.mov", "bytes": len(fixture),
                "sha256": sha_bytes(fixture), "stable_reads": 2, "source_mutations": 0}
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory); drop = temporary / "synthetic-drop"; state = temporary / "state"; drop.mkdir()
        (drop / ".synthetic_disposable_scope").write_text("SYNTHETIC_ONLY\n")
        (drop / "drop-001.mov").write_bytes(fixture)
        watcher = SyntheticDirectoryWatcher(drop, state)
        first_poll = watcher.poll()
        accepted = SyntheticDirectoryWatcher(drop, state).poll()[0]
        replayed = SyntheticDirectoryWatcher(drop, state).intake.replay()
        watcher = SyntheticDirectoryWatcher(drop, state)
        duplicate = watcher.poll()[0]
        intake = watcher.intake
        alias_observation = dict(observed, drop_key="drop-001-copy.mov", basename="drop-001-copy.mov")
        alias = intake.observe(alias_observation, fixture)
        changed = b"P0E4-SYNTHETIC-CHANGED"
        drift_observation = dict(observed, bytes=len(changed), sha256=sha_bytes(changed))
        held = intake.observe(drift_observation, changed)
        final_state = intake.replay()
        ledger = intake.ledger_path.read_bytes()
    write("SYNTHETIC_RAW_DROP_LEDGER.jsonl", ledger)
    write("RAW_DROP_SIMULATION.json", {
        "schema": "SYNTHETIC_RAW_DROP_SIMULATION_V01", "observation": observed, "accepted": accepted,
        "first_poll": first_poll,
        "duplicate": duplicate, "alias_duplicate": alias, "source_drift": held,
        "recovered_after_restart": replayed["accepted_by_hash"] == final_state["accepted_by_hash"],
        "accepted_content_count": len(final_state["accepted_by_hash"]), "event_count": final_state["event_count"],
        "ledger_head_hash": final_state["ledger_head_hash"], "real_raw_drop_triggered": False,
    })

    raw_sha, audio_sha = sha_bytes(fixture), sha_bytes(b"synthetic-audio")
    outputs = [asset("master", "synthetic-master", raw_sha, 214400)] + [asset("derivative", f"synthetic-d{x}", raw_sha) for x in range(1, 5)]
    stills = [still(f"synthetic-s{x}", raw_sha) for x in range(1, 4)]
    platform_map = {"youtube_hero": outputs[0]["sha256"], "youtube_shorts": outputs[1]["sha256"],
                    "instagram_reels": outputs[2]["sha256"], "facebook_reels": outputs[3]["sha256"],
                    "tiktok": outputs[4]["sha256"]}
    package = seal(assemble("SYNTHETIC_DISPOSABLE_001", {"raw_sha256": raw_sha, "audio_sha256": audio_sha},
                            outputs, stills, {"verdict": "PASS", "checked_assets": [x["sha256"] for x in outputs]},
                            [safe(x["sha256"]) for x in outputs], platform_map))
    write("POST_READY_PACKAGE.json", package)
    repair_request = {"schema": "BOUNDED_REPAIR_REQUEST_V01", "attempt": 1, "trigger_qc_sha256": "3" * 64,
                      "defect_ids": ["synthetic_overlay_face_overlap"], "operations": ["OVERLAY_REPOSITION"],
                      "input_hashes": [x["sha256"] for x in outputs], "production_deployment_authorized": False,
                      "publication_authorized": False, "first_real_poster": "PAUSED_BY_NITIN"}
    write("BOUNDED_REPAIR_GOVERNANCE.json", {"request": repair_request,
          "authorization": authorize_bounded_repair(repair_request, outputs), "repair_executed": False})

    architecture_refs = {
        "field_map": {"uri": "p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V151.json",
                      "sha256": sha_file(ROOT / "p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V151.json")},
        "live_headers": {"uri": "p0e4/evidence/canonical_v151/LIVE_HEADERS.json",
                         "sha256": sha_file(ROOT / "p0e4/evidence/canonical_v151/LIVE_HEADERS.json")},
        "make_boundary": {"uri": "p0e4/evidence/target_v13/CLAUDE_DISPATCH_RESULT_SANITIZED.json",
                          "sha256": sha_file(ROOT / "p0e4/evidence/target_v13/CLAUDE_DISPATCH_RESULT_SANITIZED.json")},
    }
    shadow = project(package, architecture_refs)
    assert verify_readback(shadow, package, architecture_refs) == package
    write("MAKE_DISTRIBUTION_SHADOW.json", shadow)
    master_ref = {"uri": "p0e4/MASTER_STATE_LATEST.json", "sha256": sha_file(pointer_path)}
    task_ref = {"uri": "p0e4/evidence/aakhri_factory_realization_v01/POST_READY_MANIFEST.json",
                "sha256": sha_file(ROOT / "p0e4/evidence/aakhri_factory_realization_v01/POST_READY_MANIFEST.json")}
    context = build_context(tested_sha, master_ref, [task_ref])
    write("EXECUTION_CONTEXT.json", context)
    governed = governed_task_prompt("CODEX", "Validate synthetic RAW intake and inert POST_READY projection without external actions", [master_ref, task_ref])
    write("PROMPT_EFFICIENCY.json", governed)
    write("ADVERSARIAL_VALIDATION.json", {
        "schema": "P0E4_HARDENING_ADVERSARIAL_VALIDATION_V01",
        "covered": ["real_scope_rejected", "unstable_file_rejected", "hash_mismatch_rejected", "ledger_tamper_rejected",
                    "duplicate_suppressed", "path_drift_held", "partial_qc_rejected", "unsafe_overlay_rejected",
                    "lyric_claim_rejected", "technical_decode_failure_rejected", "repair_scope_expansion_rejected",
                    "repair_budget_exhaustion_rejected", "shadow_tamper_rejected", "live_dispatch_rejected",
                    "authority_drift_rejected", "prompt_semantic_drift_rejected"],
        "real_external_actions": 0, "status": "COVERED_BY_REGRESSION",
    })
    write("STATE_REDUCER_OUTCOME.json", {
        "schema": "P0E4_HARDENING_STATE_OUTCOME_V01", "parent_state_version": pointer["state_version"],
        "workstream_state": "SYNTHETIC_HARDENING_GREEN_REAL_RAW_PARKED", "global_master_state_mutated": False,
        "reason": "Synthetic/shadow engineering evidence cannot change global deployment, publication, rights or approvals.",
    })
    write("NEXT_READY.json", {
        "schema": "P0E4_HARDENING_NEXT_READY_V01", "status": "WAITING_FOR_NITIN_AT_PC",
        "completed_independent_work": ["SYNTHETIC_RAW_DROP", "POST_READY_HARDENING", "MAKE_SHADOW_ADAPTER", "PROMPT_CONTEXT_GOVERNANCE"],
        "independent_ready_work_remaining": [], "parked": [{"task": "REAL_RAW_DROP_ACCEPTANCE", "reason": "Explicitly parked until Nitin is at his PC"}],
        "production_deployment_authorized": False, "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tested-sha", required=True)
    args = parser.parse_args()
    main(args.tested_sha)
