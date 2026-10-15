"""TikTok post settings (creator's per-post privacy / interactions / consent) bound to the publish grant.

Synthetic test grants only ("test:" namespace, isolated temp stores, local HTTP on 127.0.0.1)."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE
from unpipe.placement_provisioner import PlacementProvisioner
from unpipe.publish_approval import PublishApprovalService
from unpipe.tiktok_settings import TikTokSettingsService, TikTokSettingsError, settings_for_response
from unpipe import canonical as C

SECRET = "test-signing-secret"
CID, PLAT, SHA = "test:post:T01-V01", "tiktok", "a" * 64
TITLE, CAPTION, SCHED, SV = "", "Synthetic <b>caption</b> & \"quotes\"", "2026-10-19 18:00:00", "1"
OPTS = ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]


def make_grant(tmp, platform=PLAT, cid=CID, revoke=False):
    store = ApprovalStore(str(Path(tmp) / "a.json"))
    grants = str(Path(tmp) / "g.json")
    fp, pkg = PlacementProvisioner.fingerprint(cid, SHA, platform, TITLE, CAPTION, SV)
    for g in (GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH):
        store.record(PlacementProvisioner.grant_key(cid, platform), "synthetic", g, APPROVE, "test-harness", fp)
    prov = PlacementProvisioner(store, grants)
    prov.create_grant(cid, SHA, platform, "@unchainednitin", TITLE, CAPTION, SCHED, SV, int(time.time()) + 86400, test_only=True)
    if revoke:
        prov.revoke_grant(cid, platform)
    return store, grants, pkg


def gate_req(pkg, platform=PLAT, cid=CID):
    return {"content_id": cid, "platform": platform, "target_account": "@unchainednitin", "asset_sha256": SHA,
            "packaging_sha256": pkg, "schedule_version": SV, "scheduled_at_epoch": C.scheduled_at_to_epoch(SCHED)}


class SettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store, self.grants, self.pkg = make_grant(self.tmp)
        self.svc = TikTokSettingsService(SECRET, ["nitin"], self.grants, str(Path(self.tmp) / "c.json"))
        self.tok = self.svc.create_request(CID, PLAT, CAPTION, OPTS, creator_nickname="unchainednitin")

    def grant(self):
        return json.loads(Path(self.grants).read_text())["grants"]["%s::%s" % (CID, PLAT)]

    def test_link_only_for_tiktok_and_only_known_creator_info_options(self):
        with self.assertRaises(TikTokSettingsError):
            self.svc.create_request(CID, "instagram_reels", CAPTION, OPTS)
        with self.assertRaises(TikTokSettingsError):
            self.svc.create_request(CID, PLAT, CAPTION, ["EVERYONE_ELSE"])
        self.assertEqual(self.svc.render_request(self.tok)["privacy_options"], OPTS)

    def test_refusals(self):
        ok = {"privacy_level": "SELF_ONLY", "consent": "yes"}
        cases = [({"consent": "yes"}, "no default"), ({"privacy_level": "FOLLOWER_OF_CREATOR", "consent": "yes"}, "not offered"),
                 ({"privacy_level": "SELF_ONLY"}, "consent")]
        for form, why in cases:
            with self.subTest(why=why), self.assertRaises(TikTokSettingsError):
                self.svc.decide(self.tok, form, "nitin")
        with self.assertRaises(TikTokSettingsError):
            self.svc.decide(self.tok, ok, "someone-else")
        with self.assertRaises(TikTokSettingsError):
            self.svc.decide(self.tok[:-2] + "00", ok, "nitin")
        expired = TikTokSettingsService(SECRET, ["nitin"], self.grants, str(Path(self.tmp) / "c2.json"), now=lambda: int(time.time()) + 999999)
        with self.assertRaises(TikTokSettingsError):
            expired.decide(self.tok, ok, "nitin")
        self.assertNotIn("tiktok_settings", self.grant())          # nothing stored by any refusal

    def test_no_grant_or_revoked_grant_is_refused(self):
        tmp = tempfile.mkdtemp()
        _, grants, _ = make_grant(tmp, revoke=True)
        svc = TikTokSettingsService(SECRET, ["nitin"], grants, str(Path(tmp) / "c.json"))
        with self.assertRaises(TikTokSettingsError):
            svc.decide(svc.create_request(CID, PLAT, CAPTION, OPTS), {"privacy_level": "SELF_ONLY", "consent": "yes"}, "nitin")
        with self.assertRaises(TikTokSettingsError):
            svc.decide(svc.create_request("test:post:NOPE", PLAT, CAPTION, OPTS), {"privacy_level": "SELF_ONLY", "consent": "yes"}, "nitin")

    def test_saved_on_grant_interactions_off_by_default_and_single_use(self):
        st = self.svc.decide(self.tok, {"privacy_level": "PUBLIC_TO_EVERYONE", "consent": "yes"}, "nitin")
        self.assertEqual((st["privacy_level"], st["allow_comment"], st["allow_duet"], st["allow_stitch"]),
                         ("PUBLIC_TO_EVERYONE", False, False, False))
        self.assertEqual(self.grant()["tiktok_settings"]["grant_fingerprint"], self.grant()["fingerprint"])
        again = self.svc.decide(self.tok, {"privacy_level": "SELF_ONLY", "consent": "yes", "allow_comment": "on"}, "nitin")
        self.assertTrue(again["idempotent_replay"])
        self.assertEqual(self.grant()["tiktok_settings"]["privacy_level"], "PUBLIC_TO_EVERYONE")   # replay changes nothing

    def test_concurrent_use_of_one_link_stores_exactly_one_choice(self):
        out, errs = [], []
        def go(level):
            try: out.append(self.svc.decide(self.tok, {"privacy_level": level, "consent": "yes"}, "nitin"))
            except Exception as e: errs.append(e)
        ts = [threading.Thread(target=go, args=(OPTS[i % 2],)) for i in range(12)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(sum(1 for r in out if not r.get("idempotent_replay")), 1)       # one winner, the rest replays
        winner = next(r for r in out if not r.get("idempotent_replay"))["privacy_level"]
        self.assertEqual(self.grant()["tiktok_settings"]["privacy_level"], winner)
        self.assertTrue(all(r["privacy_level"] == winner for r in out))

    def test_revoke_and_choice_never_lose_the_revoke(self):
        for _ in range(5):
            tmp = tempfile.mkdtemp()
            store, grants, _ = make_grant(tmp)
            svc = TikTokSettingsService(SECRET, ["nitin"], grants, str(Path(tmp) / "c.json"))
            tok = svc.create_request(CID, PLAT, CAPTION, OPTS)
            prov = PlacementProvisioner(store, grants)
            t1 = threading.Thread(target=lambda: prov.revoke_grant(CID, PLAT))
            def choose():
                try: svc.decide(tok, {"privacy_level": "SELF_ONLY", "consent": "yes"}, "nitin")
                except TikTokSettingsError: pass
            t2 = threading.Thread(target=choose)
            t2.start(); t1.start(); t1.join(); t2.join()
            self.assertTrue(json.loads(Path(grants).read_text())["grants"]["%s::%s" % (CID, PLAT)]["revoked"])

    def test_only_https_preview_and_malformed_tokens_refused(self):
        with self.assertRaises(TikTokSettingsError):
            self.svc.create_request(CID, PLAT, CAPTION, OPTS, preview_url="javascript:alert(1)")
        import base64, hashlib, hmac as H
        pb = base64.urlsafe_b64encode(json.dumps({"gate": "tiktok_settings", "content_id": CID}).encode()).decode().rstrip("=")
        forged = pb + "." + H.new(SECRET.encode(), pb.encode(), hashlib.sha256).hexdigest()     # signed but no exp/nonce
        with self.assertRaises(TikTokSettingsError):
            self.svc.render_request(forged)

    def test_gate_returns_choice_only_when_eligible_and_bound(self):
        verifier = lambda: PublishApprovalService(self.store, self.grants, allow_test_grants=True)
        self.assertNotIn("tiktok", verifier().evaluate(gate_req(self.pkg)))      # not chosen yet
        self.svc.decide(self.tok, {"privacy_level": "SELF_ONLY", "consent": "yes", "allow_comment": "on"}, "nitin")
        res = verifier().evaluate(gate_req(self.pkg))
        self.assertTrue(res["eligible"])
        self.assertEqual(res["tiktok"], {"privacy_level": "SELF_ONLY", "disable_comment": False, "disable_duet": True, "disable_stitch": True})
        bad = verifier().evaluate(dict(gate_req(self.pkg), asset_sha256="b" * 64))
        self.assertFalse(bad["eligible"]); self.assertNotIn("tiktok", bad)        # never on a blocked answer
        g = self.grant(); g["fingerprint"] = "other"
        self.assertIsNone(settings_for_response(g, PLAT))                       # stale choice after a new grant
        self.assertIsNone(settings_for_response(self.grant(), "instagram_reels"))


class SettingsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.store, cls.grants, cls.pkg = make_grant(cls.tmp)
        cls._saved = {k: os.environ.get(k) for k in ("APPROVAL_SIGNING_SECRET", "PUBLISH_ELIGIBILITY_APIKEY", "PUBLISH_GRANTS_STORE",
                                                     "TIKTOK_SETTINGS_CONSUMED_STORE", "APPROVERS")}
        os.environ.update(APPROVAL_SIGNING_SECRET=SECRET, PUBLISH_ELIGIBILITY_APIKEY="k", PUBLISH_GRANTS_STORE=cls.grants,
                          TIKTOK_SETTINGS_CONSUMED_STORE=str(Path(cls.tmp) / "c.json"), APPROVERS="nitin")
        import approval_server
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), approval_server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for k, v in cls._saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def call(self, path, data=None, headers=None, form=False):
        body = None if data is None else (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
        req = urllib.request.Request(self.base + path, data=body, headers=headers or {}, method="POST" if body else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def test_link_page_and_save(self):
        req = {"content_id": CID, "platform": PLAT, "caption": CAPTION, "privacy_options": OPTS, "creator_nickname": "unchainednitin"}
        self.assertEqual(self.call("/v/tiktok-link", req)[0], 401)                       # unauthenticated
        code, body = self.call("/v/tiktok-link", req, {"x-publish-apikey": "k"})
        self.assertEqual(code, 200)
        path = json.loads(body)["path"]
        code, page = self.call(path + "&approver=nitin")
        self.assertEqual(code, 200)
        self.assertNotIn("<b>caption</b>", page); self.assertIn("&lt;b&gt;caption&lt;/b&gt;", page)   # escaped
        self.assertEqual(len(re.findall(r"type=radio name=privacy_level", page)), 2)
        self.assertNotIn("checked", page)                                                   # no default anywhere
        self.assertIn("Music Usage Confirmation", page)
        req2 = urllib.request.Request(self.base + path)
        with urllib.request.urlopen(req2, timeout=5) as r:
            self.assertIn("default-src 'none'", r.headers.get("Content-Security-Policy", ""))
        token = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)["token"][0]
        self.assertEqual(self.call("/v/tiktok", {"token": token, "approver": "nitin", "privacy_level": "SELF_ONLY"}, form=True)[0], 400)
        code, _ = self.call("/v/tiktok", {"token": token, "approver": "nitin", "privacy_level": "SELF_ONLY", "consent": "yes"}, form=True)
        self.assertEqual(code, 200)
        g = json.loads(Path(self.grants).read_text())["grants"]["%s::%s" % (CID, PLAT)]
        self.assertEqual(g["tiktok_settings"]["privacy_level"], "SELF_ONLY")


if __name__ == "__main__":
    unittest.main()
