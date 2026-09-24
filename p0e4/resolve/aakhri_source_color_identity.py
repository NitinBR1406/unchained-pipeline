"""Render a four-scene, zero-grade Rec.2100 HLG identity test; never a full master."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS, TAKES, sha


SCENES = (
    ("1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8", 36.0),
    ("1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin", 24.0),
    ("1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8", 96.0),
    ("1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW", 72.0),
)
PROJECT_SETTINGS = {
    "timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920",
    "timelineFrameRate": str(FPS), "colorScienceMode": "davinciYRGBColorManaged",
    "isAutoColorManage": "0", "colorSpaceInput": "Rec.2100 HLG",
    "colorSpaceTimeline": "Rec.2100 HLG", "colorSpaceOutput": "Rec.2100 HLG",
    "colorSpaceOutputToneMapping": "None", "colorSpaceOutputGamutMapping": "None",
}


def run(source_dir: Path, out_dir: Path, project_name: str) -> dict:
    source_dir, root = Path(source_dir).resolve(), Path(out_dir).resolve()
    if root.parent.name != ".local" or root.name != "aakhri-source-color-forensics":
        raise ValueError("PRIVATE_FORENSICS_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_SOURCE_COLOR_IDENTITY_V01", project_name):
        raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "RESOLVE_IDENTITY_ROUNDTRIP_V01.json"
    if report_path.exists():
        raise ValueError("NO_DUPLICATE_REPLAY")
    sources = {}
    for asset_id, _ in SCENES:
        filename, expected, _ = TAKES[asset_id]
        path = source_dir / filename
        digest, size = sha(path)
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
    receipt = {
        "schema": "RESOLVE_IDENTITY_ROUNDTRIP_V01",
        "classification": "PRIVATE_SOURCE_COLOR_FORENSICS_REFERENCE_SAMPLE",
        "full_master_rendered": False, "creative_grade_applied": False,
        "fusion_tools_used": [], "sources_before": sources, "segments": [],
        "governance": {"production_deployment_authorized": False, "publication_authorized": False,
                       "first_real_poster": "PAUSED_BY_NITIN"},
    }
    def save(): report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    try:
        project = pm.CreateProject(project_name)
        if not project:
            raise RuntimeError("PROJECT_CREATE")
        setting_results = {key: bool(project.SetSetting(key, value)) for key, value in PROJECT_SETTINGS.items()}
        if not all(setting_results.values()):
            raise RuntimeError("PROJECT_COLOR_SETTING_REJECTED:" + repr(setting_results))
        actual = {key: str(project.GetSetting(key)) for key in PROJECT_SETTINGS}
        validate_resolve_hlg_settings(actual)
        receipt["project_settings_requested"] = PROJECT_SETTINGS
        receipt["project_settings_actual"] = actual
        receipt["project_setting_results"] = setting_results
        pool = project.GetMediaPool()
        imported = pool.ImportMedia([row["path"] for row in sources.values()])
        if len(imported) != 4:
            raise RuntimeError("IMPORT")
        by_name = {item.GetName(): item for item in imported}
        receipt["resolve_input_interpretation"] = {}
        for asset_id, row in sources.items():
            name = Path(row["path"]).name; item = by_name[name]
            interpretation = {key: item.GetClipProperty(key) for key in (
                "Input Color Space", "Input Gamma", "Video Codec", "Bit Depth", "Resolution", "FPS"
            )}
            if interpretation["Input Color Space"] != "Rec.2100 HLG" or interpretation["Input Gamma"] != "Rec.2100 HLG":
                raise ValueError("RESOLVE_INPUT_INTERPRETATION:" + asset_id + ":" + repr(interpretation))
            receipt["resolve_input_interpretation"][asset_id] = interpretation
        timeline = pool.CreateEmptyTimeline("IDENTITY_ROUNDTRIP_REFERENCE_V01")
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError("TIMELINE")
        origin = timeline.GetStartFrame(); cursor = 0
        for index, (asset_id, seconds) in enumerate(SCENES, 1):
            name = Path(sources[asset_id]["path"]).name; start = round(seconds * FPS)
            clips = pool.AppendToTimeline([{"mediaPoolItem": by_name[name], "startFrame": start,
                "endFrame": start + FPS, "mediaType": 1, "trackIndex": 1,
                "recordFrame": origin + cursor}])
            if len(clips) != 1:
                raise RuntimeError("APPEND:" + str(index))
            receipt["segments"].append({"scene_index": index, "take_asset_id": asset_id,
                "source_sha256": sources[asset_id]["sha256"], "source_time_seconds": seconds,
                "timeline_start_frame": cursor, "timeline_end_frame_exclusive": cursor + FPS,
                "color_operations": [], "fusion_tools": []})
            cursor += FPS
        if cursor != 4 * FPS:
            raise RuntimeError("NOT_FOUR_SECONDS")
        if not project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ"):
            raise RuntimeError("PRORES422HQ_UNAVAILABLE")
        project.SetCurrentRenderMode(1)
        settings = {"SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + cursor - 1,
            "TargetDir": str(root), "CustomName": "IDENTITY_ROUNDTRIP_REFERENCE_V01",
            "ExportVideo": True, "ExportAudio": False, "FormatWidth": 1080,
            "FormatHeight": 1920, "FrameRate": FPS}
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
        output = root / "IDENTITY_ROUNDTRIP_REFERENCE_V01.mov"
        if status.get("JobStatus") != "Complete" or not output.exists():
            raise RuntimeError("RENDER_FAILED:" + repr(status))
        receipt["output"] = {"path": str(output), "sha256": sha(output)[0], "bytes": sha(output)[1],
                             "frames": cursor, "render_status": status}
        if not pm.SaveProject() or not pm.ExportProject(project_name, str(root / (project_name + ".drp")), False):
            raise RuntimeError("PROJECT_EXPORT")
        drp = root / (project_name + ".drp")
        receipt["resolve_project"] = {"path": str(drp), "sha256": sha(drp)[0]}
        receipt["sources_after"] = {aid: {"sha256": sha(row["path"])[0], "bytes": sha(row["path"])[1]}
                                    for aid, row in sources.items()}
        if any(receipt["sources_after"][aid]["sha256"] != row["sha256"] for aid, row in sources.items()):
            raise ValueError("SOURCE_CHANGED")
        receipt["status"] = "IDENTITY_ROUNDTRIP_REFERENCE_RENDERED_PRIVATE_ONLY"
        save()
    finally:
        if project:
            pm.SaveProject(); receipt["project_closed"] = bool(pm.CloseProject(project)); save()
        if original_name:
            receipt["original_restored"] = bool(pm.LoadProject(original_name)); save()
        if original_page:
            resolve.OpenPage(original_page)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("source_dir"); parser.add_argument("out_dir")
    parser.add_argument("project"); args = parser.parse_args()
    run(Path(args.source_dir), Path(args.out_dir), args.project)
