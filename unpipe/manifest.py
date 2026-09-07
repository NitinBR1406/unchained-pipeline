"""Campaign manifest loader/validator. Canonical format: JSON (YAML supported if PyYAML present).

Generic across covers/originals — no Aakhri-Ishq values baked into pipeline logic.
"""
from pathlib import Path
from .util import read_json

REQUIRED = ["campaign_id", "artist", "song_title", "release_type", "source_master",
            "duration", "aspect_ratio", "fps", "presentation_preset", "brand_profile",
            "platform_targets"]


def load_manifest(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml  # optional
            data = yaml.safe_load(p.read_text())
        except Exception as e:
            raise RuntimeError(f"YAML manifest needs PyYAML ({e}); use campaign.json instead.")
    else:
        data = read_json(p)
    validate_manifest(data)
    return data


def validate_manifest(data):
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"manifest missing required fields: {missing}")
    return True
