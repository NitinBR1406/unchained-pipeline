"""Fail-closed helpers for an explicitly authorized real multi-take acceptance.

The helpers are pure. Filesystem/Drive reads and dispatch remain outside this module.
"""
from __future__ import annotations

from statistics import median

from .factory import digest, require


def content_kind(mime: str, video_tracks: int, audio_tracks: int) -> str:
    """Classify from inspected bytes/tracks, never from the filename."""
    if video_tracks > 0:
        require(mime.startswith("video/"), "video track/MIME disagreement")
        return "TAKE"
    if audio_tracks > 0:
        require(mime.startswith("audio/"), "audio track/MIME disagreement")
        return "MASTER_AUDIO_CANDIDATE"
    if mime.startswith("image/"):
        return "PHOTO"
    return "UNSUPPORTED"


def confidence_rubric(consensus_anchors: list[dict], fit_rmse_ms: float, drift_ppm: float) -> dict:
    """Score alignment evidence on reproducibility, fit and signal separation.

    A raw correlation peak is insufficient by itself. A take must have at least
    five mutually consistent anchors spanning 30 seconds, a <=10 ms regression
    residual, drift within the contract limit, and defensible signal/margin.
    """
    require(len(consensus_anchors) >= 1, "alignment anchors")
    offsets = [int(a["offset_ms"]) for a in consensus_anchors]
    correlations = [float(a["peak_corr"]) for a in consensus_anchors]
    margins = [float(a["peak_margin"]) for a in consensus_anchors]
    times = [int(a["take_time_ms"]) for a in consensus_anchors]
    med_offset = median(offsets)
    mad_ms = median([abs(x - med_offset) for x in offsets])
    span_ms = max(times) - min(times)
    checks = {
        "anchor_redundancy": len(consensus_anchors) >= 5,
        "temporal_span": span_ms >= 30_000,
        "offset_mad": mad_ms <= 10,
        "fit_rmse": float(fit_rmse_ms) <= 10,
        "drift": abs(float(drift_ppm)) <= 80,
        "median_correlation": median(correlations) >= 0.55,
        "median_peak_margin": median(margins) >= 0.05,
    }
    weights = {
        "anchor_redundancy": 200,
        "temporal_span": 150,
        "offset_mad": 150,
        "fit_rmse": 150,
        "drift": 150,
        "median_correlation": 100,
        "median_peak_margin": 100,
    }
    score = sum(weights[k] for k, passed in checks.items() if passed)
    return {
        "schema": "ALIGNMENT_CONFIDENCE_RUBRIC_V01",
        "confidence_milli": score,
        "threshold_milli": 850,
        "checks": checks,
        "weights_milli": weights,
        "metrics": {
            "anchor_count": len(consensus_anchors),
            "anchor_span_ms": span_ms,
            "offset_mad_ms": mad_ms,
            "fit_rmse_ms": float(fit_rmse_ms),
            "drift_ppm": float(drift_ppm),
            "median_peak_corr": round(median(correlations), 6),
            "median_peak_margin": round(median(margins), 6),
        },
        "status": "GREEN" if score >= 850 else "HOLD_LOW_CONFIDENCE",
        "rubric_sha256": digest({"checks": checks, "weights": weights}),
    }


def validate_real_inventory(poll_a: list[dict], poll_b: list[dict], probes: dict[str, dict], expected_audio_sha256: str) -> dict:
    """Validate two complete byte polls for the one authorized workload."""
    stable_fields = ("file_id", "name", "bytes_read", "sha256", "stat_size", "mtime_ns", "file_mime")
    identity = lambda rows: sorted([{k: x[k] for k in stable_fields} for x in rows], key=lambda x: x["file_id"])
    require(identity(poll_a) == identity(poll_b), "source drift between complete polls")
    require(len({x["file_id"] for x in poll_a}) == len(poll_a), "duplicate file ids")
    require(all(x["bytes_read"] == x["stat_size"] > 0 for x in poll_a), "unavailable/incomplete bytes")
    require(all(len(x["sha256"]) == 64 for x in poll_a), "missing sha256")
    require(len({x["sha256"] for x in poll_a}) == len(poll_a), "duplicate content")
    rows = []
    for item in poll_a:
        require(item["name"] in probes, "probe coverage")
        p = probes[item["name"]]
        kind = content_kind(item["file_mime"], int(p.get("video_tracks", 0)), int(p.get("audio_tracks", 0)))
        rows.append({"file_id": item["file_id"], "display_name": item["name"], "bytes": item["bytes_read"],
                     "sha256": item["sha256"], "mime_from_bytes": item["file_mime"], "kind": kind})
    takes = [r for r in rows if r["kind"] == "TAKE"]
    audio = [r for r in rows if r["kind"] == "MASTER_AUDIO_CANDIDATE"]
    require(len(takes) >= 2, "insufficient takes")
    require(len(audio) == 1, "master audio ambiguity")
    require(audio[0]["sha256"] == expected_audio_sha256, "authoritative master mismatch")
    require(all(r["kind"] != "UNSUPPORTED" for r in rows), "unsupported content")
    result = {"schema": "REAL_MULTI_TAKE_INTAKE_ACCEPTANCE_V01", "scope": "AAKHRI_ISHQ_ONLY",
              "stable_complete_polls": 2, "filename_semantics_used": False, "files": rows,
              "take_count": len(takes), "photo_count": len([r for r in rows if r["kind"] == "PHOTO"]),
              "master_audio_sha256": audio[0]["sha256"], "status": "GREEN"}
    result["receipt_sha256"] = digest(result)
    return result
