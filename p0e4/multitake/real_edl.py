"""Deterministic real-workload EDL builder/validator.

This module is deliberately data-only.  It cannot invoke Resolve, agents,
distribution, or publication.  The last source frame may bridge a sub-frame
timestamp shortfall only when decode evidence proves that exact frame exists.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_real_edl(sync_set, intelligence, edl):
    require(edl.get("schema") == "MULTI_TAKE_EDIT_DECISION_LIST_V01", "edl schema")
    require(edl.get("scope") == "PRIVATE_AAKHRI_ISHQ_ACCEPTANCE_ONLY", "scope")
    require(edl.get("synchronized_take_set_sha256") == sync_set["set_sha256"], "sync binding")
    require(edl.get("intelligence_sha256") == intelligence["intelligence_sha256"], "intelligence binding")
    require(edl.get("filename_semantics_used") is False, "filename inference")
    takes = {t["asset_id"]: t for t in sync_set["takes"]}
    ranges = {(r["asset_id"], r["start_ms"], r["end_ms"]): r
              for t in intelligence["take_observations"] for r in t["ranges"]}
    cursor = visible = 0
    for s in edl.get("segments", []):
        require(s["take_asset_id"] in takes, "unknown take")
        require(s["timeline_start_ms"] == cursor < s["timeline_end_ms"], "timeline continuity")
        require((s["take_asset_id"], s["timeline_start_ms"], s["timeline_end_ms"]) in ranges,
                "Gemini range binding")
        r = ranges[(s["take_asset_id"], s["timeline_start_ms"], s["timeline_end_ms"])]
        require(s["evidence_sha256"] == r["evidence_sha256"], "range evidence binding")
        take = takes[s["take_asset_id"]]
        require(s["take_start_ms"] >= take["take_usable_start_ms"], "source before usable range")
        excess = max(0, s["take_end_ms"] - take["take_usable_end_ms"])
        require(excess <= edl["frame_quantization"]["max_bridge_ms"], "source beyond usable range")
        require(not excess or s.get("tail_frame_bridge_ms") == excess, "unacknowledged frame bridge")
        require(s["take_end_ms"] - s["take_start_ms"] == s["timeline_end_ms"] - s["timeline_start_ms"],
                "duration mismatch")
        cursor = s["timeline_end_ms"]
        if s["performer_visible"]:
            visible += s["timeline_end_ms"] - s["timeline_start_ms"]
    require(cursor == intelligence["programme_duration_ms"], "programme duration")
    require(visible * 5 >= cursor * 4, "80_PERCENT_PERFORMANCE_RULE")
    derivatives = edl.get("derivatives", [])
    require(len(derivatives) <= 4, "maximum derivative rule")
    for d in derivatives:
        require(0 <= d["start_ms"] < d["end_ms"] <= cursor, "derivative range")
        require(d["performer_visible_ms"] * 5 >= (d["end_ms"] - d["start_ms"]) * 4,
                "derivative performance rule")
    result = deepcopy(edl)
    result.update(status="GREEN_MACHINE_READABLE_REAL_ACCEPTANCE", duration_ms=cursor,
                  visible_performance_ms=visible, performance_fraction=visible / cursor)
    result["edl_sha256"] = digest(result)
    return result
