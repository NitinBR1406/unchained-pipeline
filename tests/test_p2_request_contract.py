"""Contract between the Make publisher P2 (scenario 9974134, version f2) and /v/publish-eligibility.

The fixture holds, per channel route, P2's gate request template, the pre-gate hash filter, the upload filter and the
BLOCKED filters exactly as stored in Make (read back via the API). Since f2 the gate decision sits on the ownership read
just before the upload (upload_filter) and Instagram only fetches a URL that matches the hosting register
(fetch_filter / blocked_hosting_filter; private bucket configured since 2026-10-15, name redacted as __IG_BUCKET__). P2 hashes the bytes it fetched and sends
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
        x = re.sub(r"\{\{ifempty\((\d+\.expires_epoch); 0\)\}\}", lambda m: str(env.get(m.group(1), "") or 0), x)
        return x
    a, b, o = val(c["a"]), val(c.get("b")), c["o"]
    assert "{{" not in a + b, (a, b)   # an unsubstituted expression would make the case vacuous
    num = lambda x: float(x) if re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", x) else float("nan")
    return {"text:equal": lambda: a == b, "text:notequal": lambda: a != b, "text:contain": lambda: b in a,
            "text:notcontain": lambda: b not in a, "text:startwith": lambda: a.startswith(b),
            "text:notstartwith": lambda: not a.startswith(b), "text:pattern": lambda: re.search(b, a) is not None,
            "text:notpattern": lambda: re.search(b, a) is None, "number:greater": lambda: num(a) > num(b),
            "number:lessorequal": lambda: num(a) <= num(b)}[o]()


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

    def test_empty_registered_hash_never_reaches_the_gate(self):
        for r in FX["routes"]:
            env = env_for(r, dict(self.record, asset_sha256="", media_url="https://x.invalid/a?generation=1"), "", meta="")
            self.assertFalse(filter_true(r["gate_prefilter"], env), r["channel"])
            self.assertTrue(filter_true(r["blocked_hash_filter"], env), r["channel"])

    def test_drive_metadata_must_agree_too(self):
        env = env_for(self.route, self.record, self.computed, meta="")
        self.assertFalse(filter_true(self.route["gate_prefilter"], env))
        self.assertTrue(filter_true(self.route["blocked_hash_filter"], env))

    def test_instagram_fetch_requires_registered_signed_object_version(self):
        NOW = 1_800_000_000
        BUCKET = "aki-contract-test-bucket"

        def with_bucket(f, name):
            """The stored filter with its (redacted) configured bucket set to `name`; 'UNCONFIGURED' = hosting switched off."""
            return json.loads(json.dumps(f).replace("__IG_BUCKET__", name))

        for ch, ext in (("instagram_reels", "mp4"), ("instagram_feed", "jpg")):
            r = ROUTES[ch]; reg_id = r["register_id"]
            self.assertEqual(r["register_source"], '{{ifempty(1.data.hosting_register; "NO_REGISTER")}}')
            obj = "aki-ig-staging/%s.%s" % (self.computed, ext)
            register = dict(bucket=BUCKET, object=obj, generation="1712345678901234", sha256=self.computed, expires_epoch=NOW + 3600)
            sig = "X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=sa%2F20261014%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20261014T120000Z&X-Goog-Expires=3600&X-Goog-SignedHeaders=host&X-Goog-Signature=" + "ab" * 128
            good = "https://storage.googleapis.com/%s/%s?generation=1712345678901234&%s" % (BUCKET, obj, sig)

            def env(url, **reg):
                e = {"1.data.%s" % k: v for k, v in dict(self.record, channel=ch, media_url=url).items()}
                e.update({"%d.%s" % (reg_id, k): v for k, v in dict(register, **reg).items()})
                e['formatDate(addMinutes(now; 15); "X")'] = NOW + 900
                return e

            self.assertIn("__IG_BUCKET__", json.dumps(r["fetch_filter"]))        # stored P2 has a configured private bucket
            # hosting switched off (UNCONFIGURED) -> every URL, even a perfect one, is BLOCKED before any fetch
            self.assertFalse(filter_true(with_bucket(r["fetch_filter"], "UNCONFIGURED"), env(good)), ch)
            self.assertTrue(filter_true(with_bucket(r["blocked_hosting_filter"], "UNCONFIGURED"), env(good)), ch)
            # a perfect URL for ANOTHER bucket than the configured one is BLOCKED
            self.assertFalse(filter_true(with_bucket(r["fetch_filter"], "other-bucket"), env(good)), ch)
            fetch, blocked = with_bucket(r["fetch_filter"], BUCKET), with_bucket(r["blocked_hosting_filter"], BUCKET)
            cases = [(good, {}, True),
                     (good.split("?")[0], {}, False),                                                  # unsigned, no generation
                     (good.replace("storage.googleapis.com", "evil.example"), {}, False),              # other host
                     (good.replace("/%s/" % BUCKET, "/other-bucket/"), {}, False),                    # other bucket
                     (good.replace(self.computed, "0" * 64), {}, False),                               # other object
                     (good, dict(generation="999"), False),                                            # other object version
                     (good.replace("generation=1712345678901234", "generation=1712345678901234&generation=2"), {}, False),
                     (good.replace("generation=1712345678901234", "generation="), {}, False),        # empty generation
                     (good + "#frag", {}, False),                                                       # fragment
                     (good.replace("X-Goog-Credential=", "X-Goog-Cred="), {}, False),                 # no credential
                     (good.replace("X-Goog-Expires=3600&", ""), {}, False),                            # no expiry param
                     (good.replace("GOOG4-RSA-SHA256", "GOOG4-HMAC-SHA256"), {}, False),              # other algorithm
                     (good.replace("X-Goog-Signature=", "X-Goog-Sig="), {}, False),                   # not signed
                     (good, dict(expires_epoch=NOW + 60), False),                                      # signed URL about to expire
                     (good, dict(sha256="1" * 64), False),                                             # register for other bytes
                     (good.replace("&X-Goog-Date", "&x=a@evil.example&X-Goog-Date"), {}, False),      # "@" only
                     (good, dict(expires_epoch=""), False)]                                            # register without expiry
            for url, reg, expect in cases:
                with self.subTest(ch=ch, url=url[:90], reg=reg):
                    self.assertEqual(filter_true(fetch, env(url, **reg)), expect)
                    self.assertEqual(filter_true(blocked, env(url, **reg)), not expect)   # exactly one route fires

    def test_upload_only_while_this_run_still_owns_the_claim(self):
        for r in FX["routes"]:
            fence = r["ownership_filter"]["conditions"][0]
            self.assertEqual({(c["a"].split(".")[-1].rstrip("}"), c["o"]) for c in fence},
                             {("claim_token", "text:equal"), ("status", "text:equal"), ("attempt_count", "number:equal")}, r["channel"])
            self.assertTrue(all(c["a"].startswith("{{%d." % r["upload_fence_id"]) for c in fence), r["channel"])

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
