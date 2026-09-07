"""Adapters for stages that depend on external systems not connected in this environment.

Each adapter declares connected=False by default and returns ADAPTER_READY results without
performing real external actions. Real integrations plug in later by subclassing / setting
connected=True. Nothing here publishes.
"""
from .util import now_iso


# --------------------------------------------------------------------------- derivatives
class DerivativeEngine:
    """Cuts platform derivatives from an approved master. Local ffmpeg-capable in principle;
    here it declares the derivative plan (interface) so packaging/publish can proceed by design."""
    DEFAULT_TARGETS = ["youtube_hero", "youtube_shorts", "instagram_reels", "instagram_feed",
                       "instagram_stories", "tiktok", "facebook_reels"]

    def __init__(self, connected=False):
        self.connected = connected

    def plan(self, campaign_id, master_path, targets):
        return {"campaign_id": campaign_id, "master": str(master_path),
                "targets": targets, "generated_at": now_iso(),
                "status": "ADAPTER_READY" if not self.connected else "READY",
                "note": "ffmpeg cut adapter; enable connected=True + ffmpeg for real cuts"}


# --------------------------------------------------------------------------- packaging
class PackagingEngine:
    """Builds per-platform metadata packages (structured data, not identical copy everywhere)."""
    def build(self, campaign_id, targets, base_meta):
        pkgs = []
        for t in targets:
            pkgs.append({
                "platform": t, "asset": f"{campaign_id}:{t}",
                "title": base_meta.get("title"), "caption": None, "description": None,
                "hashtags": [], "thumbnail": None, "cover_frame": None, "cta": None,
                "publish_datetime": None, "rights_status": base_meta.get("rights_status"),
                "approval_status": "PENDING",
            })
        return {"campaign_id": campaign_id, "packages": pkgs, "status": "ADAPTER_READY",
                "generated_at": now_iso()}


# --------------------------------------------------------------------------- rights
RIGHTS_STATES = ("RIGHTS_UNKNOWN", "RIGHTS_REVIEW", "RIGHTS_PASS", "RIGHTS_HOLD")


class RightsGate:
    def evaluate(self, manifest_rights):
        status = (manifest_rights or {}).get("status", "RIGHTS_UNKNOWN")
        if status not in RIGHTS_STATES:
            status = "RIGHTS_UNKNOWN"
        return {"status": status, "pass": status == "RIGHTS_PASS", "evaluated_at": now_iso()}


# --------------------------------------------------------------------------- publish
class PublishAdapter:
    def __init__(self, platform, connected=False):
        self.platform = platform
        self.connected = connected

    def publish(self, package):
        if not self.connected:
            return {"platform": self.platform, "status": "ADAPTER_READY_NOT_CONNECTED",
                    "published": False, "at": now_iso()}
        raise NotImplementedError("real publish integration not configured")


def default_publish_adapters():
    return {p: PublishAdapter(p) for p in
            ["youtube", "instagram", "facebook", "tiktok"]}


# --------------------------------------------------------------------------- analytics
class AnalyticsAdapter:
    WINDOWS = ["24h", "72h", "7d", "14d", "28d"]

    def __init__(self, connected=False):
        self.connected = connected

    def snapshot(self, campaign_id, window):
        return {"campaign_id": campaign_id, "window": window,
                "status": "ADAPTER_READY_NOT_CONNECTED", "metrics": {}, "at": now_iso()}


# --------------------------------------------------------------------------- notifications
class Notifier:
    """Actionable-only notifications. Routine machine chatter is suppressed."""
    ACTIONABLE = {
        "AWAITING_CREATIVE_APPROVAL": "Creative preview ready — Approve / Reject",
        "AWAITING_FINAL_VIDEO_APPROVAL": "Final master ready — Approve / Reject",
        "AWAITING_PUBLISH_APPROVAL": "Release package ready — Publish / Hold",
        "TECH_QC_FAIL": "Technical QC failed — no action taken (system on hold)",
        "HOLD": "Pipeline on HOLD — review required",
    }

    def __init__(self):
        self.outbox = []

    def maybe_notify(self, campaign_id, state):
        msg = self.ACTIONABLE.get(state)
        if msg:
            n = {"campaign_id": campaign_id, "state": state, "message": msg, "at": now_iso()}
            self.outbox.append(n)
            return n
        return None
