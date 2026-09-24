"""Inert POST_READY projection for the observed Make/distribution edge."""
from copy import deepcopy
import hashlib
import json


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    blob = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def project(package, architecture_refs):
    require(package["schema"] == "HARDENED_POST_READY_PACKAGE_V01", "package schema")
    require(package["status"] == "POST_READY_WAITING_FOR_NITIN", "package not post-ready")
    require(package["package_sha256"] == digest({k: v for k, v in package.items() if k != "package_sha256"}), "package seal")
    require(package["production_deployment_authorized"] is False and package["publication_authorized"] is False, "authority drift")
    require(set(architecture_refs) == {"field_map", "live_headers", "make_boundary"}, "architecture refs")
    for ref in architecture_refs.values():
        require(set(ref) == {"uri", "sha256"} and len(ref["sha256"]) == 64, "architecture ref binding")
    rows = []
    for platform, asset_sha in sorted(package["platform_map"].items()):
        rows.append({
            "platform": platform, "content_id": package["content_id"], "asset_sha256": asset_sha,
            "status": "SHADOW_ONLY_NOT_DISPATCHABLE", "publish_to_platform": "FALSE",
            "schedule_at": None, "rights_status": package["rights_status"],
        })
    result = {
        "schema": "POST_READY_MAKE_SHADOW_V01", "mode": "SHADOW_ONLY_NOT_DISPATCHABLE",
        "source_package_sha256": package["package_sha256"], "rows": rows,
        "architecture_refs": deepcopy(architecture_refs),
        "external_writes": 0, "make_scenario_runs": 0, "social_uploads": 0,
        "production_deployment_authorized": False, "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN",
    }
    result["shadow_sha256"] = digest(result)
    return result


def verify_readback(shadow, source_package, architecture_refs):
    require(shadow == project(source_package, architecture_refs), "shadow semantic drift")
    require(all(row["publish_to_platform"] == "FALSE" and row["schedule_at"] is None for row in shadow["rows"]), "dispatch control drift")
    require(shadow["external_writes"] == shadow["make_scenario_runs"] == shadow["social_uploads"] == 0, "external side effect")
    return deepcopy(source_package)


def dispatch(*_args, **_kwargs):
    raise ValueError("LIVE_MAKE_CUTOVER_NOT_AUTHORIZED")
