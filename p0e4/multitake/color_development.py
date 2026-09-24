"""Fail-closed validation and measurable QC for private color review passes."""
from __future__ import annotations

import hashlib
from pathlib import Path


STAGES = ["NORMALIZATION", "INTER_TAKE_SHOT_MATCH", "SKIN_EXPOSURE_CONTRAST", "SUBJECT_BACKGROUND_SEPARATION", "BOUNDED_CREATIVE_LOOK"]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_color_contract(contract):
    if contract.get("schema") != "R4_COLOR_DEVELOPMENT_CONTRACT_V01":
        raise ValueError("COLOR_CONTRACT_SCHEMA")
    if contract.get("stage_order") != STAGES:
        raise ValueError("COLOR_STAGE_ORDER")
    preserved = contract.get("preserved_r3", {})
    if not all(preserved.get(k) is True for k in ("framing", "edl", "synchronization", "beat_motion_timing")):
        raise ValueError("R3_EDIT_STATE_NOT_PRESERVED")
    if contract.get("known_r3_defects", {}).get("status") != "CONFIRMED_UNRESOLVED":
        raise ValueError("R3_DEFECT_STATUS")
    for take_id, take in contract.get("takes", {}).items():
        cdl = take.get("cdl", {})
        for key in ("Slope", "Offset", "Power"):
            vals = [float(x) for x in cdl.get(key, "").split()]
            if len(vals) != 3:
                raise ValueError(f"CDL_{key.upper()}:{take_id}")
            lo, hi = {"Slope": (0.88, 1.10), "Offset": (-0.03, 0.03), "Power": (0.90, 1.10)}[key]
            if any(x < lo or x > hi for x in vals):
                raise ValueError(f"CDL_{key.upper()}_BOUNDS:{take_id}")
        sat = float(cdl.get("Saturation", 0))
        if not 0.90 <= sat <= 1.15:
            raise ValueError(f"CDL_SATURATION_BOUNDS:{take_id}")
    separation = contract.get("subject_background_separation", {})
    if separation.get("method") != "SOFT_STATIC_INVERTED_ELLIPSE_FAIL_CLOSED":
        raise ValueError("SEPARATION_METHOD")
    if not 0.90 <= float(separation.get("gain", 0)) <= 1.0 or not 0.82 <= float(separation.get("saturation", 0)) <= 1.0:
        raise ValueError("SEPARATION_BOUNDS")
    return True


def frame_metrics(rgb):
    """Return scope-like numeric measures from rows of RGB byte tuples."""
    if not rgb or not rgb[0] or len(rgb[0][0]) < 3:
        raise ValueError("RGB_FRAME_REQUIRED")
    h, w = len(rgb), len(rgb[0])
    luma, sat, shadow, highlight, subject, edge = [], [], 0, 0, [], []
    for y, row in enumerate(rgb):
        if len(row) != w: raise ValueError("RECTANGULAR_FRAME_REQUIRED")
        for x, pixel in enumerate(row):
            r, g, b = (float(v) / 255 for v in pixel[:3])
            lum = .2126*r + .7152*g + .0722*b
            luma.append(lum); mx, mn = max(r,g,b), min(r,g,b); sat.append((mx-mn)/mx if mx else 0)
            shadow += int(r <= 3/255 and g <= 3/255 and b <= 3/255)
            highlight += int(r >= 252/255 and g >= 252/255 and b >= 252/255)
            if .18*h <= y < .84*h and .22*w <= x < .78*w: subject.append(lum)
            if x < .14*w or x >= .86*w: edge.append(lum)
    def pct(values, p):
        values = sorted(values); pos = (len(values)-1)*p/100; lo = int(pos); hi = min(lo+1,len(values)-1)
        return round(values[lo] + (values[hi]-values[lo])*(pos-lo), 6)
    total = h*w
    return {
        "luma_percentiles": {str(p): pct(luma, p) for p in (1, 5, 50, 95, 99)},
        "rgb_shadow_clip_pct": round(shadow / total * 100, 6),
        "rgb_highlight_clip_pct": round(highlight / total * 100, 6),
        "saturation_percentiles": {str(p): pct(sat, p) for p in (50, 95, 99)},
        "subject_roi_luma_median": pct(subject, 50),
        "background_edge_luma_median": pct(edge, 50),
        "subject_background_luma_delta": round(pct(subject, 50) - pct(edge, 50), 6),
    }


def assess_metrics(rows, limits):
    failures = []
    for row in rows:
        m = row["metrics"]
        if m["rgb_shadow_clip_pct"] > limits["max_shadow_clip_pct"]:
            failures.append({"time_ms": row["time_ms"], "defect": "SHADOW_CLIPPING"})
        if m["rgb_highlight_clip_pct"] > limits["max_highlight_clip_pct"]:
            failures.append({"time_ms": row["time_ms"], "defect": "HIGHLIGHT_CLIPPING"})
        if m["saturation_percentiles"]["99"] > limits["max_saturation_p99"]:
            failures.append({"time_ms": row["time_ms"], "defect": "SATURATION_OUTLIER"})
    return {"status": "GREEN" if not failures else "HOLD", "failures": failures}
