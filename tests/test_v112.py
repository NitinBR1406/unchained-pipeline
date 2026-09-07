"""V1.1.2 one-tap approval service tests (no network, no paid render, no publish)."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unpipe.orchestrator import Campaign
from unpipe.states import State
from unpipe.approvals import GATE_CREATIVE, APPROVE, REJECT
from unpipe.dispatcher import FakeDispatcher
from unpipe.approval_service import ApprovalService, ApprovalError
from unpipe.util import sha256_file


def write_frozen(p, tag="x"):
    Path(p).write_text(json.dumps({"timeline": {"tracks": [{"clips": [{"t": tag}]}]},
                                   "output": {"format": "mp4"}}))


def make_manifest(tmp):
    m = {"campaign_id": "t4", "artist": "UNCHAINED NITIN", "song_title": "Aakhri Ishq (test)",
         "release_type": "cover", "source_master": "s.mp4", "duration": 208.625,
         "aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24,
         "presentation_preset": "MOTION_A_PREMIUM_RESTRAINED",
         "brand_profile": "UNCHAINED_NITIN_BRAND_PROFILE_V1",
         "platform_targets": ["youtube_hero"], "rights": {"status": "RIGHTS_HOLD"},
         "frozen_master": "frozen.json", "release_status": "V01"}
    p = Path(tmp) / "campaign.json"; p.write_text(json.dumps(m)); return p


class V112(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.frozen = Path(self.tmp) / "frozen.json"; write_frozen(self.frozen)
        self.mani = make_manifest(self.tmp)
        self.wd = Path(self.tmp) / "wd"
        self.sha = sha256_file(self.frozen)
        self.disp = FakeDispatcher()
        self._camps = {}
        self.svc = ApprovalService(
            signing_secret="server-side-signing-secret",
            campaign_factory=self._factory,
            approvers=["nitin"],
            consumed_path=str(Path(self.tmp) / "consumed.json"))

    def _factory(self, cid):
        if cid not in self._camps:
            self._camps[cid] = Campaign(self.wd, self.mani, dispatcher=self.disp)
        return self._camps[cid]

    def token(self, ttl=3600, gate=GATE_CREATIVE):
        return self.svc.create_request("t4", gate, "frozen_master", self.sha, ttl=ttl)

    # authoritative approve
    def test_approve_records_authoritative(self):
        r = self.svc.decide(self.token(), APPROVE, "nitin")
        self.assertEqual(r["status"], "RECORDED")
        rec = self._factory("t4").approvals.latest("t4", GATE_CREATIVE)
        for k in ("campaign_id", "asset_id", "gate", "decision", "approved_by",
                  "timestamp", "artifact_sha256", "version"):
            self.assertIn(k, rec)
        self.assertEqual(rec["approved_by"], "nitin")

    def test_reject_records_no_dispatch(self):
        r = self.svc.decide(self.token(), REJECT, "nitin")
        self.assertEqual(r["decision"], REJECT)
        self.assertEqual(self.disp.calls, [])

    def test_approve_autodispatches(self):
        self.svc.decide(self.token(), APPROVE, "nitin")
        self.assertEqual(self.disp.calls, ["t4"])

    def test_unauthorized_blocked(self):
        with self.assertRaises(ApprovalError):
            self.svc.decide(self.token(), APPROVE, "someone_else")
        self.assertEqual(self.disp.calls, [])

    def test_expired_rejected(self):
        with self.assertRaises(ApprovalError):
            self.svc.decide(self.token(ttl=-10), APPROVE, "nitin")

    def test_bad_signature_rejected(self):
        t = self.token()
        tampered = t[:-2] + ("aa" if not t.endswith("aa") else "bb")
        with self.assertRaises(ApprovalError):
            self.svc.decide(tampered, APPROVE, "nitin")

    def test_replay_idempotent(self):
        t = self.token()
        r1 = self.svc.decide(t, APPROVE, "nitin")
        r2 = self.svc.decide(t, APPROVE, "nitin")   # double tap / duplicate callback
        self.assertTrue(r2.get("idempotent_replay"))
        self.assertEqual(self.disp.calls, ["t4"])   # only one dispatch

    def test_sha_mismatch_blocks(self):
        t = self.token()
        write_frozen(self.frozen, tag="CHANGED")     # artifact changed after request
        with self.assertRaises(ApprovalError):
            self.svc.decide(t, APPROVE, "nitin")
        self.assertEqual(self.disp.calls, [])
        self.assertEqual(self._factory("t4").state, State.HOLD)

    def test_production_idempotency_intact(self):
        self.svc.decide(self.token(), APPROVE, "nitin")     # token A
        self.svc.decide(self.token(), APPROVE, "nitin")     # token B (new nonce, same sha)
        self.assertEqual(self.disp.calls, ["t4"])           # still one render
        self.assertEqual(len(self._factory("t4").jobs.all()), 1)

    def test_no_secret_in_client_surface(self):
        os.environ["GITHUB_DISPATCH_TOKEN"] = "ghs_CLIENTLEAK999"
        t = self.token()
        page = self.svc.render_request(t)
        blob = json.dumps(page) + t
        self.assertNotIn("ghs_CLIENTLEAK999", blob)
        self.assertNotIn("server-side-signing-secret", blob)
        os.environ.pop("GITHUB_DISPATCH_TOKEN", None)

    def test_no_second_human_gate(self):
        r = self.svc.decide(self.token(), APPROVE, "nitin")
        self.assertTrue(r["dispatched"])            # one tap -> dispatched, no 2nd gate
        self.assertEqual(self.disp.calls, ["t4"])

    def test_render_request_fields_safe(self):
        d = self.svc.render_request(self.token())
        self.assertEqual(d["actions"], ["APPROVE", "REJECT"])
        self.assertNotIn("sha", d)                  # SHA not surfaced


if __name__ == "__main__":
    unittest.main(verbosity=2)
