"""V1.1 zero-terminal production executor tests (no network, no paid renders)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unpipe import mediaqc, executor, production
from unpipe.orchestrator import Campaign
from unpipe.states import State
from unpipe.approvals import GATE_CREATIVE
from unpipe.jobs import JOB_DONE, JOB_HOLD
from unpipe.util import sha256_file


def write_frozen(path, with_range=False):
    edit = {"timeline": {"tracks": [{"clips": []}]},
            "output": {"format": "mp4", "size": {"width": 1080, "height": 1920}, "fps": 24}}
    if with_range:
        edit["output"]["range"] = {"start": 4, "length": 6}
    Path(path).write_text(json.dumps(edit))


def make_manifest(tmp, frozen_rel="frozen.json"):
    m = {"campaign_id": "t2", "artist": "UNCHAINED NITIN", "song_title": "T2",
         "release_type": "cover", "source_master": "s.mp4", "duration": 208.625,
         "aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24,
         "presentation_preset": "MOTION_A_PREMIUM_RESTRAINED",
         "brand_profile": "UNCHAINED_NITIN_BRAND_PROFILE_V1",
         "platform_targets": ["youtube_hero"], "rights": {"status": "RIGHTS_HOLD"},
         "frozen_master": frozen_rel}
    p = Path(tmp) / "campaign.json"
    p.write_text(json.dumps(m))
    return p


def pass_qc(monkey_target):
    """Return good ffprobe info for a 208.625s 1080x1920 24fps file with audio."""
    monkey_target.ffprobe_available = lambda: True
    monkey_target.probe = lambda p: {
        "streams": [{"codec_type": "video", "width": 1080, "height": 1920,
                     "r_frame_rate": "24/1", "codec_name": "h264"},
                    {"codec_type": "audio", "codec_name": "aac", "duration": "208.6"}],
        "format": {"duration": "208.625", "format_name": "mp4"}}


class V11(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.frozen = Path(self.tmp) / "frozen.json"
        write_frozen(self.frozen)
        self.mani = make_manifest(self.tmp)
        self.wd = Path(self.tmp) / "wd"
        self._orig = (mediaqc.ffprobe_available, mediaqc.probe)

    def tearDown(self):
        mediaqc.ffprobe_available, mediaqc.probe = self._orig

    def camp(self):
        return Campaign(self.wd, self.mani, runner_path="/x")

    def approved_ready(self):
        c = self.camp()
        sha = sha256_file(self.frozen)
        c.approve(GATE_CREATIVE, "frozen_master", sha)     # auto-queues
        c._status["current_state"] = State.FROZEN_JSON_READY.value
        c._save_status()
        job = c.jobs.all()[0]
        return c, job, sha

    # 1
    def test_creative_approval_autoqueues(self):
        c = self.camp()
        c.approve(GATE_CREATIVE, "frozen_master", sha256_file(self.frozen))
        self.assertEqual(len(c.jobs.all()), 1)

    # 2
    def test_no_approval_no_job(self):
        c = self.camp()
        self.assertEqual(len(c.jobs.all()), 0)

    # 3
    def test_sha_mismatch_no_queue(self):
        c = self.camp()
        c.approve(GATE_CREATIVE, "frozen_master", "WRONGSHA")
        self.assertEqual(len(c.jobs.all()), 0)

    # 4 + 17
    def test_duplicate_enqueue_no_duplicate(self):
        c = self.camp()
        sha = sha256_file(self.frozen)
        c.approve(GATE_CREATIVE, "frozen_master", sha)
        c.approve(GATE_CREATIVE, "frozen_master", sha)  # again
        self.assertEqual(len(c.jobs.all()), 1)

    # 5
    def test_sandbox_endpoint_holds(self):
        c, job, sha = self.approved_ready()
        be = executor.FakeBackend(endpoint="https://api.shotstack.io/edit/stage/render")
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_HOLD)
        self.assertEqual(c.state, State.HOLD)

    # 6
    def test_missing_secret_safe_failure(self):
        c, job, sha = self.approved_ready()
        os.environ.pop("SHOTSTACK_PRODUCTION_API_KEY", None)
        be = executor.HttpProductionBackend()  # will MaterialError on missing key before network
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_HOLD)

    # 7
    def test_secret_never_persisted(self):
        os.environ["SHOTSTACK_PRODUCTION_API_KEY"] = "SUPERSECRETVALUE123"
        c, job, sha = self.approved_ready()
        pass_qc(mediaqc)
        be = executor.FakeBackend()
        executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        blob = ""
        for f in Path(self.wd).rglob("*"):
            if f.is_file():
                blob += f.read_text(errors="ignore")
        self.assertNotIn("SUPERSECRETVALUE123", blob)
        os.environ.pop("SHOTSTACK_PRODUCTION_API_KEY", None)

    # 8 + 9 (429 / 5xx modelled as TransientError, retried)
    def test_transient_retry_succeeds(self):
        c, job, sha = self.approved_ready()
        pass_qc(mediaqc)
        be = executor.FakeBackend(transient_before_success=2)
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_DONE)

    # 10
    def test_invalid_range_json_holds(self):
        write_frozen(self.frozen, with_range=True)
        c = self.camp()
        sha = sha256_file(self.frozen)
        c.approve(GATE_CREATIVE, "frozen_master", sha)
        c._status["current_state"] = State.FROZEN_JSON_READY.value; c._save_status()
        job = c.jobs.all()[0]
        be = executor.FakeBackend()
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_HOLD)

    # 11 + 12 + 13 + 14
    def test_success_download_hash_qc_awaitfinal(self):
        c, job, sha = self.approved_ready()
        pass_qc(mediaqc)
        be = executor.FakeBackend()
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_DONE)
        self.assertTrue(res["output_sha256"])                 # hashed
        self.assertEqual(res["tech_qc_status"], "PASS")       # QC ran + passed
        self.assertTrue((Path(self.wd) / "out.mp4").exists()) # downloaded
        self.assertEqual(c.state, State.AWAITING_FINAL_VIDEO_APPROVAL)

    # 15
    def test_qc_fail_holds(self):
        c, job, sha = self.approved_ready()
        mediaqc.ffprobe_available = lambda: True
        mediaqc.probe = lambda p: {"streams": [{"codec_type": "video", "width": 1080,
                                   "height": 1920, "r_frame_rate": "24/1", "codec_name": "h264"}],
                                   "format": {"duration": "10.0", "format_name": "mp4"}}  # no audio + wrong dur
        be = executor.FakeBackend()
        res = executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(res["status"], JOB_HOLD)
        self.assertEqual(c.state, State.HOLD)

    # 16
    def test_completed_job_not_rerendered(self):
        c, job, sha = self.approved_ready()
        pass_qc(mediaqc)
        be = executor.FakeBackend()
        executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        submits_after_first = be._submits
        # re-run same DONE job
        executor.run_production_job(c, job, be, str(self.frozen), "out.mp4", sleep=lambda s: None)
        self.assertEqual(be._submits, submits_after_first)  # no new submit


if __name__ == "__main__":
    unittest.main(verbosity=2)
