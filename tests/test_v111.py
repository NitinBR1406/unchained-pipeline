"""V1.1.1 approval-driven auto-dispatch tests (mock dispatcher, no network, no paid render)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unpipe.orchestrator import Campaign
from unpipe.states import State
from unpipe.approvals import GATE_CREATIVE, APPROVE, REJECT
from unpipe.jobs import JOB_DONE, JOB_RUNNING, JOB_HOLD, JOB_DISPATCH_RETRY
from unpipe.dispatcher import FakeDispatcher
from unpipe.util import sha256_file


def write_frozen(p):
    Path(p).write_text(json.dumps({"timeline": {"tracks": [{"clips": []}]},
                                   "output": {"format": "mp4"}}))


def make_manifest(tmp):
    m = {"campaign_id": "t3", "artist": "UNCHAINED NITIN", "song_title": "T3",
         "release_type": "cover", "source_master": "s.mp4", "duration": 208.625,
         "aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24,
         "presentation_preset": "MOTION_A_PREMIUM_RESTRAINED",
         "brand_profile": "UNCHAINED_NITIN_BRAND_PROFILE_V1",
         "platform_targets": ["youtube_hero"], "rights": {"status": "RIGHTS_HOLD"},
         "frozen_master": "frozen.json"}
    p = Path(tmp) / "campaign.json"; p.write_text(json.dumps(m)); return p


class V111(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.frozen = Path(self.tmp) / "frozen.json"; write_frozen(self.frozen)
        self.mani = make_manifest(self.tmp)
        self.wd = Path(self.tmp) / "wd"
        self.sha = sha256_file(self.frozen)

    def camp(self, disp):
        return Campaign(self.wd, self.mani, runner_path="/x", dispatcher=disp)

    # APPROVE auto-dispatches
    def test_approve_dispatches(self):
        d = FakeDispatcher(); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(d.calls, ["t3"])

    # REJECT does not dispatch
    def test_reject_no_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha, decision=REJECT)
        self.assertEqual(d.calls, [])

    # missing approval -> no dispatch
    def test_no_approval_no_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        self.assertEqual(d.calls, [])
        self.assertEqual(len(c.jobs.all()), 0)

    # SHA mismatch -> no dispatch
    def test_sha_mismatch_no_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", "WRONG")
        self.assertEqual(d.calls, [])

    # duplicate approval -> single dispatch (no duplicate render)
    def test_duplicate_approve_single_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(d.calls, ["t3"])          # only once
        self.assertEqual(len(c.jobs.all()), 1)

    # existing DONE job -> no dispatch
    def test_existing_done_no_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        job, _ = c.jobs.enqueue("t3", "frozen_master", self.sha, GATE_CREATIVE)
        c.jobs.update(job["job_id"], status=JOB_DONE)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(d.calls, [])

    # existing RUNNING job -> no dispatch
    def test_existing_running_no_dispatch(self):
        d = FakeDispatcher(); c = self.camp(d)
        job, _ = c.jobs.enqueue("t3", "frozen_master", self.sha, GATE_CREATIVE)
        c.jobs.update(job["job_id"], status=JOB_RUNNING)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(d.calls, [])

    # dispatch auth failure -> safe HOLD, approval preserved
    def test_auth_failure_holds(self):
        d = FakeDispatcher(auth_fail=True); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(c.state, State.HOLD)
        self.assertEqual(c.jobs.all()[0]["status"], JOB_HOLD)
        self.assertIsNotNone(c.approvals.latest("t3", GATE_CREATIVE))  # not lost

    # transient dispatch failure -> bounded retry then success
    def test_transient_retry(self):
        d = FakeDispatcher(transient_before_success=2); c = self.camp(d)  # retries default 3
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(len(d.calls), 3)          # 2 fail + 1 success
        self.assertNotEqual(c.state, State.HOLD)

    # transient exhausted -> HOLD / DISPATCH_RETRY
    def test_transient_exhausted_holds(self):
        d = FakeDispatcher(transient_before_success=99); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(c.state, State.HOLD)
        self.assertEqual(c.jobs.all()[0]["status"], JOB_DISPATCH_RETRY)

    # secrets absent from persisted state/logs
    def test_secrets_not_persisted(self):
        os.environ["GITHUB_DISPATCH_TOKEN"] = "ghs_TOKENSECRET999"
        os.environ["SHOTSTACK_PRODUCTION_API_KEY"] = "shk_KEYSECRET999"
        d = FakeDispatcher(); c = self.camp(d)
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        blob = "".join(f.read_text(errors="ignore") for f in Path(self.wd).rglob("*") if f.is_file())
        self.assertNotIn("ghs_TOKENSECRET999", blob)
        self.assertNotIn("shk_KEYSECRET999", blob)
        os.environ.pop("GITHUB_DISPATCH_TOKEN", None)
        os.environ.pop("SHOTSTACK_PRODUCTION_API_KEY", None)

    # AKI historical (already rendered) -> no rerender dispatch
    def test_aki_like_no_rerender(self):
        d = FakeDispatcher(); c = self.camp(d)
        job, _ = c.jobs.enqueue("t3", "frozen_master", self.sha, GATE_CREATIVE)
        c.jobs.update(job["job_id"], status=JOB_DONE, shotstack_render_id="hist-123")
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(d.calls, [])

    # None dispatcher (default) -> no live dispatch (safe)
    def test_no_dispatcher_safe(self):
        c = Campaign(self.wd, self.mani, runner_path="/x")  # dispatcher None
        c.approve(GATE_CREATIVE, "frozen_master", self.sha)
        self.assertEqual(len(c.jobs.all()), 1)   # queued, but not dispatched anywhere

    # workflow_dispatch remains for recovery
    def test_workflow_dispatch_present(self):
        wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "production.yml").read_text()
        self.assertIn("workflow_dispatch", wf)
        self.assertIn("repository_dispatch", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
