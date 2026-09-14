"""Security tests for the Publish Approval eligibility verifier (server side, fail-closed).

No network. Reuses the real unpipe.approvals.ApprovalStore (three human gates, fingerprint-bound)
plus an in-memory publish grant (platform/schedule scope, expiry, revocation). Proves the eligibility
contract and that nothing but a complete, in-scope, unexpired, non-revoked, fingerprint-matched
Publish Approval yields eligible=true. status=New / VISUALIZER_APPROVED / FINAL_VIDEO alone never pass.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE
from unpipe.publish_approval import PublishApprovalService, compute_fingerprint, REASON_ELIGIBLE

NOW = 1_000_000
CID = "AKI_M02_REPLAY"


def base_req(platform="instagram", asset="abc123", pkg="pkg1", sver="v1", sched=NOW + 100):
    return {
        "content_id": CID,
        "platform": platform,
        "asset_sha256": asset,
        "packaging_sha256": pkg,
        "schedule_version": sver,
        "scheduled_at_epoch": sched,
    }


class FailingApprovals:
    def is_approved(self, *a, **k):
        raise RuntimeError("approval store unavailable")


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ApprovalStore(str(Path(self.tmp) / "_publish_approvals.json"))

    def _approve_all(self, fp, gates=(GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH)):
        for g in gates:
            self.store.record(CID, "asset", g, APPROVE, "nitin", fp)

    def _grant(self, fp, **over):
        g = {
            "approval_id": "PA-001",
            "fingerprint": fp,
            "platforms": ["instagram", "facebook"],
            "schedule_window": [NOW, NOW + 1000],
            "schedule_version": "v1",
            "exp": NOW + 10_000,
            "revoked": False,
        }
        g.update(over)
        return {CID: g}

    def _svc(self, grants, approvals=None):
        return PublishApprovalService(approvals or self.store, grants, now=lambda: NOW)

    def _full(self, **grant_over):
        req = base_req()
        fp = compute_fingerprint(req["content_id"], req["asset_sha256"], req["platform"],
                                 req["packaging_sha256"], req["schedule_version"])
        self._approve_all(fp)
        return self._svc(self._grant(fp, **grant_over)), req, fp

    # 13 valid complete approval -> eligible
    def test_13_valid_complete_eligible(self):
        svc, req, _ = self._full()
        r = svc.evaluate(req)
        self.assertTrue(r["eligible"])
        self.assertEqual(r["reason"], REASON_ELIGIBLE)
        self.assertEqual(r["approval_id"], "PA-001")

    # 1 no Publish Approval (no grant) -> blocked
    def test_1_no_publish_approval_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp)
        r = self._svc({}).evaluate(req)              # no grant at all
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    # 1b publish GATE decision missing (grant present) -> blocked
    def test_1b_publish_gate_missing_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp, gates=(GATE_CREATIVE, GATE_FINAL_VIDEO))   # no publish gate
        r = self._svc(self._grant(fp)).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    # 2 creative missing -> blocked
    def test_2_creative_missing_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp, gates=(GATE_FINAL_VIDEO, GATE_PUBLISH))
        r = self._svc(self._grant(fp)).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "CREATIVE_APPROVAL_MISSING")

    # 3 final video missing -> blocked
    def test_3_final_missing_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp, gates=(GATE_CREATIVE, GATE_PUBLISH))
        r = self._svc(self._grant(fp)).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "FINAL_VIDEO_APPROVAL_MISSING")

    # 4 expired -> blocked
    def test_4_expired_blocked(self):
        svc, req, _ = self._full(exp=NOW - 1)
        r = svc.evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "EXPIRED")

    # 5 revoked -> blocked
    def test_5_revoked_blocked(self):
        svc, req, _ = self._full(revoked=True)
        r = svc.evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "REVOKED")

    # 6 fingerprint mismatch (gates match req fp, grant bound to a different fp) -> blocked
    def test_6_fingerprint_mismatch_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp)
        r = self._svc(self._grant("DIFFERENT_FINGERPRINT")).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "FINGERPRINT_MISMATCH")

    # 6b material change after approval (asset swapped) -> blocked
    def test_6b_material_change_blocked(self):
        svc, req, _ = self._full()
        req2 = dict(req, asset_sha256="SWAPPED_AFTER_APPROVAL")
        self.assertFalse(svc.evaluate(req2)["eligible"])

    # 7 wrong platform (gates+grant fp aligned to requested platform, but platform not in scope) -> blocked
    def test_7_wrong_platform_blocked(self):
        req = base_req(platform="tiktok")
        fp = compute_fingerprint(CID, req["asset_sha256"], "tiktok", req["packaging_sha256"], "v1")
        self._approve_all(fp)
        r = self._svc(self._grant(fp, platforms=["instagram", "facebook"])).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "PLATFORM_MISMATCH")

    # 8 wrong schedule (outside window) -> blocked
    def test_8_wrong_schedule_blocked(self):
        svc, req, _ = self._full()
        r = svc.evaluate(dict(req, scheduled_at_epoch=NOW + 999_999))
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "SCHEDULE_MISMATCH")

    # 8b wrong schedule_version -> blocked
    def test_8b_wrong_schedule_version_blocked(self):
        svc, req, _ = self._full()
        r = svc.evaluate(dict(req, schedule_version="v2"))
        self.assertFalse(r["eligible"])
        # fp includes schedule_version, so gates/grant fp won't match -> still blocked
        self.assertFalse(r["eligible"])

    # 9 status=New only (no approvals, no grant) -> blocked
    def test_9_status_new_only_blocked(self):
        req = dict(base_req(), status="New")
        r = self._svc({}).evaluate(req)     # empty store, no grant
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    # 10 VISUALIZER_APPROVED only -> blocked (visualizer is never consulted; no real gates)
    def test_10_visualizer_only_blocked(self):
        req = dict(base_req(), status="VISUALIZER_APPROVED")
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        # a grant exists but NONE of the 3 human gates are approved
        r = self._svc(self._grant(fp)).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "CREATIVE_APPROVAL_MISSING")

    # 10b FINAL_VIDEO_APPROVED alone (creative+final only, no publish) -> blocked
    def test_10b_final_video_alone_blocked(self):
        req = base_req()
        fp = compute_fingerprint(CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")
        self._approve_all(fp, gates=(GATE_CREATIVE, GATE_FINAL_VIDEO))
        r = self._svc(self._grant(fp)).evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "NO_PUBLISH_APPROVAL")

    # 11 malformed request -> blocked
    def test_11_malformed_blocked(self):
        svc, _, _ = self._full()
        for bad in (None, {}, {"content_id": CID}, {"platform": "instagram"}, "not-a-dict",
                    {"content_id": CID, "platform": "instagram"}):  # missing asset_sha256
            r = svc.evaluate(bad)
            self.assertFalse(r["eligible"])
            self.assertEqual(r["reason"], "MALFORMED_REQUEST")

    # 12 verifier/internal lookup error -> fail closed
    def test_12_internal_error_fail_closed(self):
        req = base_req()
        svc = self._svc(self._grant(compute_fingerprint(
            CID, req["asset_sha256"], req["platform"], req["packaging_sha256"], "v1")),
            approvals=FailingApprovals())
        r = svc.evaluate(req)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "INTERNAL_ERROR")

    # 14 duplicate verification does not mutate approval authority
    def test_14_duplicate_verification_no_mutation(self):
        svc, req, _ = self._full()
        approvals_before = copy.deepcopy(self.store.all(CID))
        grants_before = copy.deepcopy(svc._grants)
        r1 = svc.evaluate(req)
        r2 = svc.evaluate(req)
        self.assertTrue(r1["eligible"] and r2["eligible"])
        self.assertEqual(r1, r2)
        self.assertEqual(self.store.all(CID), approvals_before)   # store unchanged
        self.assertEqual(svc._grants, grants_before)              # grants unchanged

    # extra: eligible result carries no secret material
    def test_15_result_has_no_secret_fields(self):
        svc, req, _ = self._full()
        r = svc.evaluate(req)
        self.assertEqual(set(r.keys()), {"eligible", "content_id", "platform", "approval_id", "reason"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
