"""Render matched V01-current/V02-new face-background softness samples only."""
from __future__ import annotations
import argparse,json,re,shutil,time
from pathlib import Path
from multitake.r1_face_background_softness import VARIANTS,load,sha256,write_cube
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS,TAKES,sha

SETTINGS={'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':str(FPS),'colorScienceMode':'davinciYRGBColorManaged','isAutoColorManage':'0','colorSpaceInput':'Rec.2100 HLG','colorSpaceTimeline':'Rec.2100 HLG','colorSpaceOutput':'Rec.2100 HLG','colorSpaceOutputToneMapping':'None','colorSpaceOutputGamutMapping':'None'}

def point(tool,name,v):
    setattr(tool,name,{1:float(v[0]),2:float(v[1])})
    if tool.GetInput(name) is None: raise RuntimeError('POINT:'+name)

def wait(project,job,out):
    deadline=time.monotonic()+1500
    while project.IsRenderingInProgress() and time.monotonic()<deadline:time.sleep(.5)
    if project.IsRenderingInProgress():project.StopRendering();raise RuntimeError('TIMEOUT')
    s=project.GetRenderJobStatus(job);project.DeleteRenderJob(job)
    if s.get('JobStatus')!='Complete' or not out.exists():raise RuntimeError('RENDER:'+repr(s))
    return s

def run(source_dir,contract_path,root,project_name):
    source_dir,contract_path,root=[Path(x).resolve() for x in (source_dir,contract_path,root)]
    if root.parent.name!='.local' or root.name!='aakhri-r1-face-background-softness-v02':raise ValueError('PRIVATE_STAGING')
    if project_name!='UNCHAINED_AAKHRI_R1_FACE_BACKGROUND_SOFTNESS_V02':raise ValueError('PROJECT')
    root.mkdir(parents=True,exist_ok=True);report=root/'RESOLVE_R1_FACE_BACKGROUND_SOFTNESS_V02.json'
    if report.exists():raise ValueError('NO_DUPLICATE_REPLAY')
    c=load(contract_path);seconds=c['segment_seconds'];frames=round(seconds*FPS);sources={}
    for scene in c['representative_scenes']:
        aid=scene['take_asset_id'];name,expected,_=TAKES[aid];p=source_dir/name;got,size=sha(p)
        if got!=expected:raise ValueError('SOURCE_DRIFT:'+aid)
        sources[aid]={'path':str(p),'sha256':got,'bytes':size}
    current=Path(c['baseline']['lut_path']).resolve()
    if sha256(current)!=c['baseline']['lut_sha256']:raise ValueError('BASELINE_LUT_DRIFT')
    revised=write_cube(root/'luts'/'NEW_V02_GENTLER_FACE_CALMER_BACKGROUND.cube')
    luts={VARIANTS[0]:{'path':str(current),'sha256':sha256(current),'operation':'EXACT_V01_REVISED_HLG_BASELINE'},VARIANTS[1]:revised}
    import DaVinciResolveScript as d
    resolve=d.scriptapp('Resolve')
    if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio':raise RuntimeError('RESOLVE')
    pm=resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder():raise ValueError('NO_DUPLICATE_PROJECT')
    old=pm.GetCurrentProject();oldn=old.GetName() if old else None;page=resolve.GetCurrentPage();project=None
    receipt={'schema':'RESOLVE_R1_FACE_BACKGROUND_SOFTNESS_V02','classification':'PRIVATE_V02_COLOR_REVIEW_COMPARISON','contract_sha256':sha256(contract_path),'sources_before':sources,'luts':luts,'segments':[],'outputs':[],'full_master_rendered':False,'static_masks_used':False,'blur_used':False,'creative_motion_used':False,'governance':c['governance']}
    def save():report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    try:
        project=pm.CreateProject(project_name)
        if not project:raise RuntimeError('CREATE')
        results={k:bool(project.SetSetting(k,v)) for k,v in SETTINGS.items()}
        if not all(results.values()):raise RuntimeError('COLOR_SETTINGS:'+repr(results))
        actual={k:str(project.GetSetting(k)) for k in SETTINGS};validate_resolve_hlg_settings(actual);receipt['project_settings_actual']=actual
        lutroot=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_R1_FACE_BACKGROUND_SOFTNESS_V02');lutroot.mkdir(parents=True,exist_ok=True)
        for v in VARIANTS:
            dst=lutroot/(v+'.cube');shutil.copy2(luts[v]['path'],dst);luts[v]['resolve_discovered_path']=str(dst)
        if not project.RefreshLUTList():raise RuntimeError('REFRESH_LUT')
        pool=project.GetMediaPool();imports=pool.ImportMedia([x['path'] for x in sources.values()]);
        if len(imports)!=4:raise RuntimeError('IMPORT')
        by={x.GetName():x for x in imports};receipt['input_interpretation']={}
        for aid,row in sources.items():
            item=by[Path(row['path']).name];props={k:item.GetClipProperty(k) for k in ('Input Color Space','Input Gamma','Video Codec','Bit Depth','Resolution','FPS')}
            if props['Input Color Space']!='Rec.2100 HLG' or props['Input Gamma']!='Rec.2100 HLG' or str(props['Bit Depth'])!='10':raise ValueError('INPUT:'+aid+repr(props))
            receipt['input_interpretation'][aid]=props
        tl=pool.CreateEmptyTimeline('AAKHRI_R1_V01_CURRENT_VS_V02_NEW_HLG_V02');project.SetCurrentTimeline(tl);origin=tl.GetStartFrame();cursor=0
        for scene in c['representative_scenes']:
            aid=scene['take_asset_id'];name=Path(sources[aid]['path']).name;start=round(scene['source_time_seconds']*FPS);framing=c['base_framing'][aid]
            for variant in VARIANTS:
                clips=pool.AppendToTimeline([{'mediaPoolItem':by[name],'startFrame':start,'endFrame':start+frames,'mediaType':1,'trackIndex':1,'recordFrame':origin+cursor}])
                if len(clips)!=1:raise RuntimeError('APPEND')
                clip=clips[0]
                if not clip.SetLUT(1,luts[variant]['resolve_discovered_path']):raise RuntimeError('LUT:'+variant)
                comp=clip.AddFusionComp();media,out=comp.FindTool('MediaIn1'),comp.FindTool('MediaOut1');base=comp.AddTool('Transform');base.SetAttrs({'TOOLS_Name':'UN_R3_SAFE_BASE_FRAMING_PRESERVED'});base.Input=media.Output;base.Size=framing['base_scale'];point(base,'Center',framing['center']);out.Input=base.Output
                receipt['segments'].append({'scene_index':scene['scene_index'],'take_asset_id':aid,'source_sha256':sources[aid]['sha256'],'source_time_seconds':scene['source_time_seconds'],'duration_seconds':seconds,'variant':variant,'timeline_start_frame':cursor,'timeline_end_frame_exclusive':cursor+frames,'base_framing':framing,'lut_sha256':luts[variant]['sha256'],'spatial_mask':False,'blur':False,'creative_motion':False});cursor+=frames
        if cursor!=4*2*frames:raise RuntimeError('DURATION')
        if not project.SetCurrentRenderFormatAndCodec('mov','ProRes422HQ'):raise RuntimeError('PRORES')
        project.SetCurrentRenderMode(1);out=root/'AAKHRI_R1_V01_CURRENT_VS_V02_NEW_HLG_V02.mov'
        if not project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+cursor-1,'TargetDir':str(root),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':False,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS}):raise RuntimeError('SETTINGS')
        job=project.AddRenderJob();
        if not job or not project.StartRendering([job],False):raise RuntimeError('START')
        status=wait(project,job,out);receipt['outputs'].append({'role':'AUTHORITATIVE_HDR_V01_CURRENT_VS_V02_NEW','path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1],'frames':cursor,'status':status})
        if not pm.SaveProject() or not pm.ExportProject(project_name,str(root/(project_name+'.drp')),False):raise RuntimeError('EXPORT')
        drp=root/(project_name+'.drp');receipt['resolve_project']={'path':str(drp),'sha256':sha256(drp)};receipt['sources_after']={a:{'sha256':sha(Path(r['path']))[0],'bytes':sha(Path(r['path']))[1]} for a,r in sources.items()}
        if any(receipt['sources_after'][a]['sha256']!=r['sha256'] for a,r in sources.items()):raise ValueError('SOURCE_CHANGED')
        receipt['status']='R1_V02_FACE_BACKGROUND_SOFTNESS_RENDERED_PRIVATE_ONLY';save()
    finally:
        if project:pm.SaveProject();receipt['project_closed']=bool(pm.CloseProject(project));save()
        if oldn:receipt['original_restored']=bool(pm.LoadProject(oldn));save()
        if page:resolve.OpenPage(page)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source_dir');p.add_argument('contract');p.add_argument('out_dir');p.add_argument('project');a=p.parse_args();run(a.source_dir,a.contract,a.out_dir,a.project)
