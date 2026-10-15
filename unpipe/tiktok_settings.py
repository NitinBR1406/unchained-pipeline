"""TikTok post settings chosen by the creator, per placement (TikTok Direct Post UX requirements).

TikTok's Direct Post guidelines require that, for every post, the creator sees the content and caption, picks the privacy
level himself from the options TikTok returns for his account (creator_info; no default), decides on comments/duet/stitch
(off unless switched on) and gives explicit consent. This service renders that choice on a signed, expiring, single-use link
and stores the result ON THE PUBLISH GRANT of exactly that placement (content_id::platform). The grant is bound to the
material fingerprint, so a changed file/text/schedule needs a new grant and therefore a new choice.

Token format is byte-compatible with unpipe.approval_service / unpipe.visualizer_approval:
    token = b64url(payload_json) + "." + hex(hmac_sha256(payload_b64, secret))
payload = {gate:"tiktok_settings", content_id, platform, caption, preview_url, creator_nickname, privacy_options, exp, nonce}
privacy_options come from TikTok creator_info/query at link-creation time (Make). They are signed, so the page cannot be
tricked into offering another level; P3 re-checks the chosen level against creator_info right before posting.

This module NEVER creates a grant, NEVER approves anything and NEVER posts: without an eligible publish grant the
choice is refused, and the publish gate still decides eligibility exactly as before.
"""
import base64
import hashlib
import hmac
import json
import time

from .util import read_json, write_json, now_iso

GATE_TIKTOK_SETTINGS = "tiktok_settings"
TIKTOK_PLATFORMS = ("tiktok", "tiktok_photo")
KNOWN_PRIVACY = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")


def _b64e(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class TikTokSettingsError(Exception):
    pass


class TikTokSettingsService:
    def __init__(self, signing_secret, approvers, grants_path, consumed_path, now=None):
        if not signing_secret:
            raise TikTokSettingsError("signing secret required (server-side)")
        self._secret = signing_secret.encode() if isinstance(signing_secret, str) else signing_secret
        self.approvers = set(approvers)
        self.grants_path = grants_path
        self.consumed_path = consumed_path
        self._now = now or (lambda: int(time.time()))

    def _sign(self, pb):
        return hmac.new(self._secret, pb.encode(), hashlib.sha256).hexdigest()

    def create_request(self, content_id, platform, caption, privacy_options, preview_url="", creator_nickname="", ttl=86400):
        if platform not in TIKTOK_PLATFORMS:
            raise TikTokSettingsError("not a TikTok placement")
        opts = [o for o in (privacy_options or []) if o in KNOWN_PRIVACY]
        if not opts:
            raise TikTokSettingsError("no privacy options from creator_info")
        payload = {"gate": GATE_TIKTOK_SETTINGS, "content_id": content_id, "platform": platform, "caption": caption,
                   "preview_url": preview_url, "creator_nickname": creator_nickname, "privacy_options": opts,
                   "exp": self._now() + int(ttl),
                   "nonce": _b64e(hashlib.sha256(("%s%s%s" % (content_id, platform, time.time())).encode()).digest()[:12])}
        pb = _b64e(json.dumps(payload, separators=(",", ":")).encode())
        return "%s.%s" % (pb, self._sign(pb))

    def _verify(self, token):
        try:
            pb, sig = token.split(".", 1)
        except (ValueError, AttributeError):
            raise TikTokSettingsError("malformed token")
        if not hmac.compare_digest(sig, self._sign(pb)):
            raise TikTokSettingsError("bad signature")
        try:
            p = json.loads(_b64d(pb))
        except Exception:
            raise TikTokSettingsError("malformed token")
        if p.get("gate") != GATE_TIKTOK_SETTINGS:
            raise TikTokSettingsError("wrong gate")
        if self._now() > int(p["exp"]):
            raise TikTokSettingsError("token expired")
        return p

    def render_request(self, token):
        p = self._verify(token)
        d = {k: p.get(k, "") for k in ("content_id", "platform", "caption", "preview_url", "creator_nickname")}
        d["privacy_options"] = list(p["privacy_options"])
        return d

    def _grants(self):
        data = read_json(self.grants_path, default={"grants": {}}) or {"grants": {}}
        if not isinstance(data, dict) or not isinstance(data.get("grants"), dict):
            data = {"grants": {}}
        return data

    def decide(self, token, form, approver):
        """form: dict of submitted fields. Returns the stored settings. Raises TikTokSettingsError on any refusal."""
        p = self._verify(token)
        if approver not in self.approvers:
            raise TikTokSettingsError("unauthorized approver")
        consumed = read_json(self.consumed_path, default={}) or {}
        if p["nonce"] in consumed:
            return {**consumed[p["nonce"]], "idempotent_replay": True}
        level = (form.get("privacy_level") or "").strip()
        if not level:
            raise TikTokSettingsError("privacy level must be chosen (no default)")
        if level not in p["privacy_options"]:
            raise TikTokSettingsError("privacy level not offered for this account")
        if (form.get("consent") or "") != "yes":
            raise TikTokSettingsError("explicit consent is required")
        key = "%s::%s" % (p["content_id"], p["platform"])
        data = self._grants()
        grant = data["grants"].get(key)
        if not grant or grant.get("revoked") or p["platform"] not in (grant.get("platforms") or []):
            raise TikTokSettingsError("no active publish grant for this placement")
        settings = {"privacy_level": level,
                    "allow_comment": form.get("allow_comment") == "on",
                    "allow_duet": form.get("allow_duet") == "on",
                    "allow_stitch": form.get("allow_stitch") == "on",
                    "consent": True, "by": approver, "at": now_iso(), "nonce": p["nonce"],
                    "grant_fingerprint": grant.get("fingerprint")}
        grant["tiktok_settings"] = settings
        write_json(self.grants_path, data)
        consumed[p["nonce"]] = settings
        write_json(self.consumed_path, consumed)
        return settings


def settings_for_response(grant, platform):
    """What the publish gate returns to P3 for an ELIGIBLE TikTok placement (None if not chosen / not bound)."""
    s = (grant or {}).get("tiktok_settings")
    if platform not in TIKTOK_PLATFORMS or not isinstance(s, dict) or not s.get("consent"):
        return None
    if s.get("grant_fingerprint") != grant.get("fingerprint") or s.get("privacy_level") not in KNOWN_PRIVACY:
        return None
    return {"privacy_level": s["privacy_level"], "disable_comment": not s.get("allow_comment"),
            "disable_duet": not s.get("allow_duet"), "disable_stitch": not s.get("allow_stitch")}
