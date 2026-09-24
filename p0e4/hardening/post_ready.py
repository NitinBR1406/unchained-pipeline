"""Strict POST_READY assembly, safe-area checks, and bounded repair governance."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def valid_sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_asset(asset):
    require(set(asset) == {"role", "uri", "sha256", "bytes", "technical", "provenance"}, "asset fields")
    require(asset["role"] in {"master", "derivative", "still"}, "asset role")
    require(valid_sha(asset["sha256"]) and asset["bytes"] > 0, "asset identity")
    require(asset["provenance"]["source_sha256"] and valid_sha(asset["provenance"]["source_sha256"]), "source provenance")
    technical = asset["technical"]
    if asset["role"] in {"master", "derivative"}:
        require(set(technical) == {"width", "height", "fps", "duration_ms", "audio_tracks", "decode"}, "video technical fields")
        require(technical["width"] == 1080 and technical["height"] == 1920, "portrait dimensions")
        require(technical["fps"] == 30 and technical["duration_ms"] > 0, "video timing")
        require(technical["audio_tracks"] >= 1 and technical["decode"] == "COMPLETE", "technical decode")
    else:
        require(set(technical) == {"width", "height", "decode"}, "still technical fields")
        require(technical["width"] == 1080 and technical["height"] == 1920 and technical["decode"] == "COMPLETE", "still technical")


def validate_safe_area(record):
    require(set(record) == {"asset_sha256", "performer_box", "overlays", "platform_ui_exclusions"}, "safe-area fields")
    require(valid_sha(record["asset_sha256"]), "safe-area asset")
    def rect(value):
        require(set(value) == {"x", "y", "w", "h"}, "rectangle fields")
        require(all(type(value[k]) in (int, float) for k in value), "rectangle number")
        require(0 <= value["x"] < 1 and 0 <= value["y"] < 1 and value["w"] > 0 and value["h"] > 0, "rectangle bounds")
        require(value["x"] + value["w"] <= 1 and value["y"] + value["h"] <= 1, "rectangle overflow")
    rect(record["performer_box"])
    def intersects(a, b):
        return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or
                    a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
    for excluded in record["platform_ui_exclusions"]:
        rect(excluded)
    for overlay in record["overlays"]:
        require(set(overlay) == {"kind", "rect", "non_lyric"}, "overlay fields")
        require(overlay["kind"] in {"title", "artist", "caption", "logo"}, "overlay kind")
        require(overlay["non_lyric"] is True, "lyrics require authoritative source")
        rect(overlay["rect"])
        a, b = overlay["rect"], record["performer_box"]
        require(not intersects(a, b), "overlay intersects performer safe area")
        require(all(not intersects(a, excluded) for excluded in record["platform_ui_exclusions"]),
                "overlay intersects platform UI exclusion")
    return True


def authorize_bounded_repair(request, prior_outputs):
    expected = {"schema", "attempt", "trigger_qc_sha256", "defect_ids", "operations", "input_hashes",
                "production_deployment_authorized", "publication_authorized", "first_real_poster"}
    require(set(request) == expected and request["schema"] == "BOUNDED_REPAIR_REQUEST_V01", "repair fields")
    require(request["attempt"] in (1, 2), "repair budget exhausted")
    require(valid_sha(request["trigger_qc_sha256"]), "QC evidence binding")
    require(request["defect_ids"] and len(set(request["defect_ids"])) == len(request["defect_ids"]), "repair defects")
    allowed = {"OVERLAY_REPOSITION", "TAIL_FADE", "TAIL_EXTENSION_FRAMES", "AUDIO_FADE"}
    require(request["operations"] and set(request["operations"]) <= allowed, "repair scope expansion")
    require(request["input_hashes"] == [x["sha256"] for x in prior_outputs], "repair input drift")
    require(request["production_deployment_authorized"] is False and request["publication_authorized"] is False, "authority drift")
    require(request["first_real_poster"] == "PAUSED_BY_NITIN", "poster gate drift")
    return {"schema": "BOUNDED_REPAIR_AUTHORIZATION_V01", "attempt": request["attempt"],
            "allowed_operations": deepcopy(request["operations"]), "source_hashes_locked": deepcopy(request["input_hashes"]),
            "status": "AUTHORIZED_PRIVATE_REPAIR_ONLY", "publication_authorized": False}


def assemble(content_id, inputs, outputs, stills, qc, safe_areas, platform_map):
    require(content_id and type(content_id) is str, "content id")
    require(set(inputs) == {"raw_sha256", "audio_sha256"} and all(valid_sha(x) for x in inputs.values()), "input lineage")
    require(outputs and stills, "outputs and stills required")
    assets = outputs + stills
    for asset in assets:
        validate_asset(asset)
    hashes = [x["sha256"] for x in assets]
    require(len(hashes) == len(set(hashes)), "duplicate outputs")
    require(qc == {"verdict": "PASS", "checked_assets": [x["sha256"] for x in outputs]}, "independent QC coverage")
    require({x["asset_sha256"] for x in safe_areas} == {x["sha256"] for x in outputs}, "safe-area coverage")
    for record in safe_areas:
        validate_safe_area(record)
    require(set(platform_map) == {"youtube_hero", "youtube_shorts", "instagram_reels", "facebook_reels", "tiktok"}, "platform map coverage")
    output_hashes = {x["sha256"] for x in outputs}
    for platform, asset_sha in platform_map.items():
        require(asset_sha in output_hashes, "platform asset not bound")
    return {
        "schema": "HARDENED_POST_READY_PACKAGE_V01", "content_id": content_id,
        "status": "POST_READY_WAITING_FOR_NITIN", "inputs": deepcopy(inputs),
        "outputs": deepcopy(outputs), "stills": deepcopy(stills), "qc": deepcopy(qc),
        "safe_areas": deepcopy(safe_areas), "platform_map": deepcopy(platform_map),
        "rights_status": "UNKNOWN_RIGHTS_HOLD", "lyrics_status": "UNKNOWN_NOT_INVENTED",
        "production_deployment_authorized": False, "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN", "package_sha256": None,
    }


def seal(package):
    require(package["package_sha256"] is None, "package already sealed")
    result = deepcopy(package)
    result["package_sha256"] = digest({k: v for k, v in result.items() if k != "package_sha256"})
    return result
