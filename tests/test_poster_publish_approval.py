"""Poster path of the Publish Approval verifier (medium-neutral final gate) + provisioner integration."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import (ApprovalStore, GATE_CREATIVE, GATE_FINAL_ASSET, GATE_FINAL_VIDEO,
                              GATE_PUBLISH, APPROVE)
from unpipe.publish_approval import PublishApprovalService, REASON_ELIGIBLE
from unpipe.provisioner import PosterProvisioner
from unpipe import canonical as C
from unpipe.util import sha256_bytes

CID = "poster_serie_01"
IMG = b"\x89PNG-exact-image-bytes"
CAP = "Bollywood zoals het bedoeld is."
PLAT = "instagram"
SVER = "v1"
SCHED = "2026-06-01 12:00:00"


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json"))
        self.asset = sha256_bytes(IMG)
        self.pkg = C.packaging_sha256(CID, CAP)
        self.epoch = C.scheduled_at_to_epoch(SCHED)
        self.fp = C.compute_fingerprint(CID, self.asset, PLAT, self.pkg, SVER)

    def _req(self, **over):
        r = {"content_id": CID, "platform": PLAT, "asset_sha256": self.asset,
             "packaging_sha256": self.pkg, "schedule_version": SVER, "scheduled_at_epoch": self.epoch}
        r.update(over)
        return r

    def _grant(self, **over):
        # keyed by content_id (legacy fallback path) with medium=poster to exercise the final-asset gate
        g = {"approval_id": "PA-poster", "fingerprint": self.fp, "platforms": [PLAT],
             "schedule_window": C.schedule_window(self.epoch), "schedule_version": SVER,
             "exp": self.epoch + 100000, "revoked": False, "medium": "poster"}
        g.update(over)
        return {CID: g}

    def _svc(self, grants):
        return PublishApprovalService(self.store, grants, now=lambda: self.epoch)

    def _approve(self, gates):
        for g in gates:
            self.store.record(CID, "asset", g, APPROVE, "nitin", self.fp)

    def test_poster_three_gate_eligible(self):
        self._approve((GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req())
        self.assertTrue(r["eligible"])
        self.assertEqual(r["reason"], REASON_ELIGIBLE)

    def test_poster_missing_final_asset_blocked(self):
        self._approve((GATE_CREATIVE, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req())
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "FINAL_ASSET_APPROVAL_MISSING")

    def test_poster_final_video_does_not_satisfy(self):
        self._approve((GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req())
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "FINAL_ASSET_APPROVAL_MISSING")

    def test_poster_missing_creative_blocked(self):
        self._approve((GATE_FINAL_ASSET, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req())
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "CREATIVE_APPROVAL_MISSING")

    def test_poster_missing_publish_blocked(self):
        self._approve((GATE_CREATIVE, GATE_FINAL_ASSET))
        r = self._svc(self._grant()).evaluate(self._req())
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    def test_poster_wrong_platform_blocked(self):
        self._approve((GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req(platform="facebook"))
        self.assertFalse(r["eligible"])

    def test_poster_outside_window_blocked(self):
        self._approve((GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH))
        r = self._svc(self._grant()).evaluate(self._req(scheduled_at_epoch=self.epoch + 10**9))
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "SCHEDULE_MISMATCH")

    def test_integration_provisioner_then_verifier(self):
        # provisioner path uses the platform-scoped campaign key content_id::platform
        key = PosterProvisioner.grant_key(CID, PLAT)
        for g in (GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH):
            self.store.record(key, "asset", g, APPROVE, "nitin", self.fp)
        gp = str(Path(self.tmp) / "_publish_grants.json")
        prov = PosterProvisioner(self.store, gp)
        prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, self.epoch + 100000)
        svc = PublishApprovalService(self.store, gp, now=lambda: self.epoch)
        r = svc.evaluate(self._req())
        self.assertTrue(r["eligible"])
        self.assertEqual(r["reason"], REASON_ELIGIBLE)
        prov.revoke_grant(CID, PLAT)
        svc2 = PublishApprovalService(self.store, gp, now=lambda: self.epoch)
        self.assertFalse(svc2.evaluate(self._req())["eligible"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
