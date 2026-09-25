"""Contract helpers for the selected V03 HLG color consistency review."""
from __future__ import annotations
import json
from pathlib import Path

WINDOWS = ((8000,24000),(72000,96000),(108000,130000))

def load(path):
    data=json.loads(Path(path).read_text())
    assert data["schema"]=="V03_COLOR_CONSISTENCY_CONTRACT_V01"
    assert tuple(tuple(x) for x in data["timeline_windows_ms"])==WINDOWS
    assert data["full_master_allowed"] is False
    assert data["creative_motion_enabled"] is False
    assert data["programme_audio_sha256"]=="670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2"
    assert data["color_management"]=={"input":"Rec.2100 HLG","timeline":"Rec.2100 HLG","output":"Rec.2100 HLG","tone_mapping":"None","gamut_mapping":"None"}
    return data
