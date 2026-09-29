"""Render two bounded premium caption treatments from the immutable V13 project."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import DaVinciResolveScript as d

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aakhri_premium_style_sample_v02_contract import (
    BASE_PROJECT,
    CHAIN_LOGO_SHA256,
    REQUEST_ID,
    SAMPLE_FRAMES,
    WINDOWS,
    sha256,
    verify_decode,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-premium-style-sample-v02"
OUT.mkdir(parents=True, exist_ok=True)
BASE_DRP = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair/UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp"
BASE_MASTER = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair/AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR_HLG_PRORES.mov"
LOGO = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair/unchained_chain_emblem.png"
LOGO_ANIM = OUT / "UNCHAINED_CHAIN_LOGO_RESTRAINED_LIGHT_PASS_54F.mov"
FFMPEG = shutil.which("ffmpeg") or "/Users/nitinramdaras/ffbin/ffmpeg"
EXPECTED_TIMELINE = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]

TREATMENTS = {
    "A_CINEMATIC_BALANCE": {
        "project": "UNCHAINED_AAKHRI_PREMIUM_SAMPLE_V02_A_CINEMATIC_BALANCE",
        "hook": {"center": (0.5, 0.205), "size": 0.088, "curve": [(0, 0), (53, 0), (60, 1), (78, 1), (88, 0)]},
        "title": {"center": (0.5, 0.135), "size": 0.112, "curve": [(0, 0), (8, 1), (90, 1)]},
        "artist": {"center": (0.5, 0.252), "size": 0.064, "curve": [(0, 0), (8, 1), (90, 1)]},
        "recommendation": "RECOMMENDED_FOR_NITIN_REVIEW",
    },
    "B_EDITORIAL_RESTRAINT": {
        "project": "UNCHAINED_AAKHRI_PREMIUM_SAMPLE_V02_B_EDITORIAL_RESTRAINT",
        "hook": {"center": (0.5, 0.175), "size": 0.080, "curve": [(0, 0), (53, 0), (62, 1), (74, 1), (88, 0)]},
        "title": {"center": (0.5, 0.145), "size": 0.104, "curve": [(0, 0), (12, 1), (90, 1)]},
        "artist": {"center": (0.5, 0.242), "size": 0.057, "curve": [(0, 0), (12, 1), (90, 1)]},
        "recommendation": "ALTERNATIVE_NOT_SELECTED",
    },
}


def replace_tool_block(text: str, name: str, transform) -> str:
    marker = f"\n\t\t{name} = "
    start = text.index(marker) + 1
    match = re.search(r"\n\t\t[^\t]", text[start + len(marker):])
    if not match:
        raise RuntimeError(f"cannot locate end of {name}")
    end = start + len(marker) + match.start()
    return text[:start] + transform(text[start:end]) + text[end:]


def set_value(block: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+|\{{[^}}]+\}})(, \}},)"
    patched, count = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if count != 1:
        raise RuntimeError(f"expected one {key}")
    return patched


def set_or_insert(block: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+)(, \}},)"
    patched, count = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if count:
        return patched
    needle = "\n\t\t\t\tStyledText = Input"
    if needle not in block:
        raise RuntimeError(f"cannot insert {key}")
    return block.replace(needle, f"\n\t\t\t\t{key} = Input {{ Value = {value}, }}," + needle, 1)


def style(block: str, *, center, size, rgb, font, weight) -> str:
    for key, value in (
        ("Center", f"{{ {center[0]}, {center[1]} }}"), ("Size", str(size)),
        ("Font", f'"{font}"'), ("Style", f'"{weight}"'),
    ):
        block = set_value(block, key, value)
    for key, value in zip(("Red1", "Green1", "Blue1"), rgb):
        block = set_or_insert(block, key, str(value))
    for key, value in (("Enabled2", "0"), ("Enabled3", "0"), ("Softness1", "0"), ("Opacity1", "1")):
        block = set_or_insert(block, key, value)
    return block


def curve(block: str, points) -> str:
    begin = block.index("\n\t\t\tKeyFrames = {")
    end = block.index("\n\t\t\t}", begin) + len("\n\t\t\t}")
    lines = ["\n\t\t\tKeyFrames = {"]
    for frame, value in points:
        lines.append(f"\t\t\t\t[{frame}] = {{ {value}, Flags = {{ Linear = true }} }},")
    lines.append("\t\t\t}")
    return block[:begin] + "\n".join(lines) + block[end:]


def patch_comp(source: Path, destination: Path, clip_index: int, treatment: dict) -> None:
    text = source.read_text(encoding="utf-8")
    offwhite = (0.96, 0.94, 0.88)
    gold = (0.847058823529412, 0.72156862745098, 0.313725490196078)
    if clip_index == 0:
        h = treatment["hook"]
        text = replace_tool_block(text, "UN_BRAND_HOOK", lambda b: style(b, center=h["center"], size=h["size"], rgb=offwhite, font="Montserrat", weight="Medium"))
        text = replace_tool_block(text, "Merge1Blend", lambda b: curve(b, h["curve"]))
        text = replace_tool_block(text, "Merge2Blend", lambda b: curve(b, [(0, 0), (88, 0)]))
    elif clip_index == 1:
        t, a = treatment["title"], treatment["artist"]
        text = replace_tool_block(text, "UN_BRAND_TITLE", lambda b: style(b, center=t["center"], size=t["size"], rgb=gold, font="Cinzel", weight="SemiBold"))
        text = replace_tool_block(text, "UN_BRAND_ARTIST", lambda b: style(b, center=a["center"], size=a["size"], rgb=offwhite, font="Montserrat", weight="Medium"))
        text = replace_tool_block(text, "Merge3Blend", lambda b: curve(b, t["curve"]))
        text = replace_tool_block(text, "Merge4Blend", lambda b: curve(b, a["curve"]))
        text = replace_tool_block(text, "Merge1Blend", lambda b: curve(b, [(0, 0), (114, 0)]))
        text = replace_tool_block(text, "Merge2Blend", lambda b: curve(b, [(0, 0), (114, 0)]))
    destination.write_text(text, encoding="utf-8")


def build_logo_animation() -> None:
    if sha256(LOGO) != CHAIN_LOGO_SHA256:
        raise RuntimeError("chain-logo binding drift")
    partial = LOGO_ANIM.with_suffix(".partial.mov")
    partial.unlink(missing_ok=True)
    filter_graph = (
        "[0:v]format=rgba,split=2[base][hi];"
        "[hi]eq=brightness=0.10:saturation=0.92,"
        "crop=w=110:h=ih:x='max(0,min(iw-110,-110+t*580))':y=0[band];"
        "[base][band]overlay=x='max(0,min(W-w,-110+t*580))':y=0:format=auto,"
        "fade=t=in:st=0:d=0.20:alpha=1,fade=t=out:st=1.55:d=0.25:alpha=1,"
        "format=yuva444p10le[out]"
    )
    subprocess.run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(LOGO),
        "-filter_complex", filter_graph, "-map", "[out]", "-frames:v", "54", "-r", "30",
        "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le", "-an", "-y", str(partial),
    ], check=True)
    os.replace(partial, LOGO_ANIM)


def render_treatment(resolve, manager, key: str, treatment: dict) -> dict:
    name = treatment["project"]
    target = OUT / f"AAKHRI_PREMIUM_STYLE_{key}_HLG_PRORES.mov"
    drp = OUT / f"{name}.drp"
    readback_paths = [OUT / f"{key}_clip_{index:02d}_{kind}.comp" for index in (0, 1) for kind in ("source", "patched", "readback")]
    if target.exists() and drp.exists() and all(path.exists() for path in readback_paths):
        readbacks = []
        for index in (0, 1):
            readbacks.append({
                "clip": index,
                "source_sha256": sha256(OUT / f"{key}_clip_{index:02d}_source.comp"),
                "patched_sha256": sha256(OUT / f"{key}_clip_{index:02d}_patched.comp"),
                "readback_sha256": sha256(OUT / f"{key}_clip_{index:02d}_readback.comp"),
            })
        return {
            "treatment": key, "project": name, "sample_frames": list(SAMPLE_FRAMES), "readbacks": readbacks,
            "logo_animation": {"source_sha256": sha256(LOGO), "derived_sha256": sha256(LOGO_ANIM), "frames": list(WINDOWS["logo"]), "effect": "single_restrained_diagonal_light_pass_then_clean_fade"},
            "caption_windows": {k: list(v) for k, v in WINDOWS.items()}, "audio_colour_crop_edit_timing_changed": False,
            "render": {"path": str(target), "sha256": sha256(target), "bytes": target.stat().st_size, "seconds": "UNAVAILABLE_AFTER_RECEIPT_WRITE_FAILURE", "decode": verify_decode(target), "reused_without_rerender": True},
            "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
            "render_status": "COMPLETE_ARTIFACT_REUSED_AFTER_POST_RENDER_DECODE_TOOL_PATH_FAILURE",
            "recommendation": treatment["recommendation"],
        }
    if name in manager.GetProjectListInCurrentFolder():
        assert manager.DeleteProject(name)
    assert manager.ImportProject(str(BASE_DRP), name)
    project = manager.LoadProject(name)
    assert project and not project.IsRenderingInProgress()
    timeline = project.GetCurrentTimeline()
    origin = timeline.GetStartFrame()
    clips = timeline.GetItemListInTrack("video", 1)
    assert [(c.GetStart() - origin, c.GetEnd() - origin) for c in clips] == EXPECTED_TIMELINE

    readbacks = []
    for index in (0, 1):
        source = OUT / f"{key}_clip_{index:02d}_source.comp"
        patched = OUT / f"{key}_clip_{index:02d}_patched.comp"
        assert clips[index].ExportFusionComp(str(source), 1)
        patch_comp(source, patched, index, treatment)
        assert clips[index].ImportFusionComp(str(patched))
        readback = OUT / f"{key}_clip_{index:02d}_readback.comp"
        assert clips[index].ExportFusionComp(str(readback), 1)
        body = readback.read_text(encoding="utf-8")
        assert 'Font = Input { Value = "Montserrat", },' in body
        if index == 1:
            assert 'Font = Input { Value = "Cinzel", },' in body and 'Style = Input { Value = "SemiBold", },' in body
        readbacks.append({"clip": index, "source_sha256": sha256(source), "patched_sha256": sha256(patched), "readback_sha256": sha256(readback)})

    v2 = timeline.GetItemListInTrack("video", 2)
    intro = [item for item in v2 if item.GetStart() - origin == WINDOWS["logo"][0] and item.GetEnd() - origin == WINDOWS["logo"][1] + 1]
    assert len(intro) == 1 and timeline.DeleteClips(intro, False)
    pool = project.GetMediaPool()
    media = pool.ImportMedia([str(LOGO_ANIM)])
    assert len(media) == 1
    new_intro = pool.AppendToTimeline([{
        "mediaPoolItem": media[0], "startFrame": 0, "endFrame": 54,
        "mediaType": 1, "trackIndex": 2, "recordFrame": origin,
    }])[0]
    assert new_intro.SetProperty("ZoomX", 0.30)
    assert new_intro.SetProperty("ZoomY", 0.30)
    assert new_intro.SetProperty("Tilt", -3000.0)
    assert [new_intro.GetStart() - origin, new_intro.GetEnd() - origin] == [0, 54]

    assert manager.SaveProject()
    assert manager.ExportProject(name, str(drp), False)
    assert resolve.OpenPage("deliver")
    assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
    project.SetCurrentRenderMode(1)
    assert project.SetRenderSettings({
        "SelectAllFrames": False, "MarkIn": origin + SAMPLE_FRAMES[0], "MarkOut": origin + SAMPLE_FRAMES[1],
        "TargetDir": str(OUT), "CustomName": target.stem, "ExportVideo": True, "ExportAudio": True,
        "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
        "AudioCodec": "lpcm", "AudioSampleRate": 48000,
    })
    started = time.monotonic()
    job = project.AddRenderJob(); assert job
    assert project.StartRendering([job], False)
    deadline = time.monotonic() + 900
    while project.IsRenderingInProgress() and time.monotonic() < deadline:
        time.sleep(0.5)
    assert not project.IsRenderingInProgress()
    status = project.GetRenderJobStatus(job)
    assert status.get("JobStatus") == "Complete" and target.exists(), status
    project.DeleteRenderJob(job)
    return {
        "treatment": key, "project": name, "sample_frames": list(SAMPLE_FRAMES), "readbacks": readbacks,
        "logo_animation": {"source_sha256": sha256(LOGO), "derived_sha256": sha256(LOGO_ANIM), "frames": list(WINDOWS["logo"]), "effect": "single_restrained_diagonal_light_pass_then_clean_fade"},
        "caption_windows": {k: list(v) for k, v in WINDOWS.items()}, "audio_colour_crop_edit_timing_changed": False,
        "render": {"path": str(target), "sha256": sha256(target), "bytes": target.stat().st_size, "seconds": round(time.monotonic() - started, 3), "decode": verify_decode(target)},
        "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
        "render_status": status, "recommendation": treatment["recommendation"],
    }


assert BASE_DRP.is_file() and BASE_MASTER.is_file()
build_logo_animation()
resolve = d.scriptapp("Resolve")
assert resolve, "Resolve scripting unavailable"
manager = resolve.GetProjectManager()
receipts = [render_treatment(resolve, manager, key, value) for key, value in TREATMENTS.items()]
result = {
    "schema": "UNCHAINED_PREMIUM_STYLE_SAMPLE_EXECUTION_V02",
    "request_id": REQUEST_ID,
    "base_project": BASE_PROJECT,
    "base_drp_sha256": sha256(BASE_DRP),
    "base_master_sha256": sha256(BASE_MASTER),
    "sample_is_excerpt": True,
    "full_clip_coverage_constraint_proven_by_sample": False,
    "treatments": receipts,
    "selected_recommendation": "A_CINEMATIC_BALANCE",
    "nitin_approval": False,
    "publication_authorized": False,
}
(OUT / "PREMIUM_STYLE_SAMPLE_EXECUTION_V02.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2))
