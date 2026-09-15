"""P0E1-HUMAN-AUTH-001 — human-gate authority hardening.
An authoritative Nitin approval requires an INDEPENDENTLY VERIFIABLE detached Ed25519 signature over a
canonical approval payload, checked against a committed PUBLIC key (Nitin's PRIVATE key never enters the
repo/runtime). The event `agent` field is provenance only and grants NOTHING. Fail-closed on missing,
invalid, forged, mismatched, expired, revoked, duplicate or unverifiable approval evidence."""
import os, json
from .events import canonical, sha256
HUMAN_GATES = {"NITIN_CREATIVE_APPROVAL","NITIN_FINAL_ASSET_APPROVAL","NITIN_FINAL_VIDEO_APPROVAL",
               "NITIN_PUBLISH_APPROVAL","NITIN_CHANGE_APPROVAL"}
_PAYLOAD_REQUIRED = ("approval_id","gate","task_id","content_fingerprint","nonce","issued_at","expires_at","key_id")
def content_fingerprint(content):
    """Canonical content fingerprint (mirrors the Unchained governance model)."""
    return sha256({k:content.get(k) for k in ("content_id","asset_sha256","platform","packaging_sha256","schedule_version")})
def _verify_sig(pub_hex, msg_bytes, sig_hex):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        pub.verify(bytes.fromhex(sig_hex), msg_bytes)
        return True
    except Exception:
        return False
def load_keyring(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "..", "approval_authority.json")
    if os.path.exists(path):
        try: return json.load(open(path))
        except Exception: return {"keys":{},"revoked":[]}
    return {"keys":{},"revoked":[]}
def verify_approval(event, *, keyring, now, expected_gate, expected_task_id, expected_fingerprint,
                    consumed_ids, revoked_ids):
    """Return (ok:bool, reason:str). Fail-closed: only (True,'OK') grants authority."""
    appr = (event or {}).get("approval")
    if not isinstance(appr, dict) or "payload" not in appr or "signature" not in appr:
        return False, "MALFORMED_APPROVAL"
    p = appr["payload"]
    if not isinstance(p, dict) or any(k not in p for k in _PAYLOAD_REQUIRED):
        return False, "MALFORMED_PAYLOAD"
    kid = p.get("key_id"); keys = (keyring or {}).get("keys",{})
    if kid not in keys:
        return False, "UNKNOWN_OR_MISSING_KEY"   # no provisioned Nitin key => nothing verifies (fail-closed)
    if not _verify_sig(keys[kid]["public_key_hex"], canonical(p).encode(), appr["signature"]):
        return False, "BAD_SIGNATURE"            # forgery / AI impersonation / tampered payload
    if p["gate"] != expected_gate or event.get("gate") != expected_gate or p["gate"] not in HUMAN_GATES:
        return False, "GATE_MISMATCH"
    if p["task_id"] != expected_task_id:
        return False, "TASK_MISMATCH"
    if expected_fingerprint is not None and p["content_fingerprint"] != expected_fingerprint:
        return False, "CONTENT_MISMATCH"
    if not (p["issued_at"] <= now < p["expires_at"]):
        return False, "EXPIRED_OR_STALE"
    if p["approval_id"] in set(revoked_ids) or p["approval_id"] in set((keyring or {}).get("revoked",[])):
        return False, "REVOKED"
    if p["approval_id"] in set(consumed_ids) or p["nonce"] in set(consumed_ids):
        return False, "DUPLICATE"
    return True, "OK"
