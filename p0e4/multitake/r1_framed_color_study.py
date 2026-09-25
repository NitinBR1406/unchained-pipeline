"""Fail-closed contract helpers for the framed R1 HLG color study."""
from __future__ import annotations

import colorsys
import hashlib
import json
from pathlib import Path


VARIANTS = (
    "R1_BASELINE",
    "R1_CALMER_BACKGROUND",
    "R1_CALMER_BACKGROUND_RICHER_SUBJECT",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_contract(contract: dict) -> None:
    assert contract["schema"] == "R1_FRAMED_HLG_EXECUTION_CONTRACT_V01"
    assert contract["variant_order"] == list(VARIANTS)
    assert contract["segment_seconds"] >= 5 and contract["segment_seconds"] <= 8
    assert len(contract["representative_scenes"]) == 4
    assert contract["full_master_allowed"] is False
    assert contract["creative_winner_selected"] is False
    assert contract["color_management"] == {
        "input": "Rec.2100 HLG", "timeline": "Rec.2100 HLG",
        "output": "Rec.2100 HLG", "tone_mapping": "None", "gamut_mapping": "None",
    }
    assert contract["forbidden"] == [
        "REC709_CONVERSION", "STATIC_SPATIAL_MASK", "BLUR", "SKIN_SMOOTHING",
        "FACE_MANIPULATION", "GENERATIVE_PROCESSING", "FULL_MASTER_RENDER",
    ]


def _smoothstep(a: float, b: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _gamut_safe(luma: float, chroma: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    limit = scale
    for c in chroma:
        if c > 0:
            limit = min(limit, (1.0 - luma) / c)
        elif c < 0:
            limit = min(limit, (0.0 - luma) / c)
    scale = max(0.0, min(scale, limit * 0.995))
    return tuple(max(0.0, min(1.0, luma + c * scale)) for c in chroma)


def transform(rgb: tuple[float, float, float], variant: str) -> tuple[float, float, float]:
    """Bounded hue/chroma transform in encoded HLG RGB; luma remains constant."""
    if variant not in VARIANTS:
        raise ValueError("VARIANT")
    r, g, b = rgb
    y = 0.2627 * r + 0.6780 * g + 0.0593 * b
    c = (r - y, g - y, b - y)
    sat = max(rgb) - min(rgb)
    h, _, _ = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360.0
    warm_distance = min(abs(hue - 28.0), 360.0 - abs(hue - 28.0))
    skin = (1.0 - _smoothstep(22.0, 58.0, warm_distance)) * _smoothstep(0.035, 0.14, sat) * (1.0 - _smoothstep(0.82, 0.98, y))
    neutral_background = 1.0 - _smoothstep(0.07, 0.28, sat)
    scale = 1.035
    if variant != "R1_BASELINE":
        scale -= 0.075 * neutral_background
    if variant == "R1_CALMER_BACKGROUND_RICHER_SUBJECT":
        scale += 0.075 * skin
    return _gamut_safe(y, c, scale)


def write_cube(path: Path, variant: str, size: int = 33) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'TITLE "UNCHAINED {variant}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                out = transform((r/(size-1), g/(size-1), b/(size-1)), variant)
                lines.append("%.9f %.9f %.9f" % out)
    path.write_text("\n".join(lines) + "\n")
    return {"path": str(path), "sha256": sha256(path), "size": size, "variant": variant,
            "spatial_mask": False, "blur": False, "luma_formula": "BT2020_ENCODED_WEIGHTS",
            "operation": "BOUNDED_HUE_CHROMA_3D_LUT"}


def load(path: Path) -> dict:
    data = json.loads(Path(path).read_text())
    validate_contract(data)
    return data
