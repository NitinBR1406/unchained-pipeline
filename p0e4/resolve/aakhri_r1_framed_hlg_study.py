"""Render the bounded R1 framed HLG comparison matrix; never a full master."""
from __future__ import annotations

import argparse, json, re, shutil, time
from pathlib import Path

from multitake.r1_framed_color_study import VARIANTS, load, sha256, write_cube
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS, TAKES, sha


SETTINGS = {
    "timelineResolutionWidth":"1080", "timelineResolutionHeight":"1920", "timelineFrameRate":str(FPS),
    "colorScienceMode":"davinciYRGBColorManaged", "isAutoColorManage":"0",
    "colorSpaceInput":"Rec.2100 HLG", "colorSpaceTimeline":"Rec.2100 HLG", "colorSpaceOutput":"Rec.2100 HLG",
    "colorSpaceOutputToneMapping":"None", "colorSpaceOutputGamutMapping":"None",
}


def _point(tool, name, value):
    setattr(tool, name, {1:float(value[0]), 2:float(value[1])})
    if tool.GetInput(name) is None: raise RuntimeError("POINT_INPUT:"+name)


def _wait(project, job, output):
    deadline=time.monotonic()+1800
    while project.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(.5)
    if project.IsRenderingInProgress(): project.StopRendering(); raise RuntimeError("RENDER_TIMEOUT")
    status=project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
    if status.get("JobStatus")!="Complete" or not output.exists(): raise RuntimeError("RENDER_FAILED:"+repr(status))
    return status


def run(source_dir: Path, contract_path: Path, root: Path, project_name: str) -> dict:
    source_dir,contract_path,root=[Path(x).resolve() for x in (source_dir,contract_path,root)]
    if root.parent.name != ".local" or not re.fullmatch(r"aakhri-r1-framed-hlg-study(?:-retry[0-9]+)?",root.name): raise ValueError("PRIVATE_STAGING_ONLY")
    if not re.fullmatch(r"UNCHAINED_AAKHRI_R1_FRAMED_HLG_STUDY_V01(?:_RETRY[0-9]+)?",project_name): raise ValueError("PROJECT_NAME")
    root.mkdir(parents=True,exist_ok=True); report=root/"RESOLVE_R1_FRAMED_HLG_STUDY_V01.json"
    if report.exists(): raise ValueError("NO_DUPLICATE_REPLAY")
    contract=load(contract_path); seconds=contract["segment_seconds"]; frames=round(seconds*FPS)
    sources={}
    for scene in contract["representative_scenes"]:
        aid=scene["take_asset_id"]; name,expected,_=TAKES[aid]; p=source_dir/name; got,size=sha(p)
        if got!=expected: raise ValueError("SOURCE_DRIFT:"+aid)
        sources[aid]={"path":str(p),"sha256":got,"bytes":size}
    luts={v:write_cube(root/"luts"/(v+".cube"),v) for v in VARIANTS}
    import DaVinciResolveScript as d
    resolve=d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName()!="DaVinci Resolve Studio": raise RuntimeError("RESOLVE_STUDIO_UNAVAILABLE")
    pm=resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder(): raise ValueError("NO_DUPLICATE_PROJECT")
    old=pm.GetCurrentProject(); old_name=old.GetName() if old else None; old_page=resolve.GetCurrentPage(); project=None
    receipt={"schema":"RESOLVE_R1_FRAMED_HLG_STUDY_V01","classification":"PRIVATE_COLOR_REVIEW_MATRIX",
      "contract":{"path":str(contract_path),"sha256":sha256(contract_path)},"sources_before":sources,"luts":luts,
      "full_master_rendered":False,"static_masks_used":False,"blur_used":False,"creative_motion_used":False,
      "segments":[],"outputs":[],"governance":contract["governance"]}
    def save(): report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    try:
        project=pm.CreateProject(project_name)
        if not project: raise RuntimeError("PROJECT_CREATE")
        results={k:bool(project.SetSetting(k,v)) for k,v in SETTINGS.items()}
        if not all(results.values()): raise RuntimeError("COLOR_SETTINGS:"+repr(results))
        actual={k:str(project.GetSetting(k)) for k in SETTINGS}; validate_resolve_hlg_settings(actual)
        receipt["project_settings_actual"]=actual; receipt["project_setting_results"]=results
        discovered_root=Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_R1_FRAMED_HLG_V01")
        discovered_root.mkdir(parents=True,exist_ok=True)
        for variant in VARIANTS:
            target=discovered_root/(variant+".cube"); shutil.copy2(luts[variant]["path"],target)
            luts[variant]["resolve_discovered_path"]=str(target)
        if not project.RefreshLUTList(): raise RuntimeError("REFRESH_LUT_LIST")
        pool=project.GetMediaPool(); imported=pool.ImportMedia([x["path"] for x in sources.values()])
        if len(imported)!=4: raise RuntimeError("IMPORT")
        by={x.GetName():x for x in imported}; receipt["input_interpretation"]={}
        for aid,row in sources.items():
            item=by[Path(row["path"]).name]; props={k:item.GetClipProperty(k) for k in ("Input Color Space","Input Gamma","Video Codec","Bit Depth","Resolution","FPS")}
            if props["Input Color Space"]!="Rec.2100 HLG" or props["Input Gamma"]!="Rec.2100 HLG" or str(props["Bit Depth"])!="10": raise ValueError("INPUT_INTERPRETATION:"+aid+":"+repr(props))
            receipt["input_interpretation"][aid]=props
        tl=pool.CreateEmptyTimeline("AAKHRI_R1_FRAMED_HLG_MATRIX_V01"); project.SetCurrentTimeline(tl); origin=tl.GetStartFrame(); cursor=0
        for scene in contract["representative_scenes"]:
            aid=scene["take_asset_id"]; name=Path(sources[aid]["path"]).name; start=round(scene["source_time_seconds"]*FPS)
            framing=contract["base_framing"][aid]
            for variant in VARIANTS:
                clips=pool.AppendToTimeline([{"mediaPoolItem":by[name],"startFrame":start,"endFrame":start+frames,"mediaType":1,"trackIndex":1,"recordFrame":origin+cursor}])
                if len(clips)!=1: raise RuntimeError("APPEND")
                clip=clips[0]
                if not clip.SetLUT(1,luts[variant]["resolve_discovered_path"]): raise RuntimeError("SET_LUT:"+variant)
                comp=clip.AddFusionComp(); media,out=comp.FindTool("MediaIn1"),comp.FindTool("MediaOut1")
                base=comp.AddTool("Transform"); base.SetAttrs({"TOOLS_Name":"UN_R3_SAFE_BASE_FRAMING_PRESERVED"}); base.Input=media.Output
                base.Size=framing["base_scale"]; _point(base,"Center",framing["center"]); out.Input=base.Output
                receipt["segments"].append({"scene_index":scene["scene_index"],"take_asset_id":aid,"source_sha256":sources[aid]["sha256"],
                  "source_time_seconds":scene["source_time_seconds"],"duration_seconds":seconds,"variant":variant,
                  "timeline_start_frame":cursor,"timeline_end_frame_exclusive":cursor+frames,"base_framing":framing,
                  "lut_sha256":luts[variant]["sha256"],"spatial_mask":False,"blur":False,"creative_motion":False})
                cursor+=frames
        if cursor!=len(contract["representative_scenes"])*len(VARIANTS)*frames: raise RuntimeError("DURATION")
        if not project.SetCurrentRenderFormatAndCodec("mov","ProRes422HQ"): raise RuntimeError("PRORES_UNAVAILABLE")
        project.SetCurrentRenderMode(1); output=root/"AAKHRI_R1_FRAMED_HLG_MATRIX_V01.mov"
        if not project.SetRenderSettings({"SelectAllFrames":False,"MarkIn":origin,"MarkOut":origin+cursor-1,"TargetDir":str(root),"CustomName":output.stem,
          "ExportVideo":True,"ExportAudio":False,"FormatWidth":1080,"FormatHeight":1920,"FrameRate":FPS}): raise RuntimeError("RENDER_SETTINGS")
        job=project.AddRenderJob()
        if not job or not project.StartRendering([job],False): raise RuntimeError("RENDER_START")
        status=_wait(project,job,output); receipt["outputs"].append({"role":"AUTHORITATIVE_HDR_REVIEW_MATRIX","path":str(output),"sha256":sha(output)[0],"bytes":sha(output)[1],"frames":cursor,"status":status})
        if not pm.SaveProject() or not pm.ExportProject(project_name,str(root/(project_name+".drp")),False): raise RuntimeError("PROJECT_EXPORT")
        drp=root/(project_name+".drp"); receipt["resolve_project"]={"path":str(drp),"sha256":sha256(drp)}
        receipt["sources_after"]={a:{"sha256":sha(Path(r["path"]))[0],"bytes":sha(Path(r["path"]))[1]} for a,r in sources.items()}
        if any(receipt["sources_after"][a]["sha256"]!=r["sha256"] for a,r in sources.items()): raise ValueError("SOURCE_CHANGED")
        receipt["status"]="R1_FRAMED_HLG_MATRIX_RENDERED_PRIVATE_ONLY"; save()
    finally:
        if project: pm.SaveProject(); receipt["project_closed"]=bool(pm.CloseProject(project)); save()
        if old_name: receipt["original_restored"]=bool(pm.LoadProject(old_name)); save()
        if old_page: resolve.OpenPage(old_page)
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("source_dir"); p.add_argument("contract"); p.add_argument("out_dir"); p.add_argument("project"); a=p.parse_args()
    run(Path(a.source_dir),Path(a.contract),Path(a.out_dir),a.project)
