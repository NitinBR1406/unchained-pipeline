"""Security + reliability tests for the Visualizer approval verifier (server side).

Covers verifier-owned controls AND the /v/decision reliability patch (Make 2xx/409/timeout/5xx/4xx
handling, nonce-consume-after-success, idempotency, publish separation). No network: the Make poster
is injected. Uses a TEST secret only; never the real APPROVAL_SIGNING_SECRET.
"""
import io
import os
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.visualizer_approval import VisualizerApprovalService, VisualizerApprovalError

SECRET = "TEST_SECRET_NOT_THE_REAL_ONE"


class FakePoster:
    """Simulates the Make POST. Returns (status, body); or raises raise_exc for network failures."""
    def __init__(self, status=200, body="VISUALIZER_APPROVED", raise_exc=None):
        self.status = status
        self.body = body
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, url, payload, apikey):
        self.calls.append({"url": url, "payload": payload, "apikey": apikey})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.status, self.body


def svc(tmp, poster=None):
    return VisualizerApprovalService(
        signing_secret=SECRET, approvers=["nitin"],
        consumed_path=str(Path(tmp) / "_vis_consumed.json"),
        make_webhook_url="https://make.example/hook", make_apikey="APIKEY_TEST",
        poster=poster or FakePoster())


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    # ---- original security tests -------------------------------------------------
    def test_1_valid_signed_request_accepted_and_forwarded(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        r = s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["forwarded_to_make"])
        self.assertEqual(len(p.calls), 1)
        self.assertEqual(p.calls[0]["apikey"], "APIKEY_TEST")
        self.assertEqual(p.calls[0]["payload"]["content_id"], "hua-main")
        self.assertIn("ts", p.calls[0]["payload"])
        self.assertIsInstance(p.calls[0]["payload"]["ts"], int)
        self.assertTrue(p.calls[0]["payload"]["nonce"])
        self.assertFalse(r["creates_publish_approval"])
        self.assertFalse(r["sets_scheduled"])

    def test_2_invalid_signature_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        pb, sig = tok.split(".", 1)
        with self.assertRaises(VisualizerApprovalError):
            s.decide(pb + "." + ("0" * len(sig)), "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 0)

    def test_3_expired_request_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main", ttl=-1)
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 0)

    def test_4_replayed_nonce_idempotent_not_double_forwarded(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        s.decide(tok, "APPROVE", "nitin")
        r2 = s.decide(tok, "APPROVE", "nitin")
        self.assertTrue(r2.get("idempotent_replay"))
        self.assertEqual(len(p.calls), 1)

    def test_5_unauthorized_approver_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "someone_else")
        self.assertEqual(len(p.calls), 0)

    def test_6_reject_decision_records_without_forward(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        r = s.decide(tok, "REJECT", "nitin")
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(len(p.calls), 0)

    def test_7_persistence_of_consumed_nonce_across_instances(self):
        s = svc(self.tmp, FakePoster(200))
        tok = s.create_request("hua-main", "Hua Main")
        s.decide(tok, "APPROVE", "nitin")
        s2 = svc(self.tmp, FakePoster(200))            # new instance, same store (simulated restart)
        r = s2.decide(tok, "APPROVE", "nitin")
        self.assertTrue(r.get("idempotent_replay"))

    # ---- new reliability regression tests (502 fix) -----------------------------
    def test_r1_make_200_deterministic_success(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        r = s.decide(s.create_request("c1", "t"), "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertFalse(r["idempotent_replay"])
        self.assertFalse(r["creates_publish_approval"])
        self.assertFalse(r["sets_scheduled"])

    def test_r2_make_200_nonce_consumed_once(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("c2", "t")
        s.decide(tok, "APPROVE", "nitin")
        r2 = s.decide(tok, "APPROVE", "nitin")         # same token again
        self.assertTrue(r2.get("idempotent_replay"))
        self.assertEqual(len(p.calls), 1)              # forwarded exactly once

    def test_r3_make_409_replay_is_idempotent_success(self):
        p = FakePoster(409, "nonce already consumed (replay)"); s = svc(self.tmp, p)
        r = s.decide(s.create_request("c3", "t"), "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["idempotent_replay"])
        self.assertEqual(r["make_status"], 409)
        self.assertFalse(r["creates_publish_approval"])
        self.assertFalse(r["sets_scheduled"])

    def test_r4_409_no_second_mutation_single_forward(self):
        p = FakePoster(409, "nonce already consumed (replay)"); s = svc(self.tmp, p)
        s.decide(s.create_request("c4", "t"), "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 1)              # one forward; Make owns the dedupe

    def test_r5_timeout_fails_and_nonce_not_consumed(self):
        p = FakePoster(raise_exc=TimeoutError("timed out")); s = svc(self.tmp, p)
        tok = s.create_request("c5", "t")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        # nonce NOT consumed -> a later successful retry approves
        s._poster = FakePoster(200)
        r = s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertFalse(r["idempotent_replay"])

    def test_r6_urlerror_fails_and_nonce_not_consumed(self):
        p = FakePoster(raise_exc=urllib.error.URLError("conn reset")); s = svc(self.tmp, p)
        tok = s.create_request("c6", "t")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        s._poster = FakePoster(200)
        self.assertEqual(s.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_r7_make_500_fails_and_nonce_not_consumed(self):
        p = FakePoster(500, "server error"); s = svc(self.tmp, p)
        tok = s.create_request("c7", "t")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        s._poster = FakePoster(200)
        self.assertEqual(s.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_r8_unrelated_4xx_not_false_success(self):
        # 403, and a 409 WITHOUT the replay/nonce body, must NOT become success and must NOT consume.
        for st, bd in ((403, "forbidden"), (409, "some unrelated conflict")):
            p = FakePoster(st, bd); s = svc(self.tmp, p)
            tok = s.create_request("c8", "t")
            with self.assertRaises(VisualizerApprovalError):
                s.decide(tok, "APPROVE", "nitin")
            s._poster = FakePoster(200)                 # nonce not consumed -> retry works
            self.assertEqual(s.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_r9_duplicate_same_token_one_effective_mutation(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("c9", "t")
        s.decide(tok, "APPROVE", "nitin")
        s.decide(tok, "APPROVE", "nitin")
        s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 1)              # only one forward reaches Make

    def test_r10_publish_and_scheduled_never_set(self):
        for poster in (FakePoster(200), FakePoster(409, "nonce already consumed (replay)")):
            s = svc(self.tmp, poster)
            r = s.decide(s.create_request("c10-" + str(poster.status), "t"), "APPROVE", "nitin")
            self.assertFalse(r["creates_publish_approval"])
            self.assertFalse(r["sets_scheduled"])
            self.assertEqual(r["status"], "VISUALIZER_APPROVED")

    # ---- urllib HTTPError behaviour (the proven live root cause) -----------------
    def _http_error(self, code, body=""):
        return urllib.error.HTTPError("https://make.example/hook", code, "err", {}, io.BytesIO(body.encode()))

    def test_u1_raised_httperror_409_replay_does_not_escape(self):
        # poster RAISES urllib HTTPError(409) (exactly what urlopen does) -> handled, not escaped.
        raising = FakePoster(raise_exc=self._http_error(409, "nonce already consumed (replay)"))
        s = svc(self.tmp, raising)
        r = s.decide(s.create_request("u1", "t"), "APPROVE", "nitin")   # must NOT raise
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["idempotent_replay"])
        self.assertEqual(r["make_status"], 409)

    def test_u2_raised_httperror_409_unrelated_fails(self):
        s = svc(self.tmp, FakePoster(raise_exc=self._http_error(409, "some unrelated conflict")))
        tok = s.create_request("u2", "t")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        s._poster = FakePoster(200)                                     # nonce not consumed -> retry ok
        self.assertEqual(s.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_u3_raised_httperror_400_fails(self):
        s = svc(self.tmp, FakePoster(raise_exc=self._http_error(400, "bad")))
        with self.assertRaises(VisualizerApprovalError):
            s.decide(s.create_request("u3", "t"), "APPROVE", "nitin")

    def test_u4_raised_httperror_500_fails(self):
        s = svc(self.tmp, FakePoster(raise_exc=self._http_error(500, "boom")))
        with self.assertRaises(VisualizerApprovalError):
            s.decide(s.create_request("u4", "t"), "APPROVE", "nitin")

    def test_u5_http_post_json_converts_httperror_to_tuple(self):
        # Directly reproduce urllib: urlopen raises HTTPError(409) -> _http_post_json returns (409, body).
        import unpipe.visualizer_approval as va
        orig = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(
            self._http_error(409, "nonce already consumed (replay)"))
        try:
            code, body = va._http_post_json("https://make.example/hook", {"x": 1}, "APIKEY_TEST")
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(code, 409)
        self.assertIn("replay", body.lower())

    # ---- STRICT 409 contract (exact body == "nonce already consumed (replay)") -----
    EXACT = "nonce already consumed (replay)"

    def _decide_409(self, body, key):
        s = svc(self.tmp, FakePoster(409, body))
        return s, s.create_request(key, "t")

    def test_s1_exact_body_is_idempotent_success(self):
        s = svc(self.tmp, FakePoster(409, self.EXACT))
        r = s.decide(s.create_request("s1", "t"), "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["idempotent_replay"])
        self.assertFalse(r["creates_publish_approval"])
        self.assertFalse(r["sets_scheduled"])

    def test_s2_whitespace_around_exact_body_success(self):
        s = svc(self.tmp, FakePoster(409, "  nonce already consumed (replay)\n"))
        r = s.decide(s.create_request("s2", "t"), "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["idempotent_replay"])

    def test_s3_invalid_nonce_body_fails(self):
        s, tok = self._decide_409("invalid nonce", "s3")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        s._poster = FakePoster(200)                          # not consumed -> retry approves
        self.assertEqual(s.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_s4_replay_nonce_words_only_fails(self):
        s, tok = self._decide_409("replay nonce", "s4")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s5_html_containing_nonce_fails(self):
        s, tok = self._decide_409("<html><body>error: nonce conflict</body></html>", "s5")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s6_empty_409_body_fails(self):
        s, tok = self._decide_409("", "s6")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s7_exact_plus_extra_text_fails(self):
        s, tok = self._decide_409("nonce already consumed (replay) EXTRA", "s7")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s8_case_altered_fails(self):
        s, tok = self._decide_409("Nonce already consumed (replay)", "s8")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s9_unrelated_409_fails(self):
        s, tok = self._decide_409("some unrelated conflict", "s9")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")

    def test_s10_raised_httperror_409_exact_success_wrong_fails(self):
        # HTTPError(409) exact body -> success
        s = svc(self.tmp, FakePoster(raise_exc=self._http_error(409, self.EXACT)))
        r = s.decide(s.create_request("s10a", "t"), "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["idempotent_replay"])
        # HTTPError(409) wrong body -> failure, nonce not consumed
        s2 = svc(self.tmp, FakePoster(raise_exc=self._http_error(409, "nope")))
        tok = s2.create_request("s10b", "t")
        with self.assertRaises(VisualizerApprovalError):
            s2.decide(tok, "APPROVE", "nitin")
        s2._poster = FakePoster(200)
        self.assertEqual(s2.decide(tok, "APPROVE", "nitin")["status"], "VISUALIZER_APPROVED")

    def test_s11_failure_then_success_consumes_once(self):
        # failure (wrong 409) does NOT consume; subsequent exact-replay 409 -> single idempotent success
        s = svc(self.tmp, FakePoster(409, "wrong"))
        tok = s.create_request("s11", "t")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        s._poster = FakePoster(409, self.EXACT)
        r = s.decide(tok, "APPROVE", "nitin")
        self.assertTrue(r["idempotent_replay"])
        r2 = s.decide(tok, "APPROVE", "nitin")               # now server-nonce short-circuit
        self.assertTrue(r2.get("idempotent_replay"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
