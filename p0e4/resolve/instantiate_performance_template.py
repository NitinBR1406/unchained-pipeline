"""Instantiate the reusable performance template as a private, non-rendering Resolve project."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from p0e4.resolve.performance_template import build_dry_run_plan, load_json, sha256

FPS = 30
HLG_SETTINGS = {
    "timelineResolutionWidth": "1080",
    "timelineResolutionHeight": "1920",
    "timelineFrameRate": "30",
    "colorScienceMode": "davinciYRGBColorManaged",
    "isAutoColorManage": "0",
    "colorSpaceInput": "Rec.2100 HLG",
    "colorSpaceTimeline": "Rec.2100 HLG",
    "colorSpaceOutput": "Rec.2100 HLG",
    "colorSpaceOutputToneMapping": "None",
    "colorSpaceOutputGamutMapping": "None",
}


def frame(ms: int) -> int:
    return round(ms * FPS / 1000)


def point(tool, name, value):
    setattr(tool, name, {1: float(value[0]), 2: float(value[1])})


def run(job_path: str, edl_path: str, source_dir: str, lut_path: str, output_dir: str, project_name: str):
    job = load_json(job_path)
    plan = build_dry_run_plan(job)
    if plan["effect_nodes_enabled"] or plan["caption_enabled"]:
        raise ValueError("DRY_RUN_REQUIRES_ALL_EFFECTS_AND_CAPTIONS_OFF")
    edl = load_json(edl_path)
    if edl["edl_sha256"] != job["source_binding"]["edit_plan_sha256"]:
        raise ValueError("EDIT_PLAN_DRIFT")
    output = Path(output_dir).resolve()
    if output.parent.name != ".local" or output.name != "unchained-performance-template-v01":
        raise ValueError("PRIVATE_DISPOSABLE_OUTPUT_REQUIRED")
    output.mkdir(parents=True, exist_ok=True)
    report = output / "TEMPLATE_INSTANTIATION_RECEIPT.json"
    drp = output / f"{project_name}.drp"
    if report.exists() or drp.exists():
        raise ValueError("NO_DUPLICATE_REPLAY")
    source_dir = Path(source_dir).resolve()
    lut = Path(lut_path).resolve()
    if sha256(lut) != job["style_binding"]["color_preset_sha256"]:
        raise ValueError("COLOR_PRESET_DRIFT")
    names = {"1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8": "IMG_5739.MOV", "1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin": "IMG_5740.MOV", "1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8": "IMG_5741.MOV", "1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW": "IMG_5742.MOV"}
    sources = {}
    for asset_id, expected in job["source_binding"]["take_asset_ids_and_sha256"].items():
        path = source_dir / names[asset_id]
        if sha256(path) != expected:
            raise ValueError(f"TAKE_DRIFT:{asset_id}")
        sources[asset_id] = path
    audio = source_dir / "AAKHRI ISHQ MASTER 2.wav"
    if sha256(audio) != job["source_binding"]["audio_sha256"]:
        raise ValueError("AUDIO_DRIFT")

    import DaVinciResolveScript as d
    resolve = d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName() != "DaVinci Resolve Studio":
        raise RuntimeError("RESOLVE_STUDIO_UNAVAILABLE")
    pm = resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder():
        raise ValueError("NO_DUPLICATE_PROJECT")
    previous = pm.GetCurrentProject()
    previous_name = previous.GetName() if previous else None
    previous_page = resolve.GetCurrentPage()
    project = None
    receipt = {"schema": "UNCHAINED_PERFORMANCE_TEMPLATE_INSTANTIATION_RECEIPT_V01", "project_name": project_name, "job_sha256": sha256(job_path), "edit_plan_semantic_sha256": edl["edl_sha256"], "source_hashes": job["source_binding"], "effects_enabled": [], "effects_bypassed": plan["effect_nodes_bypassed"], "caption_mode": "NONE", "render_requested": False, "full_master_rendered": False}
    try:
        project = pm.CreateProject(project_name)
        if not project:
            raise RuntimeError("CREATE_PROJECT_FAILED")
        applied = {key: bool(project.SetSetting(key, value)) for key, value in HLG_SETTINGS.items()}
        if not all(applied.values()):
            raise RuntimeError("HLG_SETTINGS_FAILED")
        receipt["hlg_settings"] = {key: str(project.GetSetting(key)) for key in HLG_SETTINGS}
        lut_root = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_PERFORMANCE_TEMPLATE_V01")
        lut_root.mkdir(parents=True, exist_ok=True)
        lut_dest = lut_root / "AAKHRI_V06_PROVISIONAL.cube"
        shutil.copy2(lut, lut_dest)
        project.RefreshLUTList()
        pool = project.GetMediaPool()
        imported = pool.ImportMedia([str(path) for path in sources.values()] + [str(audio)])
        by_name = {item.GetName(): item for item in imported}
        timeline = pool.CreateEmptyTimeline("TEMPLATE_DRY_RUN_24S_EFFECTS_OFF")
        project.SetCurrentTimeline(timeline)
        origin = timeline.GetStartFrame()
        cursor = 0
        start_ms, end_ms = 72000, 96000
        component_instances = []
        for segment in edl["segments"]:
            start = max(start_ms, segment["timeline_start_ms"])
            end = min(end_ms, segment["timeline_end_ms"])
            if start >= end:
                continue
            asset_id = segment["take_asset_id"]
            source_start = segment["take_start_ms"] + start - segment["timeline_start_ms"]
            duration = end - start
            clip = pool.AppendToTimeline([{"mediaPoolItem": by_name[names[asset_id]], "startFrame": frame(source_start), "endFrame": frame(source_start + duration), "mediaType": 1, "trackIndex": 1, "recordFrame": origin + cursor}])[0]
            if not clip.SetLUT(1, str(lut_dest)):
                raise RuntimeError("LUT_BIND_FAILED")
            comp = clip.AddFusionComp()
            media_in, media_out = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
            base = comp.AddTool("Transform"); base.SetAttrs({"TOOLS_Name": "BASE_CROP"}); base.Input = media_in.Output
            crop = job["style_binding"]["per_take_base_crop"][asset_id]
            base.Size = float(crop["scale"]); point(base, "Center", crop["center"])
            current = base
            for component in ("MICRO_PUSH_OFF", "RESTRAINED_SHAKE_OFF", "SLOW_PUSH_OFF"):
                tool = comp.AddTool("Transform"); tool.SetAttrs({"TOOLS_Name": component}); tool.Input = current.Output; tool.Size = 1.0; point(tool, "Center", [0.5, 0.5]); current = tool
            media_out.Input = current.Output
            component_instances.append({"asset_id": asset_id, "timeline_ms": [start, end], "components": ["BASE_CROP", "MICRO_PUSH_OFF", "RESTRAINED_SHAKE_OFF", "SLOW_PUSH_OFF"], "caption_component_connected": False})
            cursor += frame(duration)
        audio_items = pool.AppendToTimeline([{"mediaPoolItem": by_name[audio.name], "startFrame": frame(start_ms), "endFrame": frame(end_ms), "mediaType": 2, "trackIndex": 1, "recordFrame": origin}])
        if len(audio_items) != 1:
            raise RuntimeError("AUDIO_APPEND_FAILED")
        if not pm.SaveProject() or not pm.ExportProject(project_name, str(drp), False):
            raise RuntimeError("PROJECT_EXPORT_FAILED")
        receipt.update({"status": "INSTANTIATED_PRIVATE_DRY_RUN_NO_RENDER", "timeline": timeline.GetName(), "timeline_frames": cursor, "component_instances": component_instances, "project_export": str(drp), "project_export_sha256": sha256(drp)})
        report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    finally:
        if project:
            pm.SaveProject(); receipt["project_closed"] = bool(pm.CloseProject(project)); report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        if previous_name:
            receipt["previous_project_restored"] = bool(pm.LoadProject(previous_name)); report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        if previous_page:
            resolve.OpenPage(previous_page)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("job", "edl", "source_dir", "lut", "output_dir", "project_name"):
        parser.add_argument(name)
    args = parser.parse_args()
    run(args.job, args.edl, args.source_dir, args.lut, args.output_dir, args.project_name)
