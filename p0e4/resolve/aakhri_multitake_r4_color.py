"""Render the SHA-bound R4 Color Review Candidate without changing R3 edit state."""
from __future__ import annotations

import argparse, json, re
from pathlib import Path

from multitake.color_development import sha256, validate_color_contract
from resolve.aakhri_multitake_realization import EDL_SHA, FPS, MASTER_SHA, TAKES, frame, render, sha


def _point(tool, name, values):
    setattr(tool, name, {1: float(values[0]), 2: float(values[1])})
    if tool.GetInput(name) is None: raise RuntimeError("POINT_INPUT:" + name)


def finish_clip(comp, frames, take_id, timeline_start_ms, r3, r4):
    media, out = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
    if not media or not out: raise RuntimeError("FUSION_IO")
    sep = r4["subject_background_separation"]
    background = comp.AddTool("BrightnessContrast"); background.SetAttrs({"TOOLS_Name": "UN_R4_BOUNDED_BACKGROUND_SEPARATION"})
    background.Input = media.Output; background.Gain = sep["gain"]; background.Saturation = sep["saturation"]
    mask = comp.AddTool("EllipseMask"); mask.SetAttrs({"TOOLS_Name": "UN_R4_SOFT_STATIC_SUBJECT_REGION"})
    mask.Width = sep["mask"]["width"]; mask.Height = sep["mask"]["height"]; mask.SoftEdge = sep["mask"]["soft_edge"]; mask.Invert = 1
    _point(mask, "Center", sep["mask"]["center"]); background.EffectMask = mask.Output
    blur = comp.AddTool("Blur"); blur.SetAttrs({"TOOLS_Name": "UN_R4_BACKGROUND_SOFTENING"}); blur.Input = background.Output
    blur.BlurSize = sep["blur_size"]; blur.EffectMask = mask.Output
    take = r3["takes"][take_id]
    base = comp.AddTool("Transform"); base.SetAttrs({"TOOLS_Name": "UN_R3_SAFE_BASE_FRAMING_PRESERVED"}); base.Input = blur.Output
    base.Size = take["base_scale"]; _point(base, "Center", take["center"])
    motion = comp.AddTool("Transform"); motion.SetAttrs({"TOOLS_Name": "UN_R3_BEAT_BOUND_MOTION_PRESERVED"}); motion.Input = base.Output
    motion.Size = comp.BezierSpline(); motion.Angle = comp.BezierSpline(); motion.Size[0] = 1.0; motion.Size[max(0,frames-1)] = 1.0
    motion.Angle[0] = 0.0; motion.Angle[max(0,frames-1)] = 0.0; applied=[]
    end_ms = timeline_start_ms + round(frames*1000/FPS)
    for event in r3["motion"]["events"]:
        if not timeline_start_ms <= event["time_ms"] < end_ms: continue
        local=frame(event["time_ms"]-timeline_start_ms); pre=max(0,local-3); post=min(frames-1,local+7)
        motion.Size[pre]=1.0; motion.Size[local]=1.018 if event["motion"]=="GENTLE_PUSH" else 1.035; motion.Size[post]=1.0
        if event["motion"]=="PUNCH_IN_MICRO_SHAKE":
            motion.Angle[max(0,local-2)]=0.0; motion.Angle[local]=0.22; motion.Angle[min(frames-1,local+2)]=-0.18; motion.Angle[min(frames-1,local+5)]=0.0
        applied.append(event)
    out.Input = motion.Output
    return {"take_asset_id":take_id,"base_framing":take,"beat_motion_events":applied,"separation":sep}


def run(source_dir, edl_path, r3_path, r4_path, out_dir, project_name):
    source_dir, edl_path, r3_path, r4_path, root = [Path(x).resolve() for x in (source_dir,edl_path,r3_path,r4_path,out_dir)]
    if root.parent.name != ".local" or not re.fullmatch(r"aakhri-multitake-realization-r4-color(?:-repair[0-9]+)?",root.name): raise ValueError("PRIVATE_R4_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_MULTITAKE_V01_RUN4_COLOR(?:_REPAIR[0-9]+)?",project_name): raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True,exist_ok=True); report=root/(project_name+".json")
    if report.exists(): raise ValueError("NO_DUPLICATE_REPLAY")
    edl=json.loads(edl_path.read_text()); r3=json.loads(r3_path.read_text()); r4=json.loads(r4_path.read_text()); validate_color_contract(r4)
    if edl.get("edl_sha256") != EDL_SHA or sha256(edl_path) != r4["authorized_basis"]["edl_sha256"]: raise ValueError("EDL_DRIFT")
    if sha256(r3_path) != r4["authorized_basis"]["r3_contract_sha256"]: raise ValueError("R3_CONTRACT_DRIFT")
    r3_master=Path(".local/aakhri-multitake-realization-r3-repair5/AAKHRI_MULTITAKE_MASTER_V01_RUN3.mp4").resolve()
    if sha256(r3_master) != r4["authorized_basis"]["r3_candidate_sha256"]: raise ValueError("R3_CANDIDATE_DRIFT")
    before={"edl":{"path":str(edl_path),"sha256":sha256(edl_path)},"r3_contract":{"path":str(r3_path),"sha256":sha256(r3_path)},"r3_candidate":{"path":str(r3_master),"sha256":sha256(r3_master)},"takes":{},"master":{}}
    for asset,(name,expected,_) in TAKES.items():
        path=source_dir/name; got,size=sha(path)
        if got != expected: raise ValueError("TAKE_DRIFT:"+asset)
        before["takes"][asset]={"path":str(path),"sha256":got,"bytes":size}
    master=source_dir/"AAKHRI ISHQ MASTER 2.wav"; got,size=sha(master)
    if got != MASTER_SHA: raise ValueError("MASTER_DRIFT")
    before["master"]={"path":str(master),"sha256":got,"bytes":size}
    import DaVinciResolveScript as d
    resolve=d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName()!="DaVinci Resolve Studio": raise RuntimeError("RESOLVE_UNAVAILABLE")
    pm=resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder(): raise ValueError("NO_DUPLICATE_PROJECT")
    original=pm.GetCurrentProject(); original_name=original.GetName() if original else None; page=resolve.GetCurrentPage(); project=None
    receipt={"schema":"RESOLVE_R4_COLOR_REALIZATION_V01","classification":"COLOR_REVIEW_CANDIDATE","inputs_before":before,"project":project_name,"outputs":[],"r3_edit_state_preserved":r4["preserved_r3"],"known_r3_defects":r4["known_r3_defects"],"governance":r4["governance"]}
    def save(): report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    try:
        project=pm.CreateProject(project_name)
        if not project or not project.SetSettings({"timelineResolutionWidth":"1080","timelineResolutionHeight":"1920","timelineFrameRate":"30"}): raise RuntimeError("PROJECT_SETUP")
        pool=project.GetMediaPool(); imported=pool.ImportMedia([v["path"] for v in before["takes"].values()]+[before["master"]["path"]])
        if len(imported)!=5: raise RuntimeError("IMPORT")
        by={x.GetName():x for x in imported}; items={a:by[n] for a,(n,_,_) in TAKES.items()}; audio=by[master.name]
        name="AAKHRI_MULTITAKE_MASTER_V01_RUN4_COLOR_REVIEW"; timeline=pool.CreateEmptyTimeline(name); project.SetCurrentTimeline(timeline); origin=timeline.GetStartFrame(); cursor=0; finishes=[]
        for segment in edl["segments"]:
            frames=frame(segment["timeline_end_ms"])-frame(segment["timeline_start_ms"]); start=frame(segment["take_start_ms"])
            clips=pool.AppendToTimeline([{"mediaPoolItem":items[segment["take_asset_id"]],"startFrame":start,"endFrame":start+frames,"mediaType":1,"trackIndex":1,"recordFrame":origin+cursor}])
            if len(clips)!=1: raise RuntimeError("VIDEO_APPEND:"+segment["segment_id"])
            comp=clips[0].AddFusionComp()
            if not comp: raise RuntimeError("FUSION_COMP")
            fin=finish_clip(comp,frames,segment["take_asset_id"],segment["timeline_start_ms"],r3,r4)
            cdl=r4["takes"][segment["take_asset_id"]]["cdl"]
            if not clips[0].SetCDL(cdl): raise RuntimeError("COLOR_PAGE_CDL")
            finishes.append({"segment_id":segment["segment_id"],**fin,"resolve_color_page_cdl":cdl}); cursor+=frames
        aclips=pool.AppendToTimeline([{"mediaPoolItem":audio,"startFrame":0,"endFrame":frame(214400),"mediaType":2,"trackIndex":1,"recordFrame":origin}])
        if len(aclips)!=1: raise RuntimeError("AUDIO_APPEND")
        output=render(project,timeline,root,name,cursor); output.update(audio_route="AUTHORITATIVE_MASTER_ONLY",color_pipeline=r4["stage_order"],clip_finishing=finishes)
        receipt["outputs"].append(output); save()
        if not pm.SaveProject() or not pm.ExportProject(project_name,str(root/(project_name+".drp")),False): raise RuntimeError("PROJECT_EXPORT")
        receipt["resolve_project_archive"]={"path":str(root/(project_name+".drp")),"sha256":sha256(root/(project_name+".drp"))}
        receipt["status"]="R4_COLOR_RENDER_COMPLETE_PRIVATE_ONLY"; save()
    finally:
        if project: pm.SaveProject(); receipt["project_closed"]=pm.CloseProject(project); save()
        if original_name: receipt["original_restored"]=bool(pm.LoadProject(original_name)); save()
        if page: resolve.OpenPage(page)
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("source_dir"); p.add_argument("edl"); p.add_argument("r3_contract"); p.add_argument("r4_contract"); p.add_argument("out_dir"); p.add_argument("project"); a=p.parse_args()
    run(a.source_dir,a.edl,a.r3_contract,a.r4_contract,a.out_dir,a.project)
