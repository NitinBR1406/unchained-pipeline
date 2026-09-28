"""Render the V13 repair base from the rejected V12 implementation.

The script clones the V11 Resolve project and changes the bounded Fusion
caption nodes/visibility curves. It snapshots and restores framing/crop/
composite properties, every Fusion comp and LUT slot used by the six clips,
and fails closed when their readback differs.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import DaVinciResolveScript as d

from aakhri_v12_repair_contract import VISIBILITY_WINDOWS, set_or_insert_scalar


BASE = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V11_CLEAN_TYPOGRAPHY"
NEW = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair"
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED_TIMELINE = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
PRESERVED_CLIP_PROPERTIES = [
    "ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "AnchorPointX",
    "AnchorPointY", "CropLeft", "CropRight", "CropTop", "CropBottom",
    "CompositeMode", "Opacity",
]


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
    return set_or_insert_scalar(block, key, value)


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
    return set_or_insert_value(block, "Opacity1", "1")


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
        # The chain intro occupies output frames 0..53.  Keep the hook fully
        # hidden until the intro has ended so two independent text/brand layers
        # can never collide in the rendered opening.
        text = replace_tool_block(text, "Merge1Blend", lambda b: blend_curve(b, [(0, 0), (53, 0), (60, 1), (72, 1), (82, 0), (88, 0)]))
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
    original_comps = []
    for comp_index in range(1, clip.GetFusionCompCount() + 1):
        original = OUT / f"clip_{index:02d}_v11_comp_{comp_index:02d}.comp"
        assert clip.ExportFusionComp(str(original), comp_index)
        original_comps.append(original)
    assert original_comps, f"clip {index} has no Fusion comp"
    selected_comps = list(original_comps)
    patch = {"changed": False, "changes": [], "sha256": sha256(original_comps[0])}
    if index in (0, 1, 2):
        selected = OUT / f"clip_{index:02d}_v13.comp"
        patch = patch_comp(original_comps[0], selected, index)
        selected_comps[0] = selected
    saved.append({
        "timeline": [clip.GetStart() - origin, clip.GetEnd() - origin],
        "source": [clip.GetSourceStartFrame(), clip.GetSourceEndFrame()],
        "media": clip.GetMediaPoolItem(), "lut": clip.GetLUT(1),
        "comps": selected_comps, "patch": patch,
        "properties": {key: clip.GetProperty(key) for key in PRESERVED_CLIP_PROPERTIES},
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
    for comp in old["comps"]:
        assert item.ImportFusionComp(str(comp))
    assert item.GetFusionCompCount() == len(old["comps"])
    assert item.SetLUT(1, old["lut"])
    assert item.GetLUT(1) == old["lut"]
    for key, value in old["properties"].items():
        assert item.SetProperty(key, value), f"cannot restore {key} on clip {index}"
        assert item.GetProperty(key) == value, f"{key} readback drift on clip {index}"
    assert [item.GetStart() - origin, item.GetEnd() - origin] == old["timeline"]
    assert [item.GetSourceStartFrame(), item.GetSourceEndFrame()] == old["source"]
    readback_comps = []
    for comp_index in range(1, item.GetFusionCompCount() + 1):
        readback = OUT / f"clip_{index:02d}_readback_comp_{comp_index:02d}.comp"
        assert item.ExportFusionComp(str(readback), comp_index)
        readback_comps.append({"index": comp_index, "sha256": sha256(readback)})
    body = (OUT / f"clip_{index:02d}_readback_comp_01.comp").read_text(encoding="utf-8")
    assert "Center = Input { Value = { 0.5, 0.72 }, }," in body
    if index == 0:
        assert 'Size = Input { Value = 0.105, },' in body
    if index in (1, 2):
        assert 'Size = Input { Value = 0.125, },' in body and 'Size = Input { Value = 0.075, },' in body
    readbacks.append({
        "index": index,
        "intended_comp_sha256": old["patch"]["sha256"],
        "readback_comps": readback_comps,
        "clip_properties": old["properties"],
        "lut_slot_1": old["lut"],
        "changed": old["patch"]["changed"],
        "changes": old["patch"]["changes"],
    })

assert manager.SaveProject()
drp = OUT / f"{NEW}.drp"
assert manager.ExportProject(NEW, str(drp), False)
prores = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_BASE_HLG_PRORES.mov"
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
    "schema": "RESOLVE_CHAIN_CAPTION_REPAIR_BASE_V13",
    "project": NEW, "baseline_project": BASE, "timeline": timeline.GetName(),
    "rendered_frames": [0, 719], "caption_readbacks": readbacks,
    "picture_source_ranges_changed": False,
    "programme_audio_changed": "NOT_MUTATED_BY_SCRIPT_REQUIRES_RENDER_PCM_COMPARISON",
    "timeline_cuts_changed": False, "fusion_picture_geometry_changed": False,
    "rhythm_motion_changed": "ALL_FUSION_COMPS_RESTORED_AND_COUNT_VERIFIED",
    "colour_changed": "LUT_SLOT_1_RESTORED_AND_READ_BACK",
    "ending_changed": "NOT_MUTATED_BY_SCRIPT_REQUIRES_ACTUAL_OUTPUT_AUDIT",
    "caption_contract": {
        "opening_hook": {"size": 0.105, "center": [0.5, 0.205], "frames": list(VISIBILITY_WINDOWS["opening_hook"]), "fill_opacity": 1, "softness": 0},
        "title": {"size": 0.125, "center": [0.5, 0.13], "fill_rgb": [1.0, 0.86, 0.38], "fill_opacity": 1, "softness": 0},
        "artist": {"size": 0.075, "center": [0.5, 0.255], "fill_opacity": 1, "softness": 0},
        "outline": {"native_text_plus_element": 2, "enabled": False},
        "local_backing": {"native_text_plus_element": 3, "enabled": False},
        "overlap_prevention": "opening hook hidden throughout chain intro; title/artist end before outro; inherited duplicates disabled",
    },
    "prores": {"path": str(prores), "sha256": sha256(prores), "bytes": prores.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
    "repair_binding": {
        "renderer_sha256": sha256(Path(__file__)),
        "contract_sha256": sha256(Path(__file__).with_name("aakhri_v12_repair_contract.py")),
    },
}
(OUT / "RESOLVE_CHAIN_CAPTION_REPAIR_BASE_V13.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
