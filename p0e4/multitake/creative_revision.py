"""Reusable contracts for evidence-bound multi-take creative revisions."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pcm_to_float(raw: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        value = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        value = np.where(value & 0x800000, value - 0x1000000, value)
        return value.astype(np.float32) / 8388608.0
    raise ValueError("UNSUPPORTED_PCM_WIDTH")


def analyze_authoritative_audio(path: Path, *, max_accents: int = 14, minimum_spacing_ms: int = 3500) -> dict:
    """Derive bounded onset/energy intelligence without lyrics or semantic guesses."""
    with wave.open(str(path), "rb") as source:
        rate, channels, width = source.getframerate(), source.getnchannels(), source.getsampwidth()
        raw = source.readframes(source.getnframes())
        frame_count = source.getnframes()
    signal = _pcm_to_float(raw, width).reshape(-1, channels).mean(axis=1)
    hop = max(1, int(rate * 0.02))
    usable = len(signal) // hop * hop
    rms = np.sqrt(np.mean(signal[:usable].reshape(-1, hop) ** 2, axis=1) + 1e-12)
    smooth = np.convolve(rms, np.ones(5, dtype=np.float32) / 5.0, mode="same")
    onset = np.maximum(np.diff(smooth, prepend=smooth[0]), 0)
    if onset.max() > 0:
        onset = onset / onset.max()
    threshold = float(max(0.12, np.quantile(onset, 0.82)))
    candidates = [i for i in range(1, len(onset) - 1) if onset[i] >= threshold and onset[i] >= onset[i - 1] and onset[i] >= onset[i + 1]]
    ranked = sorted(candidates, key=lambda i: float(onset[i]), reverse=True)
    chosen: list[int] = []
    min_gap = max(1, int(minimum_spacing_ms / 20))
    for index in ranked:
        if all(abs(index - prior) >= min_gap for prior in chosen):
            chosen.append(index)
        if len(chosen) >= max_accents:
            break
    chosen.sort()
    lo, hi = float(np.quantile(smooth, 0.30)), float(np.quantile(smooth, 0.75))
    events = []
    for index in chosen:
        energy = float(smooth[index])
        zone = "QUIET" if energy <= lo else "PEAK" if energy >= hi else "BUILD"
        strength = round(float(onset[index]), 4)
        motion = "GENTLE_PUSH" if zone == "QUIET" else "PUNCH_IN" if strength < 0.72 else "PUNCH_IN_MICRO_SHAKE"
        events.append({"time_ms": int(round(index * hop * 1000 / rate)), "onset_strength": strength, "energy_zone": zone, "motion": motion})
    duration_ms = int(round(frame_count * 1000 / rate))
    sections = []
    section_ms = 30000
    for start in range(0, duration_ms, section_ms):
        a = int(start / 20); b = min(len(smooth), int((start + section_ms) / 20))
        value = float(np.mean(smooth[a:b])) if b > a else 0.0
        zone = "QUIET" if value <= lo else "PEAK" if value >= hi else "BUILD"
        sections.append({"start_ms": start, "end_ms": min(duration_ms, start + section_ms), "energy_zone": zone, "mean_rms": round(value, 6)})
    return {
        "schema": "BEAT_SECTION_MOTION_INTELLIGENCE_V01",
        "audio_sha256": sha256(path),
        "analysis": {"sample_rate": rate, "channels": channels, "sample_width_bytes": width, "hop_ms": 20, "method": "RMS_ONSET_AND_ENERGY_ONLY", "lyrics_or_semantics_inferred": False},
        "duration_ms": duration_ms,
        "events": events,
        "sections": sections,
        "restraint": {"maximum_accents": max_accents, "minimum_spacing_ms": minimum_spacing_ms, "quiet_passage_shakes_allowed": False, "maximum_motion_scale": 1.035, "maximum_shake_offset": 0.004},
    }


def validate_revision_contract(contract: dict) -> None:
    if contract.get("schema") != "MULTI_TAKE_CREATIVE_REVISION_CONTRACT_V01":
        raise ValueError("SCHEMA")
    if not contract.get("base_framing_precedes_motion"):
        raise ValueError("FRAMING_ORDER")
    if set(contract.get("takes", {})) != set(contract.get("expected_take_ids", [])):
        raise ValueError("TAKE_COVERAGE")
    for take in contract["takes"].values():
        if take["base_scale"] < contract["limits"]["minimum_safe_base_scale"]:
            raise ValueError("UNSAFE_BASE_SCALE")
    if contract["look"]["background_deemphasis"]["method"] != "SOFT_STATIC_SUBJECT_REGION_INVERTED_MASK":
        raise ValueError("LOOK_METHOD")
    if contract["motion"]["source"] != "AUTHORITATIVE_MASTER_AUDIO_ONLY":
        raise ValueError("MOTION_SOURCE")


def dump_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
