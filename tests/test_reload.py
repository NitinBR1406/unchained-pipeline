"""P0-D step 1: per-request store reload -> grant/approval changes (esp. revocation) take effect on the
next request with NO restart. Simulates the server's per-request build (fresh ApprovalStore +
PublishApprovalService re-reading the on-disk stores) while mutating the grants file between calls."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH, APPROVE
from unpipe.publish_approval import PublishApprovalService
from unpipe import canonical as C
from unpipe.util import write_json

CID = "P0D_RELOAD"; PLAT = "instagram"; NOW = 1_000_000
ASSET = "a1"; PKG = "p1"; SVER = "v1"; SCHED = NOW + 100


def fp():
    return C.compute_fingerprint(CID, ASSET, PLAT, PKG, SVER)


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.apath = str(Path(self.tmp) / "_publish_approvals.json")
        self.gpath = str(Path(self.tmp) / "_publish_grants.json")
        st = ApprovalStore(self.apath)
        key = CID + "::" + PLAT
        for g in (GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH):
            st.record(key, "asset", g, APPROVE, "nitin", fp())

    def _grant(self, **over):
        g = {"approval_id": "PA", "content_id": CID, "fingerprint": fp(), "platforms": [PLAT],
             "schedule_window": [NOW, NOW + 1000], "schedule_version": SVER, "exp": NOW + 10000,
             "revoked": False, "medium": "poster"}
        g.update(over)
        return {"grants": {CID + "::" + PLAT: g}}

    def _svc(self):
        # a fresh build == exactly what approval_server now does per request (re-reads both stores)
        return PublishApprovalService(ApprovalStore(self.apath), self.gpath, now=lambda: NOW)

    def _req(self, **over):
        r = {"content_id": CID, "platform": PLAT, "asset_sha256": ASSET, "packaging_sha256": PKG,
             "schedule_version": SVER, "scheduled_at_epoch": SCHED}
        r.update(over)
        return r

    def test_A_valid_before_revoke(self):
        write_json(self.gpath, self._grant())
        self.assertTrue(self._svc().evaluate(self._req())["eligible"])

    def test_B_revoke_on_disk_no_restart(self):
        write_json(self.gpath, self._grant())
        self.assertTrue(self._svc().evaluate(self._req())["eligible"])
        write_json(self.gpath, self._grant(revoked=True))
        r = self._svc().evaluate(self._req())
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "REVOKED")

    def test_C_restore_no_restart(self):
        write_json(self.gpath, self._grant(revoked=True))
        self.assertFalse(self._svc().evaluate(self._req())["eligible"])
        write_json(self.gpath, self._grant())
        self.assertTrue(self._svc().evaluate(self._req())["eligible"])

    def test_expiry(self):
        write_json(self.gpath, self._grant(exp=NOW - 1))
        self.assertEqual(self._svc().evaluate(self._req())["reason"], "EXPIRED")

    def test_fingerprint_mismatch(self):
        write_json(self.gpath, self._grant(fingerprint="DIFFERENT"))
        self.assertFalse(self._svc().evaluate(self._req())["eligible"])

    def test_platform_isolation(self):
        write_json(self.gpath, self._grant())
        self.assertFalse(self._svc().evaluate(self._req(platform="facebook"))["eligible"])

    def test_schedule_mismatch(self):
        write_json(self.gpath, self._grant())
        self.assertEqual(self._svc().evaluate(self._req(scheduled_at_epoch=NOW + 999999))["reason"],
                         "SCHEDULE_MISMATCH")

    def test_schedule_version_mismatch(self):
        write_json(self.gpath, self._grant())
        self.assertFalse(self._svc().evaluate(self._req(schedule_version="v2"))["eligible"])

    def test_missing_grant(self):
        write_json(self.gpath, {"grants": {}})
        self.assertEqual(self._svc().evaluate(self._req())["reason"], "NO_PUBLISH_APPROVAL")

    def test_malformed_request(self):
        write_json(self.gpath, self._grant())
        self.assertEqual(self._svc().evaluate("not-a-dict")["reason"], "MALFORMED_REQUEST")


if __name__ == "__main__":
    unittest.main(verbosity=2)
