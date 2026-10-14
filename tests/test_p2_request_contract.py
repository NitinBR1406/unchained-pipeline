"""Contract between the Make publisher P2 (scenario 9974134) and /v/publish-eligibility.

The fixture holds P2's request template and upload-route filters exactly as stored in Make (read back via the API).
The test renders that template the way Make would (simple {{1.data.<field>}} substitution) for a SYNTHETIC placement,
sends it to the real approval_server handler on 127.0.0.1 (isolated test mode, temp stores), and then applies P2's own
filter conditions to the answer. Nothing here can match a real AKI placement (test: namespace)."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE
from unpipe.placement_provisioner import PlacementProvisioner
from unpipe import canonical as C

FX = json.loads((Path(__file__).parent / "fixtures" / "p2_gate_contract_20261014.json").read_text())


def render(template, record):
    """Make-style substitution of {{1.data.<field>}} (P2 only references record fields in this body)."""
    out = re.sub(r"\{\{1\.data\.([a-z0-9_]+)\}\}", lambda m: str(record[m.group(1)]), template)
    assert "{{" not in out, out
    return out


def p2_route_opens(filters, record_channel, route_channel, answer):
    """Would P2's stored filter of the `route_channel` upload route pass for a record on `record_channel`?"""
    eligible = "EOK" if answer.get("eligible") is True else "ENO"
    for f in filters:
        vals = {c["a"]: c["b"] for c in f["conditions"][0]}
        if vals.get("{{1.data.channel}}") != route_channel:
            continue
        return (record_channel == route_channel and vals.get("{{60.reason}}") == answer.get("reason")
                and vals.get('{{if(60.eligible = true; "EOK"; "ENO")}}') == eligible)
    return False


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
                          scheduled_at_epoch=C.scheduled_at_to_epoch(p["scheduled_at"]))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for k, v in cls._saved_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def _send(self, record, raw=None):
        body = raw if raw is not None else render(FX["request_template"], record).encode()
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-publish-apikey": self.key})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_template_renders_valid_json_with_all_bound_fields(self):
        body = json.loads(render(FX["request_template"], self.record))
        self.assertEqual(set(body), {"content_id", "platform", "target_account", "asset_sha256", "packaging_sha256",
                                     "schedule_version", "scheduled_at_epoch"})
        self.assertIsInstance(body["scheduled_at_epoch"], int)

    def test_exact_package_opens_only_the_matching_upload_route(self):
        code, raw = self._send(self.record)
        ans = json.loads(raw)                                           # P2 module 60 (Parse JSON)
        self.assertEqual(code, 200); self.assertTrue(ans["eligible"])
        ch = self.record["channel"]
        self.assertTrue(p2_route_opens(FX["upload_route_filters"], ch, "youtube_shorts", ans))
        for other in ("instagram_reels", "instagram_feed", "facebook_reels", "facebook_feed", "youtube_hero"):
            self.assertFalse(p2_route_opens(FX["upload_route_filters"], ch, other, ans))

    def test_each_changed_field_keeps_every_upload_route_closed(self):
        for field, value in (("asset_sha256", "b" * 64), ("packaging_sha256", "c" * 64), ("channel", "instagram_reels"),
                             ("target_account", "OTHER"), ("scheduled_at_epoch", self.record["scheduled_at_epoch"] + 3 * 3600),
                             ("schedule_version", "2"), ("gate_content_id", "aki:post:D01-V01")):
            with self.subTest(field=field):
                code, raw = self._send(dict(self.record, **{field: value}))
                ans = json.loads(raw)
                self.assertFalse(ans["eligible"])
                rec_ch = dict(self.record, **{field: value})["channel"]
                self.assertFalse(any(p2_route_opens(FX["upload_route_filters"], rec_ch, ch, ans)
                                     for ch in ("instagram_reels", "instagram_feed", "facebook_reels", "facebook_feed", "youtube_shorts", "youtube_hero")))

    def test_unreadable_or_error_answers_never_open_a_route(self):
        for ans in ({}, {"eligible": "true", "reason": "VALID_PUBLISH_APPROVAL"}, {"eligible": True, "reason": "OTHER"},
                    {"eligible": False, "reason": "VALID_PUBLISH_APPROVAL"}):
            with self.subTest(ans=ans):
                self.assertFalse(p2_route_opens(FX["upload_route_filters"], "youtube_shorts", "youtube_shorts", ans))


if __name__ == "__main__":
    unittest.main()
