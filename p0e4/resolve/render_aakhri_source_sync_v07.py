"""Render the bounded Aakhri Ishq V07 source-take lipsync repair.

The edit, motion, captions, colour, branding, programme audio, and ending remain
unchanged.  Only video source frames are replaced with contiguous frames from
the independently selected IMG_5739 performance take at its guide-audio
baseline.  Resolve must be running and idle.
"""

import hashlib
import json
import time
from pathlib import Path

import DaVinciResolveScript as d


BASE = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V06_SOURCE_TAKE_SYNC"
NEW = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-lipsync-v07"
OUT.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


resolve = d.scriptapp("Resolve")
assert resolve
manager = resolve.GetProjectManager()
project = manager.LoadProject(BASE)
assert project and not project.IsRenderingInProgress()
baseline_drp = OUT / f"{BASE}.drp"
assert manager.SaveProject()
assert manager.ExportProject(BASE, str(baseline_drp), False)
assert manager.CloseProject(project)
if NEW in manager.GetProjectListInCurrentFolder():
    raise RuntimeError(f"isolated project already exists: {NEW}")
assert manager.ImportProject(str(baseline_drp), NEW)
project = manager.LoadProject(NEW)
assert project
timeline = project.GetCurrentTimeline()
origin = timeline.GetStartFrame()
clips = timeline.GetItemListInTrack("video", 1)
assert len(clips) == 6
assert [(clip.GetStart() - origin, clip.GetEnd() - origin) for clip in clips] == [
    (0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)
]

mpi_5739 = next(clip.GetMediaPoolItem() for clip in clips if clip.GetName() == "IMG_5739.MOV")
assert mpi_5739

# Contiguous guide-baseline source frames for master interval 72.000-96.000 s.
# Diagnostic evidence selected IMG_5739 as the closer performance. V06's
# one-frame delay produced a residual lag in exact-output QC, so V07 returns to
# the evidence-bound baseline without moving programme audio.
source_ranges = [(2144, 2233), (2233, 2348), (2348, 2479),
                 (2479, 2635), (2635, 2767), (2767, 2864)]

saved = []
for index, clip in enumerate(clips):
    comp_path = OUT / f"clip_{index:02d}_fusion.comp"
    assert clip.ExportFusionComp(str(comp_path), 1)
    saved.append({
        "timeline_start": clip.GetStart() - origin,
        "timeline_end": clip.GetEnd() - origin,
        "before_take": clip.GetName(),
        "before_source": [clip.GetSourceStartFrame(), clip.GetSourceEndFrame()],
        "comp": comp_path,
        "lut": clip.GetLUT(1),
    })

assert timeline.DeleteClips(clips, False)
pool = project.GetMediaPool()
repairs = []
for old, (source_start, source_end) in zip(saved, source_ranges):
    appended = pool.AppendToTimeline([{
        "mediaPoolItem": mpi_5739,
        "startFrame": source_start,
        "endFrame": source_end,
        "mediaType": 1,
        "trackIndex": 1,
        "recordFrame": origin + old["timeline_start"],
    }])
    assert len(appended) == 1
    item = appended[0]
    assert item.ImportFusionComp(str(old["comp"]))
    assert item.SetLUT(1, old["lut"])
    assert (item.GetStart() - origin, item.GetEnd() - origin) == (
        old["timeline_start"], old["timeline_end"])
    assert (item.GetSourceStartFrame(), item.GetSourceEndFrame()) == (source_start, source_end)
    repairs.append({
        "timeline_frames": [old["timeline_start"], old["timeline_end"]],
        "before_take": old["before_take"],
        "before_source_frames": old["before_source"],
        "after_take": item.GetName(),
        "after_source_frames": [source_start, source_end],
    })

assert manager.SaveProject()
drp = OUT / f"{NEW}.drp"
assert manager.ExportProject(NEW, str(drp), False)

prores = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC_HLG_PRORES.mov"
assert resolve.OpenPage("deliver")
assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetCurrentRenderMode(1)
assert project.SetRenderSettings({
    "SelectAllFrames": False,
    "MarkIn": origin,
    "MarkOut": origin + 620,
    "TargetDir": str(OUT),
    "CustomName": prores.stem,
    "ExportVideo": True,
    "ExportAudio": True,
    "FormatWidth": 1080,
    "FormatHeight": 1920,
    "FrameRate": 30,
    "AudioCodec": "lpcm",
    "AudioSampleRate": 48000,
})
job = project.AddRenderJob()
assert job
assert project.StartRendering([job], False)
deadline = time.monotonic() + 1800
while project.IsRenderingInProgress() and time.monotonic() < deadline:
    time.sleep(0.5)
assert not project.IsRenderingInProgress()
status = project.GetRenderJobStatus(job)
assert status.get("JobStatus") == "Complete" and prores.exists(), status
project.DeleteRenderJob(job)

receipt = {
    "schema": "RESOLVE_SOURCE_TAKE_LIPSYNC_REPAIR_V07",
    "project": NEW,
    "baseline_project": BASE,
    "timeline": timeline.GetName(),
    "rendered_frames": [0, 620],
    "selected_take": "IMG_5739.MOV",
    "selected_take_sha256": "8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971",
    "source_repairs": repairs,
    "programme_audio_shift_ms": 0,
    "audio_time_stretch": False,
    "timeline_cuts_changed": False,
    "fusion_motion_changed": False,
    "captions_branding_colour_ending_changed": False,
    "prores": {"path": str(prores), "sha256": sha256(prores), "bytes": prores.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
}
(OUT / "RESOLVE_LIPSYNC_V07.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
