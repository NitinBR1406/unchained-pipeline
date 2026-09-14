"""Single source of truth for publication canonicalization.

Fingerprint, packaging canonical JSON, scheduled_at->epoch, schedule window, and medium->final-gate
mapping ALL live here. Verifier, provisioner and tests import from this module. No duplicated
fingerprint/timestamp logic may exist elsewhere.
"""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .approvals import GATE_FINAL_VIDEO, GATE_FINAL_ASSET

MEDIUM_VIDEO = "video"
MEDIUM_POSTER = "poster"

DEFAULT_TZ = "Europe/Amsterdam"
SCHEDULE_FMT = "%Y-%m-%d %H:%M:%S"
# Fixed, single tolerance for the schedule window (seconds pre/post the scheduled instant).
SCHEDULE_GRACE_SECONDS = 3600


def compute_fingerprint(content_id, asset_sha256, platform, packaging_sha256="", schedule_version=""):
    """Material publication fingerprint. Any material change -> different fingerprint.

    IDENTICAL basis/ordering to the original verifier implementation (do not change silently)."""
    basis = {
        "content_id": content_id,
        "asset_sha256": asset_sha256,
        "platform": platform,
        "packaging_sha256": packaging_sha256 or "",
        "schedule_version": schedule_version or "",
    }
    raw = json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def packaging_canonical_json(content_id, caption):
    """Deterministic canonical packaging JSON (minimum contract)."""
    return json.dumps({"content_id": content_id, "caption": caption},
                      sort_keys=True, separators=(",", ":"))


def packaging_sha256(content_id, caption):
    return hashlib.sha256(packaging_canonical_json(content_id, caption).encode()).hexdigest()


def scheduled_at_to_epoch(scheduled_at, tz=DEFAULT_TZ):
    """'YYYY-MM-DD HH:MM:SS' interpreted in tz (default Europe/Amsterdam) -> int epoch seconds.

    Matches Make's parseDate(scheduled_at,'YYYY-MM-DD HH:mm:ss','Europe/Amsterdam') then formatDate 'X'.
    """
    dt = datetime.strptime(scheduled_at, SCHEDULE_FMT).replace(tzinfo=ZoneInfo(tz))
    return int(dt.timestamp())


def schedule_window(epoch, pre=SCHEDULE_GRACE_SECONDS, post=SCHEDULE_GRACE_SECONDS):
    """Single rule for the allowed publication window around the scheduled instant."""
    e = int(epoch)
    return [e - int(pre), e + int(post)]


def final_gate_for_medium(medium):
    """Medium-neutral final-asset gate. Unknown/empty medium -> video (preserves existing behavior)."""
    return GATE_FINAL_ASSET if medium == MEDIUM_POSTER else GATE_FINAL_VIDEO
