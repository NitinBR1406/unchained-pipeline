"""Contract between the Make publisher P2 (scenario 9974134, version e) and /v/publish-eligibility.

The fixture holds, per channel route, P2's gate request template, the pre-gate hash filter, the upload filter and the
BLOCKED filters exactly as stored in Make (read back via the API). P2 version e hashes the bytes it fetched and sends
THAT hash ({{<n>.bytes_sha256}}) to the gate. The test computes the hash over a synthetic file, renders the template
the way Make would, sends it to the real approval_server handler on 127.0.0.1 (isolated test mode, temp stores) and then
applies P2's own filter conditions to the answer. Nothing here can match a real AKI placement (test: namespace)."""
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE
from unpipe.placement_provisioner import PlacementProvisioner
from unpipe import canonical as C

FX = json.loads((Path(__file__).parent / "fixtures" / "p2_gate_contract_20261014.json").read_text())
ROUTES = {r["channel"]: r for r in FX["routes"]}


def render(template, record, hash_var_ref, computed):
    """Make-style substitution: {{1.data.<field>}} from the record, {{<n>.bytes_sha256}} = hash of the fetched bytes."""
    out = template.replace("{{%s}}" % hash_var_ref, computed)
    out = re.sub(r"\{\{1\.data\.([a-z0-9_]+)\}\}", lambda m: str(record[m.group(1)]), out)
    assert "{{" not in out, out
    return out


def cond_true(c, env):
    def val(x):
        x = x or ""
        for k, v in env.items():
            x = x.replace("{{%s}}" % k, str(v))
        return x
    a, b, o = val(c["a"]), val(c.get("b")), c["o"]
    return {"text:equal": a == b, "text:notequal": a != b, "text:contain": b in a, "text:notcontain": b not in a}[o]


def filter_true(f, env):
    return any(all(cond_true(c, env) for c in group) for group in f["conditions"])


def env_for(route, record, computed, meta=None, answer=None):
    env = {"1.data.%s" % k: v for k, v in record.items()}
    env["%d.bytes_sha256" % (route["fetch_id"] + 1)] = computed
    env["%d.sha256Checksum" % route["fetch_id"]] = meta if meta is not None else ""
    env['ifempty(%d.sha256Checksum; "NONE")' % route["fetch_id"]] = meta or "NONE"
    if answer is not None:
        p = route["parse_id"]
        env["%d.reason" % p] = answer.get("reason", "")
        env['if(%d.eligible = true; "EOK"; "ENO")' % p] = "EOK" if answer.get("eligible") is True else "ENO"
    return env


class P2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.key = "local-contract-test-key"
        cls._saved_env = {k: os.environ.get(k) for k in ("PUBLISH_ELIGIBILITY_APIKEY", "PUBLISH_ALLOW_TEST_GRANTS", "PUBLISH_APPROVALS_STORE", "PUBLISH_GRANTS_STORE")}
        os.environ.update(PUBLISH_ELIGIBILITY_APIKEY=cls.key, PUBLISH_ALLOW_TEST_GRANTS="1",
                          PUBLISH_APPROVALS_STORE=str(Path(cls.tmp) / "a.json"), PUBLISH_GRANTS_STORE=str(Path(cls.tmp) / "g.json"))
        import approval_server
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), approval_server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/v/publish-eligibility" % cls.srv.server_address[1]
        p = FX["synthetic_placement"]
        cls.bytes = (ROOT / p["media_file"]).read_bytes()
        cls.computed = hashlib.sha256(cls.bytes).hexdigest()
        assert cls.computed == p["asset_sha256"]
        fp, pkg = PlacementProvisioner.fingerprint(p["gate_content_id"], p["asset_sha256"], p["channel"], p["title"], p["caption"], p["schedule_version"])
        store = ApprovalStore(os.environ["PUBLISH_APPROVALS_STORE"])
        for g in (GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH):
            store.record(PlacementProvisioner.grant_key(p["gate_content_id"], p["channel"]), "synthetic", g, APPROVE, "test-harness", fp)
        PlacementProvisioner(store, os.environ["PUBLISH_GRANTS_STORE"]).create_grant(
            p["gate_content_id"], p["asset_sha256"], p["channel"], p["target_account"], p["title"], p["caption"],
            p["scheduled_at"], p["schedule_version"], 1999999999, test_only=True)
        # the record exactly as P2 reads it from the data store
        cls.record = dict(gate_content_id=p["gate_content_id"], channel=p["channel"], target_account=p["target_account"],
                          asset_sha256=p["asset_sha256"], packaging_sha256=pkg, schedule_version=p["schedule_version"],
                          scheduled_at_epoch=C.scheduled_at_to_epoch(p["scheduled_at"]), format_variant=p["format_variant"], media_url="")
        cls.route = ROUTES[p["channel"]]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for k, v in cls._saved_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def _send(self, record, computed):
        r = self.route
        body = render(r["request_template"], record, "%d.bytes_sha256" % (r["fetch_id"] + 1), computed).encode()
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-publish-apikey": self.key})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_fixture_is_p2_version_e(self):
        self.assertEqual(sorted(ROUTES), sorted(["instagram_reels", "instagram_feed", "facebook_reels", "facebook_feed", "youtube_shorts", "youtube_hero"]))
        for r in FX["routes"]:
            hv = "%d.bytes_sha256" % (r["fetch_id"] + 1)
            self.assertIn('"asset_sha256":"{{%s}}"' % hv, r["request_template"], r["channel"])   # gate gets the COMPUTED hash
            self.assertEqual(r["hash_variable"]["value"], "{{sha256(%d.data)}}" % r["fetch_id"])
            self.assertNotIn("downloaded bytes", json.dumps(r))

    def test_template_renders_valid_json_with_all_bound_fields(self):
        r = self.route
        body = json.loads(render(r["request_template"], self.record, "%d.bytes_sha256" % (r["fetch_id"] + 1), self.computed))
        self.assertEqual(set(body), {"content_id", "platform", "target_account", "asset_sha256", "packaging_sha256",
                                     "schedule_version", "scheduled_at_epoch"})
        self.assertEqual(body["asset_sha256"], self.computed)
        self.assertIsInstance(body["scheduled_at_epoch"], int)

    def test_exact_bytes_call_gate_and_open_only_the_matching_upload(self):
        env = env_for(self.route, self.record, self.computed, meta=self.computed)
        self.assertTrue(filter_true(self.route["gate_prefilter"], env))
        self.assertFalse(filter_true(self.route["blocked_hash_filter"], env))
        code, ans = self._send(self.record, self.computed)
        self.assertEqual(code, 200); self.assertTrue(ans["eligible"])
        self.assertTrue(filter_true(self.route["upload_filter"], env_for(self.route, self.record, self.computed, self.computed, ans)))
        self.assertFalse(filter_true(self.route["blocked_gate_filter"], env_for(self.route, self.record, self.computed, self.computed, ans)))

    def test_changed_bytes_never_reach_the_gate_or_upload(self):
        changed = bytearray(self.bytes); changed[0] ^= 1
        h = hashlib.sha256(bytes(changed)).hexdigest()
        for meta in (h, self.computed, None):
            env = env_for(self.route, self.record, h, meta=meta)
            self.assertFalse(filter_true(self.route["gate_prefilter"], env))
            self.assertTrue(filter_true(self.route["blocked_hash_filter"], env))
        # even if the record were re-pointed to the changed file, the gate refuses (approval bound to the old bytes)
        code, ans = self._send(dict(self.record, asset_sha256=h), h)
        self.assertFalse(ans["eligible"])

    def test_drive_metadata_must_agree_too(self):
        env = env_for(self.route, self.record, self.computed, meta="")
        self.assertFalse(filter_true(self.route["gate_prefilter"], env))
        self.assertTrue(filter_true(self.route["blocked_hash_filter"], env))

    def test_instagram_requires_pinned_content_addressed_url(self):
        r = ROUTES["instagram_reels"]
        rec = dict(self.record, channel="instagram_reels")
        good = "https://storage.example.invalid/aki/%s.mp4?generation=7" % self.computed
        for url, expect in ((good, True), (good.split("?")[0], False), ("https://storage.example.invalid/aki/x.mp4?generation=7", False)):
            env = env_for(r, dict(rec, media_url=url), self.computed)
            self.assertEqual(filter_true(r["gate_prefilter"], env), expect, url)
            self.assertEqual(filter_true(r["blocked_hash_filter"], env), not expect, url)

    def test_each_changed_field_is_refused_by_the_gate(self):
        for field, value in (("packaging_sha256", "c" * 64), ("channel", "instagram_reels"), ("target_account", "OTHER"),
                             ("scheduled_at_epoch", self.record["scheduled_at_epoch"] + 3 * 3600), ("schedule_version", "2"),
                             ("gate_content_id", "aki:post:D01-V01")):
            with self.subTest(field=field):
                code, ans = self._send(dict(self.record, **{field: value}), self.computed)
                self.assertFalse(ans["eligible"])
                self.assertFalse(filter_true(self.route["upload_filter"], env_for(self.route, self.record, self.computed, self.computed, ans)))

    def test_unreadable_or_error_answers_never_open_an_upload(self):
        for ans in ({}, {"eligible": "true", "reason": "VALID_PUBLISH_APPROVAL"}, {"eligible": True, "reason": "OTHER"},
                    {"eligible": False, "reason": "VALID_PUBLISH_APPROVAL"}):
            with self.subTest(ans=ans):
                for r in FX["routes"]:
                    env = env_for(r, self.record, self.computed, self.computed, ans)
                    self.assertFalse(filter_true(r["upload_filter"], env))
                    self.assertTrue(filter_true(r["blocked_gate_filter"], env))


if __name__ == "__main__":
    unittest.main()
