"""Render V08 with source-aware ceiling-free base framing.

V07 proved the source-take lipsync repair but imported take-specific Fusion
geometry after replacing every picture clip with IMG_5739.  This renderer
keeps V07's exact source ranges, cuts, audio, captions, colour and motion.  It
normalises only compositions that still carry IMG_5741's base geometry to the
already established IMG_5739 base (center 0.5/0.72, size 2.3).  Animated size
values and their spline handles are scaled proportionally, preserving the
relative musical motion while ensuring recovery never falls below the safe
base.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import DaVinciResolveScript as d


BASE = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V06_SOURCE_TAKE_SYNC"
NEW = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V08_CEILING_FREE_BASE"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-ceiling-free-v08"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE_SHA = "8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971"
SAFE_CENTER = (0.5, 0.72)
SAFE_BASE = 2.3
OLD_BASE = 2.02
SCALE_FACTOR = SAFE_BASE / OLD_BASE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def n(value: float) -> str:
    return f"{value:.14f}".rstrip("0").rstrip(".")


def patch_source_geometry(source: Path, destination: Path) -> dict:
    text = source.read_text(encoding="utf-8")
    center_old = "Center = Input { Value = { 0.5, 0.49 }, },"
    center_new = "Center = Input { Value = { 0.5, 0.72 }, },"
    if text.count(center_old) != 1:
        raise RuntimeError(f"unexpected old center count in {source}")
    text = text.replace(center_old, center_new, 1)
    marker = "UN_CONTINUOUS_RHYTHM_V03Size = BezierSpline {"
    start = text.index(marker)
    end = text.index("\n\t\t},", start) + len("\n\t\t},")
    block = text[start:end]
    before_values = []
    after_values = []

    def patch_line(match: re.Match) -> str:
        line = match.group(0)

        def main_value(m: re.Match) -> str:
            value = float(m.group(2)); before_values.append(value)
            scaled = value * SCALE_FACTOR; after_values.append(scaled)
            return m.group(1) + n(scaled)

        line = re.sub(r"(\]\s*=\s*\{\s*)(-?\d+(?:\.\d+)?)", main_value, line, count=1)

        def handle_value(m: re.Match) -> str:
            return m.group(1) + n(float(m.group(2)) * SCALE_FACTOR) + m.group(3)

        line = re.sub(r"((?:LH|RH)\s*=\s*\{\s*-?\d+(?:\.\d+)?,\s*)(-?\d+(?:\.\d+)?)(\s*\})", handle_value, line)
        return line

    patched = re.sub(r"^\s*\[-?\d+\].*$", patch_line, block, flags=re.MULTILINE)
    if not before_values or abs(min(before_values) - OLD_BASE) > 1e-9:
        raise RuntimeError(f"unexpected base scale in {source}: {min(before_values) if before_values else None}")
    text = text[:start] + patched + text[end:]
    destination.write_text(text, encoding="utf-8")
    return {
        "old_center": [0.5, 0.49], "new_center": list(SAFE_CENTER),
        "old_min_size": min(before_values), "new_min_size": min(after_values),
        "old_max_size": max(before_values), "new_max_size": max(after_values),
        "scale_factor": SCALE_FACTOR,
    }


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
expected_timeline = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
assert [(clip.GetStart() - origin, clip.GetEnd() - origin) for clip in clips] == expected_timeline
mpi_5739 = next(clip.GetMediaPoolItem() for clip in clips if clip.GetName() == "IMG_5739.MOV")
assert mpi_5739
source_ranges = [(2144, 2233), (2233, 2348), (2348, 2479),
                 (2479, 2635), (2635, 2767), (2767, 2864)]

saved = []
for index, clip in enumerate(clips):
    original = OUT / f"clip_{index:02d}_original.comp"
    assert clip.ExportFusionComp(str(original), 1)
    selected = original
    geometry = {"changed": False}
    if index in (0, 2, 4):
        selected = OUT / f"clip_{index:02d}_img5739_safe.comp"
        geometry = {"changed": True, **patch_source_geometry(original, selected)}
    saved.append({
        "timeline_start": clip.GetStart() - origin,
        "timeline_end": clip.GetEnd() - origin,
        "before_take": clip.GetName(),
        "before_source": [clip.GetSourceStartFrame(), clip.GetSourceEndFrame()],
        "comp": selected,
        "comp_sha256": sha256(selected),
        "geometry": geometry,
        "lut": clip.GetLUT(1),
    })

assert timeline.DeleteClips(clips, False)
pool = project.GetMediaPool()
repairs = []
for index, (old, (source_start, source_end)) in enumerate(zip(saved, source_ranges)):
    appended = pool.AppendToTimeline([{
        "mediaPoolItem": mpi_5739, "startFrame": source_start, "endFrame": source_end,
        "mediaType": 1, "trackIndex": 1, "recordFrame": origin + old["timeline_start"],
    }])
    assert len(appended) == 1
    item = appended[0]
    assert item.ImportFusionComp(str(old["comp"]))
    assert item.SetLUT(1, old["lut"])
    assert (item.GetStart() - origin, item.GetEnd() - origin) == (old["timeline_start"], old["timeline_end"])
    assert (item.GetSourceStartFrame(), item.GetSourceEndFrame()) == (source_start, source_end)
    readback = OUT / f"clip_{index:02d}_readback.comp"
    assert item.ExportFusionComp(str(readback), 1)
    readback_text = readback.read_text(encoding="utf-8")
    assert "Center = Input { Value = { 0.5, 0.72 }, }," in readback_text
    assert "Center = Input { Value = { 0.5, 0.49 }, }," not in readback_text
    repairs.append({
        "timeline_frames": [old["timeline_start"], old["timeline_end"]],
        "before_take": old["before_take"], "after_take": item.GetName(),
        "before_source_frames": old["before_source"],
        "after_source_frames": [source_start, source_end],
        "geometry": old["geometry"], "readback_comp_sha256": sha256(readback),
    })

assert manager.SaveProject()
drp = OUT / f"{NEW}.drp"
assert manager.ExportProject(NEW, str(drp), False)
prores = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V08_CEILING_FREE_BASE_HLG_PRORES.mov"
assert resolve.OpenPage("deliver")
assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetCurrentRenderMode(1)
assert project.SetRenderSettings({
    "SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + 620,
    "TargetDir": str(OUT), "CustomName": prores.stem,
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
assert status.get("JobStatus") == "Complete" and prores.exists(), status
project.DeleteRenderJob(job)

receipt = {
    "schema": "RESOLVE_SOURCE_AWARE_BASE_FRAMING_REPAIR_V08",
    "project": NEW, "baseline_project": BASE, "timeline": timeline.GetName(),
    "rendered_frames": [0, 620], "selected_take": "IMG_5739.MOV",
    "selected_take_sha256": SOURCE_SHA, "source_repairs": repairs,
    "safe_base_contract": {"center": list(SAFE_CENTER), "minimum_size": SAFE_BASE},
    "programme_audio_shift_ms": 0, "audio_time_stretch": False,
    "timeline_cuts_changed": False, "relative_fusion_motion_changed": False,
    "captions_branding_colour_ending_changed": False,
    "prores": {"path": str(prores), "sha256": sha256(prores), "bytes": prores.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
}
(OUT / "RESOLVE_CEILING_FREE_V08.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
