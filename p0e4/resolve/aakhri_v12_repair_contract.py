"""Fail-closed contract helpers for the bounded Aakhri V12 repair.

This module is deliberately independent from Resolve so its asset binding,
visibility-window and decoder gates can be tested off-host.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path


CHAIN_LOGO_URL = (
    "https://storage.googleapis.com/unchained-nitin-media/assets/"
    "unchained_chain_emblem.png"
)
CHAIN_LOGO_SHA256 = "5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509"

# Inclusive output-frame windows. The hook begins only after the intro ends;
# all performance captions end before the flattened outro begins.
VISIBILITY_WINDOWS = {
    "chain_intro": (0, 53),
    "opening_hook": (54, 88),
    "title_artist": (89, 334),
    "outro_card": (600, 719),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_no_forbidden_overlap(windows=VISIBILITY_WINDOWS) -> None:
    forbidden = (
        ("chain_intro", "opening_hook"),
        ("chain_intro", "title_artist"),
        ("outro_card", "opening_hook"),
        ("outro_card", "title_artist"),
    )
    for left, right in forbidden:
        a0, a1 = windows[left]
        b0, b1 = windows[right]
        if max(a0, b0) <= min(a1, b1):
            raise RuntimeError(f"forbidden visibility overlap: {left}/{right}")


def set_or_insert_scalar(block: str, key: str, value: str) -> str:
    """Idempotently set one scalar Fusion Input, rejecting duplicates."""
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+)(, \}},)"
    matches = list(re.finditer(pattern, block))
    if len(matches) > 1:
        raise RuntimeError(f"duplicate {key} inputs")
    if len(matches) == 1:
        return re.sub(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    needle = "\n\t\t\t\tStyledText = Input"
    if needle not in block:
        raise RuntimeError(f"cannot insert {key}")
    return block.replace(
        needle,
        f"\n\t\t\t\t{key} = Input {{ Value = {value}, }}," + needle,
        1,
    )


def restore_property(item, key: str, expected) -> None:
    """Restore a Resolve property and prove its readback.

    Resolve returns ``False`` when SetProperty is asked to set some properties
    to the value they already have.  Treat that documented API quirk as safe
    only when the pre-write readback is already exact; a differing value must
    still be accepted by SetProperty and every path is verified afterward.
    """
    observed = item.GetProperty(key)
    if observed != expected and not item.SetProperty(key, expected):
        raise RuntimeError(f"cannot restore {key}: {observed!r} -> {expected!r}")
    if item.GetProperty(key) != expected:
        raise RuntimeError(f"{key} readback drift")


def resolve_chain_logo(destination: Path) -> Path:
    """Return exact chain-logo bytes, downloading atomically when absent."""
    if destination.exists() and sha256(destination) == CHAIN_LOGO_SHA256:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    if temporary.exists():
        temporary.unlink()
    urllib.request.urlretrieve(CHAIN_LOGO_URL, temporary)
    observed = sha256(temporary)
    if observed != CHAIN_LOGO_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"chain-logo hash mismatch: expected {CHAIN_LOGO_SHA256}, got {observed}"
        )
    os.replace(temporary, destination)
    return destination


def verify_full_decode(path: Path) -> dict:
    """Decode every video frame and the complete audio stream, then probe."""
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"missing render: {path}")
    commands = {
        "video": ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
        "audio": ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "null", "-"],
    }
    results = {}
    for stream, command in commands.items():
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{stream} full decode failed: {completed.stderr[-2000:]}")
        results[stream] = "FULL_DECODE_PASS"
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames", "-show_streams",
            "-show_format", "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {probe.stderr[-2000:]}")
    results["probe"] = json.loads(probe.stdout)
    return results


assert_no_forbidden_overlap()
