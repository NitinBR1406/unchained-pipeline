"""Publish Approval eligibility verifier (server-side authority, fail-closed).

Server-side verifier that decides whether ONE content item may be published NOW to ONE platform.
Authority lives SERVER-SIDE: the three human approval gates (unpipe.approvals.ApprovalStore, each
decision bound to the material fingerprint) plus a publish grant (platform scope / schedule scope /
expiry / revocation), both persisted on the server's disk and reachable ONLY behind an authenticated
endpoint. A process holding Make datastore write access CANNOT forge eligibility here.

CONTRACT — eligible ONLY if ALL are true:
    content exists (a publish grant exists for content_id)
    AND creative_approval      == APPROVED (bound to current fingerprint)
    AND final_video_approval   == APPROVED (bound to current fingerprint)
    AND publish_approval        == APPROVE (bound to current fingerprint)
    AND grant.fingerprint      == current fingerprint
    AND requested platform      in grant.platforms
    AND requested schedule/version within grant scope
    AND approval not expired
    AND approval not revoked

NEVER sufficient (must be BLOCKED): status="New", status="Scheduled", VISUALIZER_APPROVED,
FINAL_VIDEO_APPROVED alone. Any missing datum / lookup error / exception => NOT ELIGIBLE (fail closed).

This module does NOT weaken the visualizer approval flow: VISUALIZER_APPROVED is never consulted here
and never grants publication authority.
"""
import time

from .approvals import GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH
# Single source of truth for canonicalization (re-exported so existing importers keep working).
from .canonical import compute_fingerprint, final_gate_for_medium, MEDIUM_VIDEO
from .util import read_json

REASON_ELIGIBLE = "VALID_PUBLISH_APPROVAL"


class PublishApprovalError(Exception):
    pass


class PublishApprovalService:
    """Fail-closed eligibility verifier.

    approvals : unpipe.approvals.ApprovalStore  (creative/final/publish gate decisions; each bound
                to artifact_sha256 == the material fingerprint)
    grants    : dict {content_id: grant} OR a path to JSON {"grants": {content_id: grant}}
                grant = {approval_id, fingerprint, platforms:[...], schedule_window:[start_epoch,end_epoch],
                         schedule_version, exp:<epoch>, revoked:<bool>}
    Both are server-side artifacts (persistent disk); neither is writable from Make.
    """

    def __init__(self, approvals, grants, now=None):
        self.approvals = approvals
        if isinstance(grants, (str, bytes)):
            data = read_json(grants, default={"grants": {}}) or {"grants": {}}
            self._grants = data.get("grants", {}) if isinstance(data, dict) else {}
        else:
            self._grants = grants or {}
        self._now = now or (lambda: int(time.time()))

    @staticmethod
    def _blocked(reason):
        return {"eligible": False, "reason": reason}

    def evaluate(self, req):
        """Return {'eligible':bool, 'reason':<code>, ...}. NEVER raises (fail closed)."""
        try:
            if not isinstance(req, dict):
                return self._blocked("MALFORMED_REQUEST")
            content_id = req.get("content_id")
            platform = req.get("platform")
            asset_sha256 = req.get("asset_sha256")
            if not content_id or not platform or not asset_sha256:
                return self._blocked("MALFORMED_REQUEST")

            fp = compute_fingerprint(content_id, asset_sha256, platform,
                                     req.get("packaging_sha256", ""), req.get("schedule_version", ""))

            # content must exist AND have a publish grant (a bare content id / status is never enough).
            # Platform-scoped grant key (content_id::platform) with legacy fallback to content_id.
            # Approvals are checked under the SAME campaign key so IG/FB (different fingerprints) stay
            # independent; legacy video grants keyed by content_id resolve exactly as before.
            composite = "{}::{}".format(content_id, platform)
            grant = self._grants.get(composite)
            approval_campaign = composite
            if grant is None:
                grant = self._grants.get(content_id)
                approval_campaign = content_id
            if not grant:
                return self._blocked("NO_PUBLISH_APPROVAL")

            # three independent human gates, each bound to the current fingerprint
            if not self._is_approved(approval_campaign, GATE_CREATIVE, fp):
                return self._blocked("CREATIVE_APPROVAL_MISSING")
            # medium-neutral final-asset gate: video keeps NITIN_FINAL_VIDEO_APPROVAL, poster requires
            # NITIN_FINAL_ASSET_APPROVAL. Missing grant.medium defaults to video (existing behavior).
            final_gate = final_gate_for_medium(grant.get("medium", MEDIUM_VIDEO))
            if not self._is_approved(approval_campaign, final_gate, fp):
                return self._blocked("FINAL_ASSET_APPROVAL_MISSING" if final_gate == GATE_FINAL_ASSET
                                     else "FINAL_VIDEO_APPROVAL_MISSING")
            if not self._is_approved(approval_campaign, GATE_PUBLISH, fp):
                return self._blocked("NO_PUBLISH_APPROVAL")

            # publish grant scope / lifecycle
            if grant.get("revoked", False):
                return self._blocked("REVOKED")
            try:
                exp = int(grant["exp"])
            except (KeyError, TypeError, ValueError):
                return self._blocked("MALFORMED_APPROVAL")
            if self._now() > exp:
                return self._blocked("EXPIRED")
            if grant.get("fingerprint") != fp:
                return self._blocked("FINGERPRINT_MISMATCH")
            if platform not in (grant.get("platforms") or []):
                return self._blocked("PLATFORM_MISMATCH")

            sw = grant.get("schedule_window") or [None, None]
            st = req.get("scheduled_at_epoch")
            try:
                schedule_ok = (
                    st is not None and sw[0] is not None and sw[1] is not None
                    and int(sw[0]) <= int(st) <= int(sw[1])
                    and req.get("schedule_version") == grant.get("schedule_version")
                )
            except (TypeError, ValueError):
                schedule_ok = False
            if not schedule_ok:
                return self._blocked("SCHEDULE_MISMATCH")

            return {
                "eligible": True,
                "content_id": content_id,
                "platform": platform,
                "approval_id": grant.get("approval_id"),
                "reason": REASON_ELIGIBLE,
            }
        except Exception:
            # Any unexpected error (incl. approval-store unavailable) MUST fail closed.
            return self._blocked("INTERNAL_ERROR")

    def _is_approved(self, content_id, gate, fingerprint):
        """Delegate to the reused ApprovalStore; any error here is caught by evaluate() (fail closed)."""
        return bool(self.approvals.is_approved(content_id, gate, fingerprint))
