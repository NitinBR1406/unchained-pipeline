"""Automatic technical media QC via ffprobe (deterministic). Produces TECH_QC_REPORT.json.

Any material failure -> qc_pass False with MUST_FIX issues (caller routes to TECH_QC_FAIL/HOLD).
If ffprobe is unavailable, returns tool_available=False and qc_pass=None (caller must HOLD,
never assume pass).
"""
import json
import shutil
import subprocess
from fractions import Fraction
from .util import write_json, now_iso


def ffprobe_available():
    return shutil.which("ffprobe") is not None


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except Exception:
        return None


def _fps(rate):
    try:
        return float(Fraction(rate))
    except Exception:
        return None


def run_media_qc(path, expected, report_path=None):
    """expected: dict with duration, width, height, fps (and tolerances)."""
    issues = []  # (severity, message)
    report = {"generated_at": now_iso(), "file": str(path), "tool_available": ffprobe_available()}

    if not ffprobe_available():
        report["qc_pass"] = None
        report["issues"] = [["MUST_FIX", "ffprobe not available; cannot verify media -> HOLD"]]
        if report_path:
            write_json(report_path, report)
        return report

    info = probe(path)
    if info is None:
        report["qc_pass"] = False
        report["issues"] = [["MUST_FIX", "file unreadable or ffprobe failed (possibly truncated)"]]
        if report_path:
            write_json(report_path, report)
        return report

    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = info.get("format", {})
    dur = float(fmt.get("duration", 0) or 0)
    w, h = v.get("width"), v.get("height")
    fps = _fps(v.get("r_frame_rate", "0/1"))

    probe_summary = {
        "container": fmt.get("format_name"),
        "duration": dur,
        "width": w, "height": h,
        "frame_rate": v.get("r_frame_rate"), "fps": fps,
        "video_codec": v.get("codec_name"),
        "audio_codec": a.get("codec_name"),
        "audio_sample_rate": a.get("sample_rate"),
        "audio_channels": a.get("channels"),
        "audio_duration": a.get("duration"),
        "video_present": bool(v),
        "audio_present": bool(a),
    }
    report["probe"] = probe_summary

    # ---- gates
    if not v:
        issues.append(["MUST_FIX", "no video stream"])
    if not a:
        issues.append(["MUST_FIX", "no audio stream"])
    tol = expected.get("duration_tol", 0.5)
    if expected.get("duration") is not None and abs(dur - expected["duration"]) > tol:
        issues.append(["MUST_FIX", f"duration {dur:.3f}s != expected {expected['duration']}s (tol {tol})"])
    if expected.get("width") and w != expected["width"]:
        issues.append(["MUST_FIX", f"width {w} != {expected['width']}"])
    if expected.get("height") and h != expected["height"]:
        issues.append(["MUST_FIX", f"height {h} != {expected['height']}"])
    if expected.get("fps") and fps and abs(fps - expected["fps"]) > 0.05:
        issues.append(["MUST_FIX", f"fps {fps} != {expected['fps']}"])
    # audio continuity (best-effort): audio duration close to container duration
    ad = a.get("duration")
    if ad:
        try:
            if abs(float(ad) - dur) > 1.0:
                issues.append(["MATERIAL_IMPROVEMENT", f"audio duration {ad} differs from video {dur:.3f}"])
        except Exception:
            pass

    must_fix = [i for i in issues if i[0] == "MUST_FIX"]
    report["issues"] = issues
    report["qc_pass"] = len(must_fix) == 0
    if report_path:
        write_json(report_path, report)
    return report
