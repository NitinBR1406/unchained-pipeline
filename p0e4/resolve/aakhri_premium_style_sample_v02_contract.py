"""Fail-closed contract for the bounded V13 premium-style sample."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REQUEST_ID = "UNCHAINED_PREMIUM_STYLE_SAMPLE_20260929_V02"
BASE_PROJECT = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR"
CHAIN_LOGO_SHA256 = "5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509"
SAMPLE_FRAMES = (0, 179)
WINDOWS = {
    "logo": (0, 53),
    "hook": (54, 88),
    "title_artist": (89, 179),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_windows(windows=WINDOWS) -> None:
    ordered = sorted((start, end, name) for name, (start, end) in windows.items())
    for start, end, name in ordered:
        if start < SAMPLE_FRAMES[0] or end > SAMPLE_FRAMES[1] or start > end:
            raise RuntimeError(f"invalid {name} window")
    for left, right in zip(ordered, ordered[1:]):
        if left[1] >= right[0]:
            raise RuntimeError(f"overlap: {left[2]}/{right[2]}")


def verify_decode(path: Path) -> dict:
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"missing sample: {path}")
    result = {}
    ffmpeg = shutil.which("ffmpeg") or "/Users/nitinramdaras/ffbin/ffmpeg"
    ffprobe = shutil.which("ffprobe") or "/Users/nitinramdaras/ffbin/ffprobe"
    for stream in ("v:0", "a:0"):
        completed = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-map", f"0:{stream}", "-f", "null", "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"decode failed for {stream}: {completed.stderr[-1000:]}")
        result[stream] = "FULL_DECODE_PASS"
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    result["probe"] = json.loads(probe.stdout)
    return result


validate_windows()
