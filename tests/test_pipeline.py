"""Test suite for the Unchained Nitin Autonomous Media Pipeline V1 (stdlib unittest)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unpipe import mediaqc, production
from unpipe.orchestrator import Campaign
from unpipe.states import State, can_transition
from unpipe.approvals import GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE


def make_manifest(tmp, rights="RIGHTS_HOLD", dur=208.625):
    m = {
        "campaign_id": "test-song", "artist": "UNCHAINED NITIN", "song_title": "Test",
        "release_type": "cover", "source_master": "src.mp4", "duration": dur,
        "aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24,
        "presentation_preset": "MOTION_A_PREMIUM_RESTRAINED",
        "brand_profile": "UNCHAINED_NITIN_BRAND_PROFILE_V1",
        "platform_targets": ["youtube_hero", "tiktok"],
        "rights": {"status": rights},
    }
    p = Path(tmp) / "campaign.json"
    p.write_text(json.dumps(m))
    return p


def make_frozen(tmp, with_range=False):
    edit = {"timeline": {"tracks": [{"clips": []}]},
            "output": {"format": "mp4", "size": {"width": 1080, "height": 1920}, "fps": 24}}
    if with_range:
        edit["output"]["range"] = {"start": 4, "length": 6}
    p = Path(tmp) / "frozen.json"
    p.write_text(json.dumps(edit))
    return p


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wd = Path(self.tmp) / "wd"

    def camp(self, **kw):
        mani = make_manifest(self.tmp, **kw)
        return Campaign(self.wd, mani, runner_path="/nonexistent/runner.sh")

    # 1
    def test_valid_transition(self):
        c = self.camp()
        c.transition(State.EDIT_BUILDING, "build")
        self.assertEqual(c.state, State.EDIT_BUILDING)

    # 2
    def test_invalid_transition(self):
        c = self.camp()
        with self.assertRaises(ValueError):
            c.transition(State.PUBLISHED, "illegal")

    # 3 + 5
    def test_production_blocked_without_creative_approval(self):
        c = self.camp()
        frozen = make_frozen(self.tmp)
        with self.assertRaises(PermissionError):
            c.run_production_master(frozen, "out.mp4", execute=False)

    # 4
    def test_changed_hash_invalidates_approval(self):
        c = self.camp()
        frozen = make_frozen(self.tmp)
        sha = production.assert_master_payload(frozen)
        c.approve(GATE_CREATIVE, "frozen", sha)
        self.assertTrue(c.gate_ok(GATE_CREATIVE, sha))
        # change artifact
        Path(frozen).write_text(json.dumps({"timeline": {"tracks": [{"clips": [{"x": 1}]}]},
                                            "output": {"format": "mp4"}}))
        new_sha = production.assert_master_payload(frozen)
        self.assertNotEqual(sha, new_sha)
        self.assertFalse(c.gate_ok(GATE_CREATIVE, new_sha))

    # 6
    def test_publish_blocked_without_publish_approval(self):
        c = self.camp(rights="RIGHTS_PASS")
        with self.assertRaises(PermissionError):
            c.publish("somesha")

    # 7
    def test_publish_blocked_on_rights_hold(self):
        c = self.camp(rights="RIGHTS_HOLD")
        c.approve(GATE_PUBLISH, "master", "sha1")
        with self.assertRaises(PermissionError):
            c.publish("sha1")

    # 8
    def test_master_mode_rejects_proof_range(self):
        frozen = make_frozen(self.tmp, with_range=True)
        with self.assertRaises(production.ProductionError):
            production.assert_master_payload(frozen)

    # 9
    def test_missing_secret_safe_failure(self):
        c = self.camp()
        frozen = make_frozen(self.tmp)
        sha = production.assert_master_payload(frozen)
        c.approve(GATE_CREATIVE, "frozen", sha)
        c._status["current_state"] = State.FROZEN_JSON_READY.value
        os.environ.pop("SHOTSTACK_PRODUCTION_API_KEY", None)
        res = c.run_production_master(frozen, "out.mp4", execute=True)
        self.assertFalse(res.get("executed"))
        self.assertEqual(c.state, State.HOLD)  # safe HOLD, no crash, no publish

    # 10
    def test_qc_duration_failure_holds(self):
        c = self.camp(dur=208.625)
        c.transition(State.EDIT_BUILDING, "b")
        # jump to a state from which tech qc is reachable
        c._status["current_state"] = State.PRODUCTION_RENDER_READY.value
        fake = {"streams": [{"codec_type": "video", "width": 1080, "height": 1920,
                             "r_frame_rate": "24/1", "codec_name": "h264"},
                            {"codec_type": "audio", "codec_name": "aac", "duration": "100.0"}],
                "format": {"duration": "100.0", "format_name": "mp4"}}  # wrong duration
        orig_av, orig_pr = mediaqc.ffprobe_available, mediaqc.probe
        mediaqc.ffprobe_available = lambda: True
        mediaqc.probe = lambda p: fake
        try:
            rep = c.run_tech_qc("x.mp4")
        finally:
            mediaqc.ffprobe_available, mediaqc.probe = orig_av, orig_pr
        self.assertFalse(rep["qc_pass"])
        self.assertEqual(c.state, State.HOLD)

    # 11
    def test_qc_missing_audio_holds(self):
        c = self.camp()
        c._status["current_state"] = State.PRODUCTION_RENDER_READY.value
        fake = {"streams": [{"codec_type": "video", "width": 1080, "height": 1920,
                             "r_frame_rate": "24/1", "codec_name": "h264"}],
                "format": {"duration": "208.625", "format_name": "mp4"}}  # no audio
        orig_av, orig_pr = mediaqc.ffprobe_available, mediaqc.probe
        mediaqc.ffprobe_available = lambda: True
        mediaqc.probe = lambda p: fake
        try:
            rep = c.run_tech_qc("x.mp4")
        finally:
            mediaqc.ffprobe_available, mediaqc.probe = orig_av, orig_pr
        self.assertFalse(rep["qc_pass"])
        self.assertEqual(c.state, State.HOLD)

    # 12
    def test_retry_does_not_duplicate_publish(self):
        c = self.camp(rights="RIGHTS_PASS")
        c.approve(GATE_PUBLISH, "master", "shaX")
        r1 = c.publish("shaX")
        r2 = c.publish("shaX")  # retry
        self.assertTrue(all("idempotent_skip" in v for v in r2.values()))
        self.assertFalse(any(v.get("idempotent_skip") for v in r1.values()))

    # 13
    def test_aakhri_state_reconstruction(self):
        c = self.camp(rights="RIGHTS_HOLD")
        frozen = make_frozen(self.tmp)
        fsha = production.assert_master_payload(frozen)
        # reconstruct: creative approved (frozen), final video approved (master), publish NOT approved
        c.approve(GATE_CREATIVE, "frozen", fsha)
        c.approve(GATE_FINAL_VIDEO, "master", "MASTER_SHA")
        c._status["current_state"] = State.FINAL_VIDEO_APPROVED.value
        c._status["video_approval"] = True
        st = c.advance(master_path="master.mp4", master_sha="MASTER_SHA")
        self.assertEqual(st, State.AWAITING_PUBLISH_APPROVAL)   # hard stop at publish gate
        self.assertFalse(c._status["publish_approval"])
        with self.assertRaises(PermissionError):
            c.publish("MASTER_SHA")  # blocked: no publish approval

    # extra: transition table sanity
    def test_transition_table(self):
        self.assertTrue(can_transition(State.TECH_QC_PASS, State.AWAITING_FINAL_VIDEO_APPROVAL))
        self.assertFalse(can_transition(State.SOURCE_READY, State.PUBLISHED))
        self.assertTrue(can_transition(State.PRODUCTION_RENDERING, State.HOLD))


if __name__ == "__main__":
    unittest.main(verbosity=2)
