"""Read back clip-level framing from the accepted-base and V07 projects."""

import json
from pathlib import Path

import DaVinciResolveScript as d


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-base-crop-v08"
OUT.mkdir(parents=True, exist_ok=True)
PROJECTS = [
    "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V04_REPAIR2",
    "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V05_LIPSYNC",
    "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V06_SOURCE_TAKE_SYNC",
    "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC",
]
KEYS = ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "AnchorPointX", "AnchorPointY", "CropLeft", "CropRight", "CropTop", "CropBottom", "DynamicZoomEase", "CompositeMode", "Opacity"]

resolve = d.scriptapp("Resolve")
assert resolve
manager = resolve.GetProjectManager()
result = {}
for name in PROJECTS:
    project = manager.LoadProject(name)
    if not project:
        result[name] = {"available": False}
        continue
    timeline = project.GetCurrentTimeline()
    origin = timeline.GetStartFrame()
    clips = timeline.GetItemListInTrack("video", 1)
    result[name] = {
        "available": True,
        "timeline": timeline.GetName(),
        "clips": [
            {
                "name": clip.GetName(),
                "timeline_frames": [clip.GetStart() - origin, clip.GetEnd() - origin],
                "source_frames": [clip.GetSourceStartFrame(), clip.GetSourceEndFrame()],
                "properties": {key: clip.GetProperty(key) for key in KEYS},
            }
            for clip in clips
        ],
    }

path = OUT / "BASE_FRAMING_PROJECT_COMPARISON_V01.json"
path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
