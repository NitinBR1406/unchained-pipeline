"""Render the immutable Aakhri Ishq R3 creative revision in private staging."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from multitake.creative_revision import validate_revision_contract
from resolve.aakhri_multitake_realization import (
    EDL_SHA,
    FPS,
    MASTER_SHA,
    TAKES,
    clip_edl,
    fade_audio,
    frame,
    render,
    sha,
)


def _set_point(tool, name, x, y):
    setattr(tool, name, {1: float(x), 2: float(y)})
    if tool.GetInput(name) is None:
        raise RuntimeError("POINT_INPUT:" + name)


def finish_clip_r3(comp, frames, take_id, timeline_start_ms, contract):
    media = comp.FindTool("MediaIn1")
    out = comp.FindTool("MediaOut1")
    if not media or not out:
        raise RuntimeError("FUSION_IO")
    take = contract["takes"][take_id]

    normalization = comp.AddTool("BrightnessContrast")
    normalization.SetAttrs({"TOOLS_Name": "UN_COLOR_NORMALIZATION"})
    normalization.Input = media.Output
    normalization.Gain = TAKES[take_id][2]

    shot_match = comp.AddTool("BrightnessContrast")
    shot_match.SetAttrs({"TOOLS_Name": "UN_SHOT_MATCH"})
    shot_match.Input = normalization.Output
    shot_match.Contrast = contract["look"]["shot_match"]["contrast"]

    look = comp.AddTool("BrightnessContrast")
    look.SetAttrs({"TOOLS_Name": "UN_R3_RICH_NATURAL_SUBJECT_LOOK"})
    look.Input = shot_match.Output
    look.Gain = contract["look"]["creative_grade"]["gain"]
    look.Contrast = contract["look"]["creative_grade"]["contrast"]
    look.Saturation = contract["look"]["creative_grade"]["saturation"]

    background = comp.AddTool("BrightnessContrast")
    background.SetAttrs({"TOOLS_Name": "UN_R3_BACKGROUND_DEEMPHASIS"})
    background.Input = look.Output
    background.Gain = contract["look"]["background_deemphasis"]["gain"]
    background.Saturation = contract["look"]["background_deemphasis"]["saturation"]
    mask = comp.AddTool("EllipseMask")
    mask.SetAttrs({"TOOLS_Name": "UN_R3_SOFT_SUBJECT_REGION"})
    mask.Width = contract["look"]["background_deemphasis"]["mask"]["width"]
    mask.Height = contract["look"]["background_deemphasis"]["mask"]["height"]
    mask.SoftEdge = contract["look"]["background_deemphasis"]["mask"]["soft_edge"]
    mask.Invert = 1
    _set_point(mask, "Center", *contract["look"]["background_deemphasis"]["mask"]["center"])
    background.EffectMask = mask.Output

    blur = comp.AddTool("Blur")
    blur.SetAttrs({"TOOLS_Name": "UN_R3_BACKGROUND_SOFTENING"})
    blur.Input = background.Output
    blur.BlurSize = contract["look"]["background_deemphasis"]["blur_size"]
    blur.EffectMask = mask.Output

    base = comp.AddTool("Transform")
    base.SetAttrs({"TOOLS_Name": "UN_R3_SAFE_BASE_FRAMING"})
    base.Input = blur.Output
    base.Size = take["base_scale"]
    _set_point(base, "Center", *take["center"])

    motion = comp.AddTool("Transform")
    motion.SetAttrs({"TOOLS_Name": "UN_R3_BEAT_BOUND_MOTION"})
    motion.Input = base.Output
    motion.Size = comp.BezierSpline()
    motion.Angle = comp.BezierSpline()
    motion.Size[0] = 1.0
    motion.Size[max(0, frames - 1)] = 1.0
    motion.Angle[0] = 0.0
    motion.Angle[max(0, frames - 1)] = 0.0
    applied = []
    end_ms = timeline_start_ms + round(frames * 1000 / FPS)
    for event in contract["motion"]["events"]:
        if not (timeline_start_ms <= event["time_ms"] < end_ms):
            continue
        local = frame(event["time_ms"] - timeline_start_ms)
        pre, post = max(0, local - 3), min(frames - 1, local + 7)
        scale = 1.018 if event["motion"] == "GENTLE_PUSH" else 1.035
        motion.Size[pre] = 1.0
        motion.Size[local] = scale
        motion.Size[post] = 1.0
        if event["motion"] == "PUNCH_IN_MICRO_SHAKE":
            motion.Angle[max(0, local - 2)] = 0.0
            motion.Angle[local] = 0.22
            motion.Angle[min(frames - 1, local + 2)] = -0.18
            motion.Angle[min(frames - 1, local + 5)] = 0.0
        applied.append(event)
    out.Input = motion.Output
    return {
        "take_asset_id": take_id,
        "base_framing": take,
        "normalization_gain": TAKES[take_id][2],
        "creative_grade": contract["look"]["creative_grade"],
        "background_deemphasis": contract["look"]["background_deemphasis"],
        "beat_motion_events": applied,
    }


def build_timeline(project, pool, name, items, audio, segments, audio_startf, audio_endf, root, contract, derivative=False):
    timeline = pool.CreateEmptyTimeline(name)
    project.SetCurrentTimeline(timeline)
    origin = timeline.GetStartFrame()
    finishes = []
    cursor = 0
    for segment in segments:
        frames = frame(segment["timeline_end_ms"]) - frame(segment["timeline_start_ms"])
        start = frame(segment["take_start_ms"])
        clips = pool.AppendToTimeline([{"mediaPoolItem": items[segment["take_asset_id"]], "startFrame": start, "endFrame": start + frames, "mediaType": 1, "trackIndex": 1, "recordFrame": origin + cursor}])
        if len(clips) != 1:
            raise RuntimeError("VIDEO_APPEND:" + segment["segment_id"])
        comp = clips[0].AddFusionComp()
        if not comp:
            raise RuntimeError("FUSION_COMP")
        finishes.append({"segment_id": segment["segment_id"], **finish_clip_r3(comp, frames, segment["take_asset_id"], segment["timeline_start_ms"], contract)})
        cursor += frames
    audio_item, startf, endf, lineage = audio, audio_startf, audio_endf, None
    if derivative:
        wav = root / (name + ".wav")
        lineage = fade_audio(audio.GetClipProperty("File Path"), wav, audio_startf, audio_endf)
        audio_item = pool.ImportMedia([str(wav)])[0]
        startf, endf = 0, cursor
    clips = pool.AppendToTimeline([{"mediaPoolItem": audio_item, "startFrame": startf, "endFrame": endf, "mediaType": 2, "trackIndex": 1, "recordFrame": origin}])
    if len(clips) != 1:
        raise RuntimeError("AUDIO_APPEND")
    return timeline, cursor, finishes, lineage


def run(source_dir, edl_path, contract_path, out_dir, project_name):
    source_dir, edl_path, contract_path, root = map(lambda p: Path(p).resolve(), (source_dir, edl_path, contract_path, out_dir))
    if not re.fullmatch(r"aakhri-multitake-realization-r3(?:-repair[0-9]+)?", root.name) or root.parent.name != ".local":
        raise ValueError("PRIVATE_R3_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_MULTITAKE_V01_RUN3(?:_REPAIR[0-9]+)?", project_name):
        raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True, exist_ok=True)
    report = root / (project_name + ".json")
    if report.exists():
        raise ValueError("NO_DUPLICATE_REPLAY")
    edl, contract = json.loads(edl_path.read_text()), json.loads(contract_path.read_text())
    if edl.get("edl_sha256") != EDL_SHA:
        raise ValueError("EDL_DRIFT")
    validate_revision_contract(contract)
    before = {"edl": {"path": str(edl_path), "sha256": sha(edl_path)[0]}, "contract": {"path": str(contract_path), "sha256": sha(contract_path)[0]}, "takes": {}, "master": {}}
    for asset, (name, expected, _) in TAKES.items():
        path = source_dir / name
        got, size = sha(path)
        if got != expected:
            raise ValueError("TAKE_DRIFT:" + asset)
        before["takes"][asset] = {"path": str(path), "sha256": got, "bytes": size}
    master = source_dir / "AAKHRI ISHQ MASTER 2.wav"
    got, size = sha(master)
    if got != MASTER_SHA:
        raise ValueError("MASTER_DRIFT")
    before["master"] = {"path": str(master), "sha256": got, "bytes": size}
    import DaVinciResolveScript as d
    resolve = d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName() != "DaVinci Resolve Studio":
        raise RuntimeError("RESOLVE_UNAVAILABLE")
    pm = resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder():
        raise ValueError("NO_DUPLICATE_PROJECT")
    original = pm.GetCurrentProject()
    original_name = original.GetName() if original else None
    page = resolve.GetCurrentPage()
    project = None
    receipt = {"schema": "RESOLVE_MULTI_TAKE_R3_REALIZATION_V01", "scope": "PRIVATE_NON_PUBLISHING_CREATIVE_REVISION", "project": project_name, "inputs_before": before, "outputs": [], "run2_immutable": True, "governance": contract["governance"]}
    def save():
        report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    try:
        project = pm.CreateProject(project_name)
        if not project or not project.SetSettings({"timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920", "timelineFrameRate": "30"}):
            raise RuntimeError("PROJECT_SETUP")
        pool = project.GetMediaPool()
        imported = pool.ImportMedia([v["path"] for v in before["takes"].values()] + [before["master"]["path"]])
        if len(imported) != 5:
            raise RuntimeError("IMPORT")
        by_name = {item.GetName(): item for item in imported}
        items = {asset: by_name[name] for asset, (name, _, _) in TAKES.items()}
        audio = by_name[master.name]
        name = "AAKHRI_MULTITAKE_MASTER_V01_RUN3"
        timeline, frames, finishing, _ = build_timeline(project, pool, name, items, audio, edl["segments"], 0, frame(214400), root, contract)
        output = render(project, timeline, root, name, frames)
        output.update(fusion_finishing=finishing, audio_route="AUTHORITATIVE_MASTER_ONLY")
        receipt["outputs"].append(output); save()
        for derivative in edl["derivatives"]:
            segments = clip_edl(edl, derivative["start_ms"], derivative["end_ms"])
            name = "AAKHRI_" + derivative["derivative_id"] + "_V01_RUN3"
            timeline, frames, finishing, lineage = build_timeline(project, pool, name, items, audio, segments, frame(derivative["start_ms"]), frame(derivative["end_ms"]), root, contract, True)
            output = render(project, timeline, root, name, frames)
            output.update(fusion_finishing=finishing, audio_route="AUTHORITATIVE_MASTER_ONLY", audio_lineage=lineage, derivative_range_ms=[derivative["start_ms"], derivative["end_ms"]])
            receipt["outputs"].append(output); save()
        if not pm.SaveProject() or not pm.ExportProject(project_name, str(root / (project_name + ".drp")), False):
            raise RuntimeError("PROJECT_EXPORT")
        receipt["resolve_project_archive"] = {"path": str(root / (project_name + ".drp")), "sha256": sha(root / (project_name + ".drp"))[0], "bytes": sha(root / (project_name + ".drp"))[1]}
        receipt["status"] = "R3_RENDER_COMPLETE_PRIVATE_ONLY"; save()
    finally:
        if project:
            pm.SaveProject(); receipt["project_closed"] = pm.CloseProject(project); save()
        if original_name:
            receipt["original_restored"] = bool(pm.LoadProject(original_name)); save()
        if page:
            resolve.OpenPage(page)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir"); parser.add_argument("edl"); parser.add_argument("contract"); parser.add_argument("out_dir"); parser.add_argument("project")
    args = parser.parse_args()
    run(args.source_dir, args.edl, args.contract, args.out_dir, args.project)
