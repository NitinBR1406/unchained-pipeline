"""Placement (video + still) grants on the publish-eligibility verifier, incl. target-account binding,
synthetic-test namespace isolation, and the authenticated HTTP endpoint run locally (no network, no platform).

All data here is SYNTHETIC: content ids live in the reserved "test:" namespace; nothing can match a real
AKI placement ("aki:post:...")."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import (ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_FINAL_ASSET,
                              GATE_PUBLISH, APPROVE, REJECT)
from unpipe.publish_approval import PublishApprovalService, REASON_ELIGIBLE
from unpipe.placement_provisioner import PlacementProvisioner, ProvisionError, posted_text
from unpipe import canonical as C

CID = "test:aki-synthetic:post:D01-V01"          # synthetic, reserved namespace
PLAT = "youtube_shorts"
ACCT = "TEST-ACCOUNT-YT"
ASSET = "a" * 64
TITLE = "SYNTHETIC title"
CAP = "SYNTHETIC caption #test"
SVER = "1"
SCHED = "2030-01-01 19:00:00"
EXP = 1999999999


class PlacementGrantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json"))
        self.grants = str(Path(self.tmp) / "_publish_grants.json")
        self.epoch = C.scheduled_at_to_epoch(SCHED)
        self.fp, self.pkg = PlacementProvisioner.fingerprint(CID, ASSET, PLAT, TITLE, CAP, SVER)
        self.key = PlacementProvisioner.grant_key(CID, PLAT)

    def _approve(self, gates=(GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH), fp=None, key=None):
        for g in gates:
            self.store.record(key or self.key, "synthetic", g, APPROVE, "test-harness", fp or self.fp)

    def _provision(self, **kw):
        args = dict(content_id=CID, asset_sha256=ASSET, platform=PLAT, target_account=ACCT, title=TITLE, caption=CAP,
                    scheduled_at=SCHED, schedule_version=SVER, exp=EXP, test_only=True)
        args.update(kw)
        return PlacementProvisioner(self.store, self.grants).create_grant(**args)

    def _req(self, **over):
        r = {"content_id": CID, "platform": PLAT, "target_account": ACCT, "asset_sha256": ASSET,
             "packaging_sha256": self.pkg, "schedule_version": SVER, "scheduled_at_epoch": self.epoch}
        r.update(over)
        return r

    def _eval(self, req, now=None, test_mode=True):
        svc = PublishApprovalService(ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json")), self.grants,
                                     now=lambda: now or self.epoch, allow_test_grants=test_mode)
        return svc.evaluate(req)

    # 1. exact package accepted
    def test_valid_synthetic_grant_exact_package_eligible(self):
        self._approve(); self._provision()
        r = self._eval(self._req())
        self.assertTrue(r["eligible"]); self.assertEqual(r["reason"], REASON_ELIGIBLE)

    # 2. every material change refused
    def test_changed_file_refused(self):
        self._approve(); self._provision()
        self.assertFalse(self._eval(self._req(asset_sha256="b" * 64))["eligible"])

    def test_changed_caption_refused(self):
        self._approve(); self._provision()
        other = C.packaging_sha256(CID, posted_text(TITLE, CAP + " edited"))
        self.assertFalse(self._eval(self._req(packaging_sha256=other))["eligible"])

    def test_changed_title_refused(self):
        self._approve(); self._provision()
        other = C.packaging_sha256(CID, posted_text(TITLE + "!", CAP))
        self.assertFalse(self._eval(self._req(packaging_sha256=other))["eligible"])

    def test_other_target_account_refused(self):
        self._approve(); self._provision()
        r = self._eval(self._req(target_account="SOME-OTHER-ACCOUNT"))
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "TARGET_ACCOUNT_MISMATCH")

    def test_missing_target_account_refused(self):
        self._approve(); self._provision()
        req = self._req(); req.pop("target_account")
        self.assertFalse(self._eval(req)["eligible"])

    def test_other_platform_refused(self):
        self._approve(); self._provision()
        self.assertFalse(self._eval(self._req(platform="instagram_reels"))["eligible"])

    def test_changed_schedule_time_refused(self):
        self._approve(); self._provision()
        r = self._eval(self._req(scheduled_at_epoch=self.epoch + 3 * 3600))
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "SCHEDULE_MISMATCH")

    def test_changed_schedule_version_refused(self):
        self._approve(); self._provision()
        self.assertFalse(self._eval(self._req(schedule_version="2"))["eligible"])

    def test_missing_approval_refused(self):
        self._approve(gates=(GATE_CREATIVE, GATE_FINAL_VIDEO))
        with self.assertRaises(ProvisionError):
            self._provision()
        r = self._eval(self._req())
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    def test_revoked_grant_refused(self):
        self._approve(); self._provision()
        PlacementProvisioner(None, self.grants).revoke_grant(CID, PLAT)
        r = self._eval(self._req())
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "REVOKED")

    def test_withdrawn_publish_approval_refused(self):
        self._approve(); self._provision()
        self.store.record(self.key, "synthetic", GATE_PUBLISH, REJECT, "test-harness", self.fp)
        self.assertFalse(self._eval(self._req())["eligible"])

    def test_expired_grant_refused(self):
        self._approve(); self._provision(exp=self.epoch - 1)
        r = self._eval(self._req())
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "EXPIRED")

    def test_still_requires_final_asset_gate(self):
        self._approve(gates=(GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH))
        with self.assertRaises(ProvisionError):
            self._provision(medium="poster")
        self._approve(gates=(GATE_FINAL_ASSET,))
        self._provision(medium="poster")
        self.assertTrue(self._eval(self._req())["eligible"])

    # 3. synthetic data can never release a real AKI placement
    def test_test_grant_cannot_release_real_aki_placement(self):
        self._approve(); self._provision()
        real = "aki:post:D01-V01"
        r = self._eval(self._req(content_id=real))
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    def test_test_grant_refused_by_production_verifier(self):
        self._approve(); self._provision()
        r = self._eval(self._req(), test_mode=False)
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "TEST_GRANT_NOT_ALLOWED")

    def test_provisioner_refuses_test_flag_on_real_id_and_real_grant_in_test_namespace(self):
        with self.assertRaises(ProvisionError):
            self._provision(content_id="aki:post:D01-V01", test_only=True)
        with self.assertRaises(ProvisionError):
            self._provision(test_only=False)

    def test_tampered_test_flag_on_disk_refused(self):
        self._approve(); self._provision()
        data = json.loads(Path(self.grants).read_text())
        data["grants"][self.key]["test_only"] = False          # a test-namespace grant posing as real
        Path(self.grants).write_text(json.dumps(data))
        r = self._eval(self._req())
        self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "MALFORMED_APPROVAL")

    # 4. store unreadable / corrupt -> never an eligible result (the HTTP layer turns the raise into 500/eligible:false)
    def test_corrupt_grant_store_never_eligible(self):
        self._approve(); self._provision()
        Path(self.grants).write_text("{not json")
        with self.assertRaises(Exception):
            self._eval(self._req())


class HttpEndpointTests(unittest.TestCase):
    """Real approval_server.Handler on 127.0.0.1 with temp stores and a throwaway test key (no secrets)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.key = "local-test-key-not-a-secret"
        cls._saved_env = {k: os.environ.get(k) for k in ("PUBLISH_ELIGIBILITY_APIKEY", "PUBLISH_APPROVALS_STORE", "PUBLISH_GRANTS_STORE", "PUBLISH_ALLOW_TEST_GRANTS")}
        os.environ["PUBLISH_ELIGIBILITY_APIKEY"] = cls.key
        os.environ["PUBLISH_ALLOW_TEST_GRANTS"] = "1"          # isolated test server only
        os.environ["PUBLISH_APPROVALS_STORE"] = str(Path(cls.tmp) / "_publish_approvals.json")
        os.environ["PUBLISH_GRANTS_STORE"] = str(Path(cls.tmp) / "_publish_grants.json")
        import approval_server
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), approval_server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/v/publish-eligibility" % cls.srv.server_address[1]
        store = ApprovalStore(os.environ["PUBLISH_APPROVALS_STORE"])
        cls.fp, cls.pkg = PlacementProvisioner.fingerprint(CID, ASSET, PLAT, TITLE, CAP, SVER)
        for g in (GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH):
            store.record(PlacementProvisioner.grant_key(CID, PLAT), "synthetic", g, APPROVE, "test-harness", cls.fp)
        PlacementProvisioner(store, os.environ["PUBLISH_GRANTS_STORE"]).create_grant(
            CID, ASSET, PLAT, ACCT, TITLE, CAP, SCHED, SVER, EXP, test_only=True)
        cls.epoch = C.scheduled_at_to_epoch(SCHED)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for k, v in cls._saved_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def _post(self, body, key=True, raw=None):
        data = raw if raw is not None else json.dumps(body).encode()
        req = urllib.request.Request(self.url, data=data, method="POST", headers={"Content-Type": "application/json"})
        if key:
            req.add_header("x-publish-apikey", self.key)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _body(self, **over):
        b = {"content_id": CID, "platform": PLAT, "target_account": ACCT, "asset_sha256": ASSET,
             "packaging_sha256": self.pkg, "schedule_version": SVER, "scheduled_at_epoch": self.epoch}
        b.update(over)
        return b

    def test_http_valid_synthetic_request(self):
        # the window is around 2030-01-01; 'now' on the server is real time -> grant valid until EXP, schedule bound
        code, r = self._post(self._body())
        self.assertEqual(code, 200); self.assertTrue(r["eligible"])

    def test_http_no_key_401(self):
        code, r = self._post(self._body(), key=False)
        self.assertEqual(code, 401); self.assertFalse(r["eligible"])

    def test_http_malformed_400(self):
        code, r = self._post(None, raw=b"{broken")
        self.assertEqual(code, 400); self.assertFalse(r["eligible"])

    def test_http_other_account_refused(self):
        code, r = self._post(self._body(target_account="X"))
        self.assertEqual(code, 200); self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "TARGET_ACCOUNT_MISMATCH")

    def test_http_corrupt_store_500_not_eligible(self):
        bad = Path(self.tmp) / "_corrupt_grants.json"; bad.write_text("{not json")
        good = os.environ["PUBLISH_GRANTS_STORE"]; os.environ["PUBLISH_GRANTS_STORE"] = str(bad)
        try:
            code, r = self._post(self._body())
        finally:
            os.environ["PUBLISH_GRANTS_STORE"] = good
        self.assertEqual(code, 500); self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "INTERNAL_ERROR")

    def test_http_production_mode_refuses_test_grant(self):
        os.environ.pop("PUBLISH_ALLOW_TEST_GRANTS")
        try:
            code, r = self._post(self._body())
        finally:
            os.environ["PUBLISH_ALLOW_TEST_GRANTS"] = "1"
        self.assertEqual(code, 200); self.assertFalse(r["eligible"]); self.assertEqual(r["reason"], "TEST_GRANT_NOT_ALLOWED")

    def test_http_real_aki_id_refused(self):
        code, r = self._post(self._body(content_id="aki:post:D01-V01"))
        self.assertFalse(r["eligible"])


if __name__ == "__main__":
    unittest.main()


class PosterCompatibilityTests(unittest.TestCase):
    """Existing poster grants (no target_account, no test_only) behave exactly as before."""

    def setUp(self):
        from unpipe.provisioner import PosterProvisioner
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "a.json"))
        self.grants = str(Path(self.tmp) / "g.json")
        img, cap, self.plat = b"poster-bytes", "Poster caption", "instagram"
        prov = PosterProvisioner(self.store, self.grants)
        self.fp, self.asset, self.pkg = prov.compute_poster_fingerprint("poster_serie_01", img, cap, self.plat, "v1")
        key = prov.grant_key("poster_serie_01", self.plat)
        for g in (GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH):
            self.store.record(key, "poster", g, APPROVE, "nitin", self.fp)
        prov.create_grant("poster_serie_01", img, cap, self.plat, "2030-01-01 12:00:00", "v1", EXP)
        self.epoch = C.scheduled_at_to_epoch("2030-01-01 12:00:00")

    def _eval(self, **extra):
        req = {"content_id": "poster_serie_01", "platform": self.plat, "asset_sha256": self.asset,
               "packaging_sha256": self.pkg, "schedule_version": "v1", "scheduled_at_epoch": self.epoch}
        req.update(extra)
        return PublishApprovalService(self.store, self.grants, now=lambda: self.epoch).evaluate(req)

    def test_legacy_poster_request_unchanged(self):
        self.assertTrue(self._eval()["eligible"])

    def test_poster_grant_has_no_new_fields(self):
        g = json.loads(Path(self.grants).read_text())["grants"]["poster_serie_01::instagram"]
        self.assertNotIn("target_account", g); self.assertNotIn("test_only", g)

    def test_poster_existing_checks_still_refuse_changes(self):
        self.assertFalse(self._eval(asset_sha256="0" * 64)["eligible"])
        self.assertFalse(self._eval(platform="facebook")["eligible"])
        self.assertFalse(self._eval(scheduled_at_epoch=self.epoch + 7200)["eligible"])
