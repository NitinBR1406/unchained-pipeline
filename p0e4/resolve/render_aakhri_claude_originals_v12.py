"""Bind the proven Claude intro logo and flattened outro card to V12."""

import hashlib
import json
import time
from pathlib import Path

import DaVinciResolveScript as d

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-v12-claude-originals"
PROJECT = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V12_CLAUDE_ORIGINALS"
INTRO = OUT / "ORIGINAL_unchained_nitin_logo_320.png"
OUTRO = ROOT / "p0e4/evidence/claude_edit_posting_handoff_review_v01_execution/ORIGINAL_visualizer_outro.png"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


resolve = d.scriptapp("Resolve")
assert resolve and INTRO.exists() and OUTRO.exists()
manager = resolve.GetProjectManager()
project = manager.LoadProject(PROJECT)
assert project and not project.IsRenderingInProgress()
timeline = project.GetCurrentTimeline()
origin = timeline.GetStartFrame()
pool = project.GetMediaPool()
while timeline.GetTrackCount("video") < 2:
    assert timeline.AddTrack("video")

# Idempotent disposable execution: remove only prior V12 overlay clips.
prior = timeline.GetItemListInTrack("video", 2)
if prior:
    assert timeline.DeleteClips(prior, False)

imports = pool.ImportMedia([str(INTRO), str(OUTRO)])
by_name = {item.GetName(): item for item in imports}
intro_item = by_name[INTRO.name]
outro_item = by_name[OUTRO.name]

intro = pool.AppendToTimeline([{
    "mediaPoolItem": intro_item, "startFrame": 0, "endFrame": 53,
    "mediaType": 1, "trackIndex": 2, "recordFrame": origin,
}])[0]
assert intro.SetProperty("ZoomX", 0.55)
assert intro.SetProperty("ZoomY", 0.55)
assert intro.SetProperty("Tilt", 420.0)

outro = pool.AppendToTimeline([{
    "mediaPoolItem": outro_item, "startFrame": 0, "endFrame": 119,
    "mediaType": 1, "trackIndex": 2, "recordFrame": origin + 600,
}])[0]

assert manager.SaveProject()
drp = OUT / f"{PROJECT}.drp"
assert manager.ExportProject(PROJECT, str(drp), False)
render = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V12_CLAUDE_ORIGINALS_HLG_PRORES.mov"
assert resolve.OpenPage("deliver")
assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetCurrentRenderMode(1)
assert project.SetRenderSettings({
    "SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + 719,
    "TargetDir": str(OUT), "CustomName": render.stem,
    "ExportVideo": True, "ExportAudio": True,
    "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
    "AudioCodec": "lpcm", "AudioSampleRate": 48000,
})
job = project.AddRenderJob(); assert job
assert project.StartRendering([job], False)
deadline = time.monotonic() + 1800
while project.IsRenderingInProgress() and time.monotonic() < deadline:
    time.sleep(0.5)
assert not project.IsRenderingInProgress()
status = project.GetRenderJobStatus(job)
assert status.get("JobStatus") == "Complete" and render.exists(), status
project.DeleteRenderJob(job)

receipt = {
    "schema": "RESOLVE_CLAUDE_ORIGINAL_INTRO_OUTRO_V12",
    "project": PROJECT,
    "timeline": timeline.GetName(),
    "rendered_frames": [0, 719],
    "intro": {"frames": [0, 53], "sha256": sha256(INTRO), "source_sha256": "9ec0183958eebed15e262202918db201bcd669e0d4975c7385ec88ecbc20805d"},
    "outro": {"frames": [600, 719], "sha256": sha256(OUTRO), "exact_wording": ["UNCHAINED NITIN", "~ THE INDESTRUCTIBLE VOICE ~", "FOLLOW FOR MORE", "@UnchainedNitin"]},
    "render": {"path": str(render), "sha256": sha256(render), "bytes": render.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
    "publication_authorized": False,
}
(OUT / "RESOLVE_CLAUDE_ORIGINAL_INTRO_OUTRO_V12.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
