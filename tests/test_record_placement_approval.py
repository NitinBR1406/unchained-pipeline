"""Host CLI chain for one placement: record Nitin's 3 gates -> grant from hashes -> verifier ELIGIBLE for exactly that
file/text/platform/account; anything else stays blocked. Temp stores only."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import record_placement_approval as R, provision_placement as P
from unpipe.approvals import ApprovalStore
from unpipe.placement_provisioner import PlacementProvisioner
from unpipe.publish_approval import PublishApprovalService
from unpipe import canonical as C

CID, PLAT, ACCT = "aki:post:TEASER-NEON-V03", "youtube_shorts", "YouTube channel X"
SHA = "9470bd48072809f0d6ce1171a2e0d03c780f1b8f617b2b80b24422c1134f8c80"
TITLE, DESC = "Aakhri Ishq \U0001f5a4 | Cover Teaser by Unchained Nitin", "Some feelings never fade.\n\n#AakhriIshq"


class RecordApprovalChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.a, self.g = str(Path(self.tmp) / "a.json"), str(Path(self.tmp) / "g.json")
        _, self.pkg = PlacementProvisioner.fingerprint(CID, SHA, PLAT, TITLE, DESC, "1")
        self.when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        os.environ["APPROVERS"] = "nitin"

    def rec(self, **kw):
        args = dict(approvals=self.a, content_id=CID, platform=PLAT, asset_sha256=SHA, packaging_sha256=self.pkg,
                    schedule_version="1", approver="nitin", evidence="test")
        args.update(kw)
        return R.main(sum([["--" + k.replace("_", "-"), v] for k, v in args.items()], []))

    def grant(self):
        return P.main(["create", "--grants", self.g, "--approvals", self.a, "--content-id", CID, "--platform", PLAT,
                       "--target-account", ACCT, "--asset-sha256", SHA, "--packaging-sha256", self.pkg,
                       "--scheduled-at", self.when, "--schedule-version", "1", "--exp", str(int(time.time()) + 3600)])

    def req(self, **kw):
        r = {"content_id": CID, "platform": PLAT, "target_account": ACCT, "asset_sha256": SHA, "packaging_sha256": self.pkg,
             "schedule_version": "1", "scheduled_at_epoch": C.scheduled_at_to_epoch(self.when)}
        r.update(kw)
        return PublishApprovalService(ApprovalStore(self.a), self.g).evaluate(r)

    def test_chain_makes_exactly_this_placement_eligible(self):
        self.assertEqual(self.grant(), 2)                        # no approvals yet -> grant refused
        self.assertEqual(self.rec(), 0)
        self.assertEqual(self.grant(), 0)
        self.assertTrue(self.req()["eligible"])
        for kw in ({"asset_sha256": "0" * 64}, {"packaging_sha256": "1" * 64}, {"platform": "instagram_reels"},
                   {"target_account": "other"}, {"schedule_version": "2"}):
            with self.subTest(kw=kw):
                self.assertFalse(self.req(**kw)["eligible"])

    def test_epoch_instead_of_local_time(self):
        self.rec()
        ep = C.scheduled_at_to_epoch(self.when)
        rc = P.main(["create", "--grants", self.g, "--approvals", self.a, "--content-id", CID, "--platform", PLAT,
                     "--target-account", ACCT, "--asset-sha256", SHA, "--packaging-sha256", self.pkg,
                     "--scheduled-at-epoch", str(ep), "--schedule-version", "1", "--exp", str(int(time.time()) + 3600)])
        self.assertEqual(rc, 0)
        self.assertTrue(self.req()["eligible"])

    def test_refusals(self):
        self.assertEqual(self.rec(approver="someone"), 2)
        self.assertEqual(self.rec(content_id="test:post:X"), 2)
        self.assertEqual(self.rec(asset_sha256="ABC"), 2)
        self.assertFalse(Path(self.a).exists())


if __name__ == "__main__":
    unittest.main()
