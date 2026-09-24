"""Render only the bounded R5 RAW-reference look-development matrix."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from multitake.raw_reference_look import LOOKS, validate_contract, verify_render_plan
from resolve.aakhri_multitake_realization import FPS, TAKES, sha


def render(project, timeline, root, name, frames):
    if not project.SetCurrentTimeline(timeline):
        raise RuntimeError("TIMELINE_SELECT")
    if not project.SetCurrentRenderFormatAndCodec("mp4", "H264"):
        raise RuntimeError("H264_UNAVAILABLE")
    project.SetCurrentRenderMode(1)
    origin = timeline.GetStartFrame()
    settings = {
        "SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + frames - 1,
        "TargetDir": str(root), "CustomName": name, "ExportVideo": True,
        "ExportAudio": False, "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": FPS,
    }
    if not project.SetRenderSettings(settings):
        raise RuntimeError("RENDER_SETTINGS")
    job = project.AddRenderJob()
    if not job or not project.StartRendering([job], False):
        raise RuntimeError("RENDER_START")
    deadline = time.monotonic() + 900
    while project.IsRenderingInProgress() and time.monotonic() < deadline:
        time.sleep(0.5)
    if project.IsRenderingInProgress():
        project.StopRendering(); raise RuntimeError("RENDER_TIMEOUT")
    status = project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
    path = root / (name + ".mp4")
    if status.get("JobStatus") != "Complete" or not path.exists():
        raise RuntimeError("RENDER_FAILED:" + repr(status))
    digest, size = sha(path)
    return {"path": str(path), "sha256": digest, "bytes": size, "frames": frames, "render_status": status}


def run(source_dir, contract_path, out_dir, project_name):
    source_dir, contract_path, root = map(lambda p: Path(p).resolve(), (source_dir, contract_path, out_dir))
    if root.parent.name != ".local" or root.name != "aakhri-r5-look-development":
        raise ValueError("PRIVATE_R5_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_R5_RAW_REFERENCE_LOOK_V01", project_name):
        raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "RESOLVE_R5_LOOK_DEVELOPMENT_V01.json"
    if report_path.exists():
        raise ValueError("NO_DUPLICATE_REPLAY")
    contract = json.loads(contract_path.read_text()); validate_contract(contract)
    sources = {}
    for scene in contract["representative_scenes"]:
        asset = scene["take_asset_id"]; name, expected, _ = TAKES[asset]
        path = source_dir / name; digest, size = sha(path)
        if digest != expected:
            raise ValueError("TAKE_DRIFT:" + asset)
        sources[asset] = {"path": str(path), "sha256": digest, "bytes": size}
    import DaVinciResolveScript as d
    resolve = d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName() != "DaVinci Resolve Studio":
        raise RuntimeError("RESOLVE_STUDIO_UNAVAILABLE")
    pm = resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder():
        raise ValueError("NO_DUPLICATE_PROJECT")
    original = pm.GetCurrentProject(); original_name = original.GetName() if original else None
    original_page = resolve.GetCurrentPage(); project = None
    receipt = {
        "schema": "RESOLVE_R5_LOOK_DEVELOPMENT_V01", "classification": "COLOR_DIRECTION_SELECTION_ASSETS",
        "contract_sha256": sha(contract_path)[0], "sources_before": sources, "full_master_rendered": False,
        "fusion_tools_used": [], "r4_static_inverted_ellipse_used": False, "segments": [],
        "governance": contract["governance"],
    }
    def save(): report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    try:
        project = pm.CreateProject(project_name)
        if not project or not project.SetSettings({"timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920", "timelineFrameRate": str(FPS)}):
            raise RuntimeError("PROJECT_SETUP")
        pool = project.GetMediaPool(); imported = pool.ImportMedia([row["path"] for row in sources.values()])
        if len(imported) != 4:
            raise RuntimeError("IMPORT")
        by_name = {item.GetName(): item for item in imported}
        timeline = pool.CreateEmptyTimeline("AAKHRI_R5_LOOK_MATRIX_V01")
        project.SetCurrentTimeline(timeline); origin = timeline.GetStartFrame(); cursor = 0
        for scene in contract["representative_scenes"]:
            asset = scene["take_asset_id"]; name = TAKES[asset][0]; start = round(scene["source_time_seconds"] * FPS)
            for look in LOOKS:
                clips = pool.AppendToTimeline([{"mediaPoolItem": by_name[name], "startFrame": start, "endFrame": start + FPS,
                    "mediaType": 1, "trackIndex": 1, "recordFrame": origin + cursor}])
                if len(clips) != 1:
                    raise RuntimeError("APPEND:" + str(scene["scene_index"]) + ":" + look)
                recipe = contract["look_recipes"][look]
                if look != "RAW_REFERENCE" and not clips[0].SetCDL(recipe["cdl"]):
                    raise RuntimeError("COLOR_PAGE_CDL:" + look)
                receipt["segments"].append({
                    "scene_index": scene["scene_index"], "take_asset_id": asset, "source_sha256": sources[asset]["sha256"],
                    "source_time_seconds": scene["source_time_seconds"], "look": look, "timeline_start_frame": cursor,
                    "timeline_end_frame_exclusive": cursor + FPS, "resolve_color_page": recipe,
                    "fusion_tools": [],
                })
                cursor += FPS
        verify_render_plan({"full_master": False, "segments": receipt["segments"]})
        receipt["output"] = render(project, timeline, root, "AAKHRI_R5_LOOK_MATRIX_V01", cursor)
        if not pm.SaveProject() or not pm.ExportProject(project_name, str(root / (project_name + ".drp")), False):
            raise RuntimeError("PROJECT_EXPORT")
        receipt["resolve_project"] = {"path": str(root / (project_name + ".drp")), "sha256": sha(root / (project_name + ".drp"))[0]}
        receipt["sources_after"] = {asset: {"sha256": sha(row["path"])[0], "bytes": sha(row["path"])[1]} for asset, row in sources.items()}
        if any(receipt["sources_after"][a]["sha256"] != sources[a]["sha256"] for a in sources):
            raise ValueError("SOURCE_CHANGED")
        receipt["status"] = "R5_LOOK_MATRIX_RENDERED_PRIVATE_ONLY"; save()
    finally:
        if project:
            pm.SaveProject(); receipt["project_closed"] = pm.CloseProject(project); save()
        if original_name:
            receipt["original_restored"] = bool(pm.LoadProject(original_name)); save()
        if original_page:
            resolve.OpenPage(original_page)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("source_dir"); parser.add_argument("contract")
    parser.add_argument("out_dir"); parser.add_argument("project"); args = parser.parse_args()
    run(args.source_dir, args.contract, args.out_dir, args.project)
