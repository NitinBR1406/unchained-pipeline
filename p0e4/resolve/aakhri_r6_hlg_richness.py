"""Render the bounded four-by-four R6 Rec.2100 HLG richness matrix."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from multitake.hlg_richness_calibration import VARIANTS, validate_contract, verify_render_plan
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS, TAKES, sha


PROJECT_SETTINGS = {
    "timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920",
    "timelineFrameRate": str(FPS), "colorScienceMode": "davinciYRGBColorManaged",
    "isAutoColorManage": "0", "colorSpaceInput": "Rec.2100 HLG",
    "colorSpaceTimeline": "Rec.2100 HLG", "colorSpaceOutput": "Rec.2100 HLG",
    "colorSpaceOutputToneMapping": "None", "colorSpaceOutputGamutMapping": "None",
}


def run(source_dir: Path, contract_path: Path, out_dir: Path, project_name: str) -> dict:
    source_dir, contract_path, root = [Path(x).resolve() for x in (source_dir, contract_path, out_dir)]
    if root.parent.name != ".local" or root.name != "aakhri-r6-hlg-richness":
        raise ValueError("PRIVATE_R6_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_R6_HLG_RICHNESS_V01", project_name):
        raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "RESOLVE_R6_HLG_RICHNESS_V01.json"
    if report_path.exists():
        raise ValueError("NO_DUPLICATE_REPLAY")
    contract = json.loads(contract_path.read_text()); validate_contract(contract)
    sources = {}
    for scene in contract["representative_scenes"]:
        asset_id = scene["take_asset_id"]; filename, expected, _ = TAKES[asset_id]
        path = source_dir / filename; digest, size = sha(path)
        if digest != expected:
            raise ValueError("SOURCE_DRIFT:" + asset_id)
        sources[asset_id] = {"path": str(path), "sha256": digest, "bytes": size}

    import DaVinciResolveScript as d
    resolve = d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName() != "DaVinci Resolve Studio":
        raise RuntimeError("RESOLVE_STUDIO_UNAVAILABLE")
    pm = resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder():
        raise ValueError("NO_DUPLICATE_PROJECT")
    original = pm.GetCurrentProject(); original_name = original.GetName() if original else None
    original_page = resolve.GetCurrentPage(); project = None
    receipt = {"schema": "RESOLVE_R6_HLG_RICHNESS_V01", "classification": "HDR_COLOR_RICHNESS_SELECTION_ASSETS",
               "contract_sha256": sha(contract_path)[0], "full_master_rendered": False,
               "static_masks_used": False, "blur_used": False, "fusion_tools_used": [],
               "sources_before": sources, "segments": [], "governance": contract["governance"]}
    def save(): report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    try:
        project = pm.CreateProject(project_name)
        if not project:
            raise RuntimeError("PROJECT_CREATE")
        results = {key: bool(project.SetSetting(key, value)) for key, value in PROJECT_SETTINGS.items()}
        if not all(results.values()):
            raise RuntimeError("PROJECT_COLOR_SETTING_REJECTED:" + repr(results))
        actual = {key: str(project.GetSetting(key)) for key in PROJECT_SETTINGS}
        validate_resolve_hlg_settings(actual)
        receipt["project_settings_actual"] = actual; receipt["project_setting_results"] = results
        pool = project.GetMediaPool(); imported = pool.ImportMedia([row["path"] for row in sources.values()])
        if len(imported) != 4:
            raise RuntimeError("IMPORT")
        by_name = {item.GetName(): item for item in imported}
        receipt["resolve_input_interpretation"] = {}
        for asset_id, row in sources.items():
            item = by_name[Path(row["path"]).name]
            props = {key: item.GetClipProperty(key) for key in ("Input Color Space", "Input Gamma", "Video Codec", "Bit Depth", "Resolution", "FPS")}
            if props["Input Color Space"] != "Rec.2100 HLG" or props["Input Gamma"] != "Rec.2100 HLG" or str(props["Bit Depth"]) != "10":
                raise ValueError("INPUT_INTERPRETATION:" + asset_id + ":" + repr(props))
            receipt["resolve_input_interpretation"][asset_id] = props
        timeline = pool.CreateEmptyTimeline("AAKHRI_R6_HLG_RICHNESS_MATRIX_V01")
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError("TIMELINE")
        origin = timeline.GetStartFrame(); cursor = 0
        for scene in contract["representative_scenes"]:
            asset_id = scene["take_asset_id"]; filename = Path(sources[asset_id]["path"]).name
            start = round(float(scene["source_time_seconds"]) * FPS)
            for variant in VARIANTS:
                clips = pool.AppendToTimeline([{"mediaPoolItem": by_name[filename], "startFrame": start,
                    "endFrame": start + FPS, "mediaType": 1, "trackIndex": 1,
                    "recordFrame": origin + cursor}])
                if len(clips) != 1:
                    raise RuntimeError("APPEND:" + str(scene["scene_index"]) + ":" + variant)
                recipe = contract["variant_recipes"][variant]
                if variant != "HLG_IDENTITY" and not clips[0].SetCDL(recipe["cdl"]):
                    raise RuntimeError("COLOR_PAGE_CDL:" + variant)
                receipt["segments"].append({"scene_index": scene["scene_index"], "take_asset_id": asset_id,
                    "source_sha256": sources[asset_id]["sha256"], "source_time_seconds": scene["source_time_seconds"],
                    "variant": variant, "timeline_start_frame": cursor, "timeline_end_frame_exclusive": cursor + FPS,
                    "color_operation": recipe, "fusion_tools": [], "mask_used": False, "blur_used": False})
                cursor += FPS
        verify_render_plan({"full_master": False, "segments": receipt["segments"]})
        if cursor != 16 * FPS:
            raise RuntimeError("NOT_SIXTEEN_SECONDS")
        if not project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ"):
            raise RuntimeError("PRORES422HQ_UNAVAILABLE")
        project.SetCurrentRenderMode(1)
        settings = {"SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + cursor - 1,
            "TargetDir": str(root), "CustomName": "AAKHRI_R6_HLG_RICHNESS_MATRIX_V01",
            "ExportVideo": True, "ExportAudio": False, "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": FPS}
        if not project.SetRenderSettings(settings):
            raise RuntimeError("RENDER_SETTINGS")
        job = project.AddRenderJob()
        if not job or not project.StartRendering([job], False):
            raise RuntimeError("RENDER_START")
        deadline = time.monotonic() + 1200
        while project.IsRenderingInProgress() and time.monotonic() < deadline:
            time.sleep(.5)
        if project.IsRenderingInProgress():
            project.StopRendering(); raise RuntimeError("RENDER_TIMEOUT")
        status = project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
        output = root / "AAKHRI_R6_HLG_RICHNESS_MATRIX_V01.mov"
        if status.get("JobStatus") != "Complete" or not output.exists():
            raise RuntimeError("RENDER_FAILED:" + repr(status))
        receipt["output"] = {"path": str(output), "sha256": sha(output)[0], "bytes": sha(output)[1],
                             "duration_frames": cursor, "render_status": status}
        if not pm.SaveProject() or not pm.ExportProject(project_name, str(root / (project_name + ".drp")), False):
            raise RuntimeError("PROJECT_EXPORT")
        drp = root / (project_name + ".drp"); receipt["resolve_project"] = {"path": str(drp), "sha256": sha(drp)[0]}
        receipt["sources_after"] = {aid: {"sha256": sha(row["path"])[0], "bytes": sha(row["path"])[1]} for aid, row in sources.items()}
        if any(receipt["sources_after"][aid]["sha256"] != row["sha256"] for aid, row in sources.items()):
            raise ValueError("SOURCE_CHANGED")
        receipt["status"] = "R6_HLG_RICHNESS_MATRIX_RENDERED_PRIVATE_ONLY"; save()
    finally:
        if project:
            pm.SaveProject(); receipt["project_closed"] = bool(pm.CloseProject(project)); save()
        if original_name:
            receipt["original_restored"] = bool(pm.LoadProject(original_name)); save()
        if original_page:
            resolve.OpenPage(original_page)
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("source_dir"); p.add_argument("contract"); p.add_argument("out_dir"); p.add_argument("project"); a = p.parse_args()
    run(Path(a.source_dir), Path(a.contract), Path(a.out_dir), a.project)
