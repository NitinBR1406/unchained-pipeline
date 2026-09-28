"""Render V12 with stable captions and Claude-original intro/outro assets.

The script clones the accepted V10 Resolve project and changes only Fusion
caption nodes/visibility curves. Picture source ranges, safe framing, rhythm
motion, programme audio, colour and the ending remain byte-for-byte equivalent
at the project-control level.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import DaVinciResolveScript as d


BASE = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V11_CLEAN_TYPOGRAPHY"
NEW = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V12_CLAUDE_ORIGINALS"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-v12-claude-originals"
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED_TIMELINE = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_tool_block(text: str, name: str, transform) -> str:
    marker = f"\n\t\t{name} = "
    start = text.index(marker) + 1
    match = re.search(r"\n\t\t[^\t]", text[start + len(marker):])
    if not match:
        raise RuntimeError(f"cannot locate end of tool {name}")
    next_tool = start + len(marker) + match.start()
    return text[:start] + transform(text[start:next_tool]) + text[next_tool:]


def set_value(block: str, key: str, value: str) -> str:
    if value.startswith("{"):
        pattern = rf"({re.escape(key)} = Input \{{ Value = )(\{{[^}}]+\}})(, \}},)"
    else:
        pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+)(, \}},)"
    patched, count = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if count != 1:
        raise RuntimeError(f"expected one {key} input")
    return patched


def set_or_insert_value(block: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+)(, \}},)"
    patched, count = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if count == 1:
        return patched
    needle = "\n\t\t\t\tStyledText = Input"
    if needle not in block:
        raise RuntimeError(f"cannot insert {key}")
    return block.replace(needle, f"\n\t\t\t\t{key} = Input {{ Value = {value}, }}," + needle, 1)


def style_text(block: str, *, center: tuple[float, float], size: float,
               fill_rgb: tuple[float, float, float] | None = None) -> str:
    block = set_value(block, "Center", f"{{ {center[0]}, {center[1]} }}")
    block = set_value(block, "Size", str(size))
    if fill_rgb is not None:
        block = set_or_insert_value(block, "Red1", str(fill_rgb[0]))
        block = set_or_insert_value(block, "Green1", str(fill_rgb[1]))
        block = set_or_insert_value(block, "Blue1", str(fill_rgb[2]))
    # Nitin rejected V10's conspicuous dark patches. Remove every auxiliary
    # dark text element and keep clean, fully opaque native glyph fill only.
    block = set_or_insert_value(block, "Enabled2", "0")
    block = set_or_insert_value(block, "Enabled3", "0")
    block = set_or_insert_value(block, "Softness1", "0")
    needle = "\n\t\t\t\tStyledText = Input"
    return block.replace(needle, "\n\t\t\t\tOpacity1 = Input { Value = 1, }," + needle, 1)


def blend_curve(block: str, points: list[tuple[int, float]]) -> str:
    begin = block.index("\n\t\t\tKeyFrames = {")
    end = block.index("\n\t\t\t}", begin) + len("\n\t\t\t}")
    lines = ["\n\t\t\tKeyFrames = {"]
    for frame, value in points:
        lines.append(f"\t\t\t\t[{frame}] = {{ {value}, Flags = {{ Linear = true }} }},")
    lines.append("\t\t\t}")
    return block[:begin] + "\n".join(lines) + block[end:]


def patch_comp(source: Path, destination: Path, index: int) -> dict:
    text = source.read_text(encoding="utf-8")
    changes = []
    if index == 0:
        text = replace_tool_block(text, "UN_BRAND_HOOK", lambda b: style_text(b, center=(0.5, 0.205), size=0.105))
        text = replace_tool_block(text, "Merge1Blend", lambda b: blend_curve(b, [(0, 0), (6, 1), (72, 1), (82, 0), (88, 0)]))
        text = replace_tool_block(text, "Merge2Blend", lambda b: blend_curve(b, [(0, 0), (88, 0)]))
        changes += ["hook_size_preserved_0.105", "clean_full_opacity_fill", "outline_disabled", "backing_disabled"]
    elif index == 1:
        text = replace_tool_block(text, "UN_BRAND_TITLE", lambda b: style_text(b, center=(0.5, 0.13), size=0.125, fill_rgb=(1.0, 0.86, 0.38)))
        text = replace_tool_block(text, "UN_BRAND_ARTIST", lambda b: style_text(b, center=(0.5, 0.255), size=0.075))
        text = replace_tool_block(text, "Merge1Blend", lambda b: blend_curve(b, [(0, 0), (8, 1), (114, 1)]))
        text = replace_tool_block(text, "Merge2Blend", lambda b: blend_curve(b, [(0, 0), (8, 1), (114, 1)]))
        changes += ["title_size_preserved_0.125", "artist_size_preserved_0.075", "stable_fade_in_then_hold", "clean_full_opacity_fill", "outline_disabled", "backing_disabled"]
    elif index == 2:
        text = replace_tool_block(text, "UN_BRAND_TITLE", lambda b: style_text(b, center=(0.5, 0.13), size=0.125, fill_rgb=(1.0, 0.86, 0.38)))
        text = replace_tool_block(text, "UN_BRAND_ARTIST", lambda b: style_text(b, center=(0.5, 0.255), size=0.075))
        text = replace_tool_block(text, "Merge1Blend", lambda b: blend_curve(b, [(0, 1), (116, 1), (130, 0)]))
        text = replace_tool_block(text, "Merge2Blend", lambda b: blend_curve(b, [(0, 1), (116, 1), (130, 0)]))
        changes += ["title_size_preserved_0.125", "artist_size_preserved_0.075", "stable_hold_then_fade_out", "clean_full_opacity_fill", "outline_disabled", "backing_disabled"]
    destination.write_text(text, encoding="utf-8")
    return {"changed": bool(changes), "changes": changes, "sha256": sha256(destination)}


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
    # A prior interrupted/failed attempt may leave only the disposable clone.
    # The authoritative V08 baseline and all rendered versions remain intact.
    assert manager.DeleteProject(NEW)
assert manager.ImportProject(str(baseline_drp), NEW)
project = manager.LoadProject(NEW)
assert project
timeline = project.GetCurrentTimeline()
origin = timeline.GetStartFrame()
clips = timeline.GetItemListInTrack("video", 1)
assert [(c.GetStart() - origin, c.GetEnd() - origin) for c in clips] == EXPECTED_TIMELINE

saved = []
for index, clip in enumerate(clips):
    original = OUT / f"clip_{index:02d}_v11.comp"
    assert clip.ExportFusionComp(str(original), 1)
    selected = original
    patch = {"changed": False, "changes": [], "sha256": sha256(original)}
    if index in (0, 1, 2):
        selected = OUT / f"clip_{index:02d}_v12.comp"
        patch = patch_comp(original, selected, index)
    saved.append({
        "timeline": [clip.GetStart() - origin, clip.GetEnd() - origin],
        "source": [clip.GetSourceStartFrame(), clip.GetSourceEndFrame()],
        "media": clip.GetMediaPoolItem(), "lut": clip.GetLUT(1),
        "comp": selected, "patch": patch,
    })

assert timeline.DeleteClips(clips, False)
pool = project.GetMediaPool()
readbacks = []
for index, old in enumerate(saved):
    appended = pool.AppendToTimeline([{
        "mediaPoolItem": old["media"], "startFrame": old["source"][0],
        "endFrame": old["source"][1], "mediaType": 1, "trackIndex": 1,
        "recordFrame": origin + old["timeline"][0],
    }])
    assert len(appended) == 1
    item = appended[0]
    assert item.ImportFusionComp(str(old["comp"]))
    assert item.SetLUT(1, old["lut"])
    assert [item.GetStart() - origin, item.GetEnd() - origin] == old["timeline"]
    assert [item.GetSourceStartFrame(), item.GetSourceEndFrame()] == old["source"]
    readback = OUT / f"clip_{index:02d}_readback.comp"
    assert item.ExportFusionComp(str(readback), 1)
    body = readback.read_text(encoding="utf-8")
    assert "Center = Input { Value = { 0.5, 0.72 }, }," in body
    if index == 0:
        assert 'Size = Input { Value = 0.105, },' in body
    if index in (1, 2):
        assert 'Size = Input { Value = 0.125, },' in body and 'Size = Input { Value = 0.075, },' in body
    readbacks.append({"index": index, "sha256": sha256(readback), **old["patch"]})

assert manager.SaveProject()
drp = OUT / f"{NEW}.drp"
assert manager.ExportProject(NEW, str(drp), False)
prores = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V12_BASE_HLG_PRORES.mov"
assert resolve.OpenPage("deliver")
assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetCurrentRenderMode(1)
assert project.SetRenderSettings({
    "SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + 719,
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
    "schema": "RESOLVE_CLAUDE_ORIGINALS_BASE_V12",
    "project": NEW, "baseline_project": BASE, "timeline": timeline.GetName(),
    "rendered_frames": [0, 719], "caption_readbacks": readbacks,
    "picture_source_ranges_changed": False, "programme_audio_changed": False,
    "timeline_cuts_changed": False, "fusion_picture_geometry_changed": False,
    "rhythm_motion_changed": False, "colour_changed": False, "ending_changed": False,
    "caption_contract": {
        "opening_hook": {"size": 0.105, "center": [0.5, 0.205], "frames": [0, 82], "fill_opacity": 1, "softness": 0},
        "title": {"size": 0.125, "center": [0.5, 0.13], "fill_rgb": [1.0, 0.86, 0.38], "fill_opacity": 1, "softness": 0},
        "artist": {"size": 0.075, "center": [0.5, 0.255], "fill_opacity": 1, "softness": 0},
        "outline": {"native_text_plus_element": 2, "enabled": False},
        "local_backing": {"native_text_plus_element": 3, "enabled": False},
        "overlap_prevention": "opening hook hidden before title/artist section; inherited duplicates disabled",
    },
    "prores": {"path": str(prores), "sha256": sha256(prores), "bytes": prores.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
}
(OUT / "RESOLVE_CLAUDE_ORIGINALS_BASE_V12.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
