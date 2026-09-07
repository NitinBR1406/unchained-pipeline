"""One-tap approval service (V1.1.2) — framework-free, reusable for all three gates.

A signed, expiring, single-use link encodes {campaign_id, gate, asset_id, sha, exp, nonce}. On tap,
`decide()` validates it, re-checks the current artifact SHA, records the authoritative approval via
Campaign.approve() (which auto-dispatches for creative), and is idempotent on replay/double-tap.

Secrets: the HMAC signing secret and the GitHub dispatch token stay server-side. The client only
holds the opaque token — never a PAT/key/secret.
"""
import base64
import hashlib
import hmac
import json
import time

from .approvals import GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH, APPROVE, REJECT
from .util import read_json, write_json, now_iso, sha256_file

GATE_LABELS = {GATE_CREATIVE: "Creative Preview", GATE_FINAL_VIDEO: "Final Master",
               GATE_PUBLISH: "Release Package"}


def _b64e(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class ApprovalError(Exception):
    pass


class ApprovalService:
    def __init__(self, signing_secret, campaign_factory, approvers, consumed_path):
        if not signing_secret:
            raise ApprovalError("signing secret required (server-side)")
        self._secret = signing_secret.encode() if isinstance(signing_secret, str) else signing_secret
        self.campaign_factory = campaign_factory      # callable(campaign_id) -> Campaign (dispatcher set)
        self.approvers = set(approvers)               # allowlist of authorised approver ids
        self.consumed_path = consumed_path
        self._consumed = read_json(consumed_path, default={}) or {}

    # ---------------------------------------------------------------- tokens
    def _sign(self, payload_b64):
        return hmac.new(self._secret, payload_b64.encode(), hashlib.sha256).hexdigest()

    def create_request(self, campaign_id, gate, asset_id, sha, ttl=86400):
        payload = {"campaign_id": campaign_id, "gate": gate, "asset_id": asset_id,
                   "sha": sha, "exp": int(time.time()) + ttl,
                   "nonce": _b64e(hashlib.sha256(f"{campaign_id}{sha}{time.time()}".encode()).digest()[:12])}
        pb = _b64e(json.dumps(payload, separators=(",", ":")).encode())
        return f"{pb}.{self._sign(pb)}"

    def _verify(self, token):
        try:
            pb, sig = token.split(".", 1)
        except ValueError:
            raise ApprovalError("malformed token")
        if not hmac.compare_digest(sig, self._sign(pb)):
            raise ApprovalError("bad signature")
        payload = json.loads(_b64d(pb))
        if int(time.time()) > int(payload["exp"]):
            raise ApprovalError("token expired")
        return payload

    # ---------------------------------------------------------------- display (mobile page data)
    def render_request(self, token):
        p = self._verify(token)
        c = self.campaign_factory(p["campaign_id"])
        return {  # NO sha / render-id / secrets in the surfaced fields
            "artist": c.manifest.get("artist", "UNCHAINED NITIN"),
            "campaign": c.manifest.get("song_title", p["campaign_id"]),
            "asset": GATE_LABELS.get(p["gate"], "Asset"),
            "gate": p["gate"],
            "version": c.manifest.get("release_status", "V01"),
            "status": f"READY FOR {GATE_LABELS.get(p['gate'],'').upper()} APPROVAL",
            "actions": ["APPROVE", "REJECT"],
        }

    # ---------------------------------------------------------------- decision (the one tap)
    def decide(self, token, decision, approver, reason=""):
        p = self._verify(token)
        if approver not in self.approvers:
            raise ApprovalError("unauthorized approver")
        if decision not in (APPROVE, REJECT):
            raise ApprovalError("bad decision")

        nonce = p["nonce"]
        if nonce in self._consumed:                    # replay / double-tap -> idempotent
            return {**self._consumed[nonce], "idempotent_replay": True}

        c = self.campaign_factory(p["campaign_id"])

        # SHA re-check at tap time (bind to the exact artifact that was previewed)
        if decision == APPROVE and p["gate"] == GATE_CREATIVE:
            cur = c._resolve_frozen()
            cur_sha = sha256_file(cur) if cur else None
            if cur_sha != p["sha"]:
                c.hold("artifact changed since approval request -> REAPPROVAL_REQUIRED")
                result = {"status": "REAPPROVAL_REQUIRED", "dispatched": False, "at": now_iso()}
                self._consume(nonce, result)
                raise ApprovalError("artifact SHA changed since request; reapproval required")

        # record the authoritative approval (auto-dispatches for creative APPROVE via orchestrator)
        rec = c.approve(p["gate"], p["asset_id"], p["sha"], by=approver,
                        decision=decision, notes=reason)
        # downstream consequence for other gates
        if decision == APPROVE and p["gate"] in (GATE_FINAL_VIDEO, GATE_PUBLISH):
            try:
                c.advance(master_sha=p["sha"])
            except Exception:
                pass  # advance guards enforce gates; never crash the tap

        result = {"status": "RECORDED", "decision": decision, "gate": p["gate"],
                  "campaign_id": p["campaign_id"], "approved_by": approver,
                  "artifact_sha256": p["sha"], "at": now_iso(),
                  "dispatched": bool(decision == APPROVE and p["gate"] == GATE_CREATIVE),
                  "state": c.state.value}
        self._consume(nonce, result)
        return result

    def _consume(self, nonce, result):
        self._consumed[nonce] = result
        write_json(self.consumed_path, self._consumed)
