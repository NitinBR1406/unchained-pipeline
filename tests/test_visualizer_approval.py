"""Security tests for the Visualizer approval verifier (server side of the rebuild).

Covers the verifier-owned controls (Make-owned controls — apikey/known-content/dedupe/no-publish —
are validated in the Make blueprint, not here). No network: the Make poster is injected.
Uses a TEST secret only; never the real APPROVAL_SIGNING_SECRET.
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.visualizer_approval import VisualizerApprovalService, VisualizerApprovalError

SECRET = "TEST_SECRET_NOT_THE_REAL_ONE"


class FakePoster:
    def __init__(self, status=200):
        self.status = status
        self.calls = []

    def __call__(self, url, payload, apikey):
        self.calls.append({"url": url, "payload": payload, "apikey": apikey})
        return self.status, "ok"


def svc(tmp, poster=None, ttl_poster_status=200):
    return VisualizerApprovalService(
        signing_secret=SECRET, approvers=["nitin"],
        consumed_path=str(Path(tmp) / "_vis_consumed.json"),
        make_webhook_url="https://make.example/hook", make_apikey="APIKEY_TEST",
        poster=poster or FakePoster(ttl_poster_status))


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_1_valid_signed_request_accepted_and_forwarded(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        r = s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")
        self.assertTrue(r["forwarded_to_make"])
        self.assertEqual(len(p.calls), 1)
        self.assertEqual(p.calls[0]["apikey"], "APIKEY_TEST")            # apikey carried
        self.assertEqual(p.calls[0]["payload"]["content_id"], "hua-main")
        self.assertFalse(r["creates_publish_approval"])                  # no publish approval
        self.assertFalse(r["sets_scheduled"])                           # never Scheduled

    def test_2_invalid_signature_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        pb, sig = tok.split(".", 1)
        tampered = pb + "." + ("0" * len(sig))
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tampered, "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 0)                               # never forwarded

    def test_3_expired_request_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main", ttl=-1)          # already expired
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(len(p.calls), 0)

    def test_4_replayed_nonce_idempotent_not_double_forwarded(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        r1 = s.decide(tok, "APPROVE", "nitin")
        r2 = s.decide(tok, "APPROVE", "nitin")                          # replay
        self.assertTrue(r2.get("idempotent_replay"))
        self.assertEqual(len(p.calls), 1)                               # forwarded exactly once
        self.assertEqual(r1["content_id"], r2["content_id"])

    def test_5_unauthorized_approver_rejected(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "someone_else")
        self.assertEqual(len(p.calls), 0)

    def test_6_make_rejection_surfaces_and_does_not_consume(self):
        p = FakePoster(403); s = svc(self.tmp, p)                       # Make says no (e.g. bad apikey)
        tok = s.create_request("hua-main", "Hua Main")
        with self.assertRaises(VisualizerApprovalError):
            s.decide(tok, "APPROVE", "nitin")
        # nonce not consumed -> a later legitimate retry (after fix) still possible
        p2 = FakePoster(200)
        s._poster = p2
        r = s.decide(tok, "APPROVE", "nitin")
        self.assertEqual(r["status"], "VISUALIZER_APPROVED")

    def test_7_reject_decision_records_without_forward(self):
        p = FakePoster(200); s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        r = s.decide(tok, "REJECT", "nitin")
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(len(p.calls), 0)

    def test_8_persistence_of_consumed_nonce_across_instances(self):
        p = FakePoster(200)
        s = svc(self.tmp, p)
        tok = s.create_request("hua-main", "Hua Main")
        s.decide(tok, "APPROVE", "nitin")
        s2 = svc(self.tmp, FakePoster(200))                            # new instance, same store
        r = s2.decide(tok, "APPROVE", "nitin")
        self.assertTrue(r.get("idempotent_replay"))                    # replay blocked after restart


if __name__ == "__main__":
    unittest.main(verbosity=2)
