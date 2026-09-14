"""Tests for the Poster Publish Approval Provisioner (grants only; platform-scoped keys)."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_ASSET, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE
from unpipe.provisioner import PosterProvisioner, ProvisionError
from unpipe.util import read_json

CID = "poster_serie_01"
IMG = b"\x89PNG-exact-image-bytes"
CAP = "Er is een reden. \U0001F3A4"
PLAT = "instagram"
SVER = "v1"
SCHED = "2026-06-01 12:00:00"
EXP = 4_102_444_800


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json"))
        self.grants = str(Path(self.tmp) / "_publish_grants.json")
        self.prov = PosterProvisioner(self.store, self.grants)
        self.key = PosterProvisioner.grant_key(CID, PLAT)

    def _fp(self, caption=CAP, platform=PLAT, sver=SVER):
        fp, _, _ = self.prov.compute_poster_fingerprint(CID, IMG, caption, platform, sver)
        return fp

    def _approve_all(self, fp, gates=(GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH), campaign=None):
        for g in gates:
            self.store.record(campaign or self.key, "asset", g, APPROVE, "nitin", fp)

    def test_valid_grant_creation(self):
        self._approve_all(self._fp())
        grant = self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.assertEqual(grant["fingerprint"], self._fp())
        self.assertEqual(grant["platforms"], [PLAT])
        self.assertEqual(grant["content_id"], CID)
        self.assertEqual(grant["medium"], "poster")
        self.assertFalse(grant["revoked"])
        self.assertIn(self.key, read_json(self.grants)["grants"])

    def test_refuse_when_publish_gate_missing(self):
        self._approve_all(self._fp(), gates=(GATE_CREATIVE, GATE_FINAL_ASSET))
        with self.assertRaises(ProvisionError):
            self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.assertIsNone(read_json(self.grants))

    def test_refuse_when_final_asset_missing(self):
        self._approve_all(self._fp(), gates=(GATE_CREATIVE, GATE_PUBLISH))
        with self.assertRaises(ProvisionError):
            self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)

    def test_final_video_does_not_satisfy_poster_final_asset(self):
        self._approve_all(self._fp(), gates=(GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH))
        with self.assertRaises(ProvisionError):
            self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)

    def test_revoke_is_per_platform(self):
        self._approve_all(self._fp())
        self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.assertTrue(self.prov.revoke_grant(CID, PLAT))
        self.assertTrue(read_json(self.grants)["grants"][self.key]["revoked"])
        self.assertFalse(self.prov.revoke_grant(CID, "facebook"))

    def test_idempotent_identical(self):
        self._approve_all(self._fp())
        g1 = self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        g2 = self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.assertEqual(g1, g2)
        self.assertEqual(len(read_json(self.grants)["grants"]), 1)

    def test_material_change_requires_new_binding(self):
        self._approve_all(self._fp(caption=CAP))
        self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.assertNotEqual(self._fp(caption=CAP), self._fp(caption="A DIFFERENT CAPTION"))
        with self.assertRaises(ProvisionError):
            self.prov.create_grant(CID, IMG, "A DIFFERENT CAPTION", PLAT, SCHED, SVER, EXP)

    def test_provisioner_never_writes_approvals(self):
        self._approve_all(self._fp())
        before = copy.deepcopy(self.store.all(self.key))
        self.prov.create_grant(CID, IMG, CAP, PLAT, SCHED, SVER, EXP)
        self.prov.revoke_grant(CID, PLAT)
        self.assertEqual(self.store.all(self.key), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
