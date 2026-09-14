"""Multi-platform poster grants: content_id::platform keys, cross-platform isolation, legacy fallback."""
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
from unpipe.util import read_json, sha256_bytes

CID = "poster_serie_01"
IMG = b"\x89PNG-exact-image-bytes"
CAP = "Bollywood zoals het bedoeld is."
SVER = "v1"
SCHED = "2026-06-01 12:00:00"


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json"))
        self.gp = str(Path(self.tmp) / "_publish_grants.json")
        self.prov = PosterProvisioner(self.store, self.gp)
        self.epoch = C.scheduled_at_to_epoch(SCHED)
        self.asset = sha256_bytes(IMG)
        self.pkg = C.packaging_sha256(CID, CAP)

    def _fp(self, platform, caption=CAP):
        return C.compute_fingerprint(CID, self.asset, platform, C.packaging_sha256(CID, caption), SVER)

    def _provision(self, platform, exp=None, caption=CAP):
        key = PosterProvisioner.grant_key(CID, platform)
        fp = self._fp(platform, caption)
        for g in (GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH):
            self.store.record(key, "asset", g, APPROVE, "nitin", fp)
        return self.prov.create_grant(CID, IMG, caption, platform, SCHED, SVER,
                                      exp if exp is not None else self.epoch + 100000)

    def _svc(self):
        return PublishApprovalService(self.store, self.gp, now=lambda: self.epoch)

    def _req(self, platform, **over):
        r = {"content_id": CID, "platform": platform, "asset_sha256": self.asset,
             "packaging_sha256": self.pkg, "schedule_version": SVER, "scheduled_at_epoch": self.epoch}
        r.update(over)
        return r

    def test_ig_and_fb_coexist_and_both_authorize(self):
        self._provision("instagram")
        self._provision("facebook")
        keys = set(read_json(self.gp)["grants"].keys())
        self.assertEqual(keys, {"poster_serie_01::instagram", "poster_serie_01::facebook"})
        self.assertTrue(self._svc().evaluate(self._req("instagram"))["eligible"])
        self.assertTrue(self._svc().evaluate(self._req("facebook"))["eligible"])

    def test_ig_grant_cannot_authorize_fb(self):
        self._provision("instagram")
        self.assertTrue(self._svc().evaluate(self._req("instagram"))["eligible"])
        r = self._svc().evaluate(self._req("facebook"))
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    def test_fb_grant_cannot_authorize_ig(self):
        self._provision("facebook")
        self.assertTrue(self._svc().evaluate(self._req("facebook"))["eligible"])
        self.assertFalse(self._svc().evaluate(self._req("instagram"))["eligible"])

    def test_revoke_ig_does_not_affect_fb(self):
        self._provision("instagram")
        self._provision("facebook")
        self.prov.revoke_grant(CID, "instagram")
        self.assertFalse(self._svc().evaluate(self._req("instagram"))["eligible"])
        self.assertTrue(self._svc().evaluate(self._req("facebook"))["eligible"])

    def test_expired_platform_blocks_only_that_platform(self):
        self._provision("instagram", exp=self.epoch - 1)
        self._provision("facebook")
        ig = self._svc().evaluate(self._req("instagram"))
        self.assertFalse(ig["eligible"])
        self.assertEqual(ig["reason"], "EXPIRED")
        self.assertTrue(self._svc().evaluate(self._req("facebook"))["eligible"])

    def test_material_change_ig_does_not_mutate_fb(self):
        self._provision("instagram")
        fb_grant = self._provision("facebook")
        fb_before = dict(read_json(self.gp)["grants"]["poster_serie_01::facebook"])
        self._provision("instagram", caption="A NEW IG CAPTION")
        fb_after = read_json(self.gp)["grants"]["poster_serie_01::facebook"]
        self.assertEqual(fb_before, fb_after)
        self.assertEqual(fb_after["fingerprint"], fb_grant["fingerprint"])

    def test_legacy_video_grant_still_resolves(self):
        vid = "LEGACY_VIDEO_01"
        asset = "vid_master_sha"
        fp = C.compute_fingerprint(vid, asset, "instagram", "", "v1")
        for g in (GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH):
            self.store.record(vid, "asset", g, APPROVE, "nitin", fp)
        grants = {vid: {"approval_id": "PA-legacy", "fingerprint": fp, "platforms": ["instagram"],
                        "schedule_window": [self.epoch - 10, self.epoch + 10], "schedule_version": "v1",
                        "exp": self.epoch + 10000, "revoked": False}}
        svc = PublishApprovalService(self.store, grants, now=lambda: self.epoch)
        req = {"content_id": vid, "platform": "instagram", "asset_sha256": asset,
               "packaging_sha256": "", "schedule_version": "v1", "scheduled_at_epoch": self.epoch}
        r = svc.evaluate(req)
        self.assertTrue(r["eligible"])
        self.assertEqual(r["reason"], REASON_ELIGIBLE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
