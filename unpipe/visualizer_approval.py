"""Visualizer approval verifier (reuses the existing APPROVAL_SIGNING_SECRET / HMAC scheme).

Purpose: replace the unauthenticated Make "Visualizer Approve" webhook. Possession of a URL is never
sufficient. The signed, expiring, single-use link is verified HERE (server can compute HMAC), and only
on success does the server call the NEW Make webhook (with an x-make-apikey header). Make then does its
own known-content + dedupe checks and writes ONLY a VISUALIZER_APPROVED state.

Token format is byte-compatible with unpipe.approval_service:
    token = b64url(payload_json) + "." + hex(hmac_sha256(payload_b64, secret))
payload = {gate:"visualizer", content_id, title, exp, nonce}

CRITICAL: this module NEVER sets Scheduled, NEVER sets publish_to_* TRUE, NEVER creates a Publish
Approval. It only asks Make to record VISUALIZER_APPROVED. Real publishing stays gated on a separate,
independently-validated Publish Approval Token (unpipe.publish_approval).
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.request

from .util import read_json, write_json, now_iso

GATE_VISUALIZER = "visualizer"


def _b64e(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class VisualizerApprovalError(Exception):
    pass


def _http_post_json(url, payload, apikey, timeout=20):
    """Default Make poster. Sends x-make-apikey; returns (status_code, body_text)."""
    data = json.dumps(payload, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("x-make-apikey", apikey)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode(errors="ignore")


class VisualizerApprovalService:
    def __init__(self, signing_secret, approvers, consumed_path,
                 make_webhook_url="", make_apikey="", poster=None):
        if not signing_secret:
            raise VisualizerApprovalError("signing secret required (server-side)")
        self._secret = signing_secret.encode() if isinstance(signing_secret, str) else signing_secret
        self.approvers = set(approvers)
        self.consumed_path = consumed_path
        self._consumed = read_json(consumed_path, default={}) or {}
        self._make_url = make_webhook_url
        self._make_apikey = make_apikey
        self._poster = poster or _http_post_json  # injectable for tests (no network)

    # ---------------------------------------------------------------- tokens
    def _sign(self, payload_b64):
        return hmac.new(self._secret, payload_b64.encode(), hashlib.sha256).hexdigest()

    def create_request(self, content_id, title, ttl=86400):
        payload = {"gate": GATE_VISUALIZER, "content_id": content_id, "title": title,
                   "exp": int(time.time()) + ttl,
                   "nonce": _b64e(hashlib.sha256(f"{content_id}{title}{time.time()}".encode()).digest()[:12])}
        pb = _b64e(json.dumps(payload, separators=(",", ":")).encode())
        return f"{pb}.{self._sign(pb)}"

    def _verify(self, token):
        try:
            pb, sig = token.split(".", 1)
        except ValueError:
            raise VisualizerApprovalError("malformed token")
        if not hmac.compare_digest(sig, self._sign(pb)):
            raise VisualizerApprovalError("bad signature")
        payload = json.loads(_b64d(pb))
        if payload.get("gate") != GATE_VISUALIZER:
            raise VisualizerApprovalError("wrong gate")
        if int(time.time()) > int(payload["exp"]):
            raise VisualizerApprovalError("token expired")
        return payload

    def render_request(self, token):
        p = self._verify(token)
        return {"content_id": p["content_id"], "title": p.get("title", p["content_id"]),
                "status": "READY FOR VISUALIZER APPROVAL", "actions": ["APPROVE", "REJECT"]}

    # ---------------------------------------------------------------- decision
    def decide(self, token, decision, approver):
        p = self._verify(token)                              # bad sig / expiry -> raises
        if approver not in self.approvers:
            raise VisualizerApprovalError("unauthorized approver")
        if decision not in ("APPROVE", "REJECT"):
            raise VisualizerApprovalError("bad decision")

        nonce = p["nonce"]
        if nonce in self._consumed:                          # replay / double-tap -> idempotent
            return {**self._consumed[nonce], "idempotent_replay": True}

        if decision == "REJECT":
            result = {"status": "REJECTED", "content_id": p["content_id"], "by": approver, "at": now_iso(),
                      "forwarded_to_make": False}
            self._consume(nonce, result)
            return result

        # APPROVE: forward to Make (server-verified). Make enforces apikey + known-content + dedupe,
        # and writes ONLY VISUALIZER_APPROVED. The server sets NO publish state of any kind.
        if not self._make_url or not self._make_apikey:
            raise VisualizerApprovalError("make webhook/apikey not configured")
        body = {"content_id": p["content_id"], "title": p.get("title", ""), "approver": approver,
                "nonce": nonce, "ts": int(time.time()), "intent": "VISUALIZER_APPROVED"}
        code, _ = self._poster(self._make_url, body, self._make_apikey)
        if not (200 <= int(code) < 300):
            raise VisualizerApprovalError(f"make webhook rejected (status {code})")
        result = {"status": "VISUALIZER_APPROVED", "content_id": p["content_id"], "by": approver,
                  "at": now_iso(), "forwarded_to_make": True, "make_status": int(code),
                  "creates_publish_approval": False, "sets_scheduled": False}
        self._consume(nonce, result)
        return result

    def _consume(self, nonce, result):
        self._consumed[nonce] = result
        write_json(self.consumed_path, self._consumed)
