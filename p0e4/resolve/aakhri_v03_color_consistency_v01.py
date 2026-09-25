"""Render selected V03 color across longer real-EDL excerpts; never a full master."""
from __future__ import annotations
import argparse,json,shutil,time
from pathlib import Path
from multitake.v03_color_consistency import load
from multitake.r1_peak_highlights_eyelids import sha256
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS,MASTER_SHA,TAKES,sha

SETTINGS={'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':str(FPS),'colorScienceMode':'davinciYRGBColorManaged','isAutoColorManage':'0','colorSpaceInput':'Rec.2100 HLG','colorSpaceTimeline':'Rec.2100 HLG','colorSpaceOutput':'Rec.2100 HLG','colorSpaceOutputToneMapping':'None','colorSpaceOutputGamutMapping':'None'}
def frame(ms): return round(ms*FPS/1000)
def point(tool,name,v):
    setattr(tool,name,{1:float(v[0]),2:float(v[1])})
    if tool.GetInput(name) is None: raise RuntimeError('POINT:'+name)
def wait(project,job,out):
    deadline=time.monotonic()+1800
    while project.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(.5)
    if project.IsRenderingInProgress(): project.StopRendering(); raise RuntimeError('TIMEOUT')
    status=project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
    if status.get('JobStatus')!='Complete' or not out.exists(): raise RuntimeError('RENDER:'+repr(status))
    return status

def run(source_dir,contract_path,out_dir,project_name):
    source_dir,contract_path,out_dir=[Path(x).resolve() for x in (source_dir,contract_path,out_dir)]
    if out_dir.parent.name!='.local' or out_dir.name!='aakhri-v03-color-consistency-v01': raise ValueError('PRIVATE_STAGING')
    if project_name!='UNCHAINED_AAKHRI_V03_COLOR_CONSISTENCY_V01': raise ValueError('PROJECT')
    out_dir.mkdir(parents=True,exist_ok=True); report=out_dir/'RESOLVE_V03_COLOR_CONSISTENCY_V01.json'
    if report.exists(): raise ValueError('NO_DUPLICATE_REPLAY')
    c=load(contract_path); edl=json.loads(Path(c['edl_path']).read_text())
    if edl['edl_sha256']!=c['edl_semantic_sha256']: raise ValueError('EDL_DRIFT')
    master=source_dir/'AAKHRI ISHQ MASTER 2.wav'; master_hash,master_size=sha(master)
    if master_hash!=MASTER_SHA: raise ValueError('MASTER_DRIFT')
    sources={}
    for aid,(name,expected,_) in TAKES.items():
        p=source_dir/name; got,n=sha(p)
        if got!=expected: raise ValueError('SOURCE_DRIFT:'+aid)
        sources[aid]={'path':str(p),'sha256':got,'bytes':n}
    lut=Path(c['v03_lut_path']).resolve()
    if sha256(lut)!=c['v03_lut_sha256']: raise ValueError('LUT_DRIFT')
    import DaVinciResolveScript as d
    resolve=d.scriptapp('Resolve')
    if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio': raise RuntimeError('RESOLVE')
    pm=resolve.GetProjectManager()
    if project_name in pm.GetProjectListInCurrentFolder(): raise ValueError('NO_DUPLICATE_PROJECT')
    old=pm.GetCurrentProject(); oldn=old.GetName() if old else None; page=resolve.GetCurrentPage(); project=None
    receipt={'schema':'RESOLVE_V03_COLOR_CONSISTENCY_V01','classification':'PRIVATE_COLOR_CONSISTENCY_REVIEW','contract_sha256':sha256(contract_path),'edl_semantic_sha256':edl['edl_sha256'],'programme_audio':{'path':str(master),'sha256':master_hash,'bytes':master_size},'sources_before':sources,'timeline_windows_ms':c['timeline_windows_ms'],'segments':[],'full_master_rendered':False,'creative_motion_enabled':False,'outputs':[],'governance':c['governance']}
    def save(): report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    try:
        project=pm.CreateProject(project_name)
        if not project: raise RuntimeError('CREATE')
        results={k:bool(project.SetSetting(k,v)) for k,v in SETTINGS.items()}
        if not all(results.values()): raise RuntimeError('COLOR_SETTINGS:'+repr(results))
        actual={k:str(project.GetSetting(k)) for k in SETTINGS}; validate_resolve_hlg_settings(actual); receipt['project_settings_actual']=actual
        lutroot=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_V03_COLOR_CONSISTENCY_V01'); lutroot.mkdir(parents=True,exist_ok=True)
        lutdst=lutroot/lut.name; shutil.copy2(lut,lutdst)
        if not project.RefreshLUTList(): raise RuntimeError('REFRESH_LUT')
        pool=project.GetMediaPool(); imports=pool.ImportMedia([r['path'] for r in sources.values()]+[str(master)])
        by={x.GetName():x for x in imports}; audio=by[master.name]
        for aid,row in sources.items():
            props={k:by[Path(row['path']).name].GetClipProperty(k) for k in ('Input Color Space','Input Gamma','Video Codec','Bit Depth','Resolution','FPS')}
            if props['Input Color Space']!='Rec.2100 HLG' or props['Input Gamma']!='Rec.2100 HLG' or str(props['Bit Depth'])!='10': raise ValueError('INPUT:'+aid+repr(props))
        tl=pool.CreateEmptyTimeline('AAKHRI_V03_COLOR_CONSISTENCY_LONGER_EDL_EXCERPTS'); project.SetCurrentTimeline(tl); origin=tl.GetStartFrame(); cursor=0
        for wi,(ws,we) in enumerate(c['timeline_windows_ms'],1):
            for seg in edl['segments']:
                a=max(ws,seg['timeline_start_ms']); b=min(we,seg['timeline_end_ms'])
                if a>=b: continue
                aid=seg['take_asset_id']; source_a=seg['take_start_ms']+(a-seg['timeline_start_ms']); duration=b-a; framing=c['base_framing'][aid]
                clips=pool.AppendToTimeline([{'mediaPoolItem':by[Path(sources[aid]['path']).name],'startFrame':frame(source_a),'endFrame':frame(source_a+duration),'mediaType':1,'trackIndex':1,'recordFrame':origin+cursor}])
                if len(clips)!=1: raise RuntimeError('VIDEO_APPEND')
                clip=clips[0]
                if not clip.SetLUT(1,str(lutdst)): raise RuntimeError('LUT')
                comp=clip.AddFusionComp(); media,out=comp.FindTool('MediaIn1'),comp.FindTool('MediaOut1'); base=comp.AddTool('Transform'); base.SetAttrs({'TOOLS_Name':'UN_R3_SAFE_BASE_FRAMING_PRESERVED'}); base.Input=media.Output; base.Size=framing['base_scale']; point(base,'Center',framing['center']); out.Input=base.Output
                receipt['segments'].append({'window':wi,'segment_id':seg['segment_id'],'take_asset_id':aid,'original_timeline_ms':[a,b],'source_ms':[source_a,source_a+duration],'review_timeline_ms':[round(cursor*1000/FPS),round((cursor+frame(duration))*1000/FPS)],'base_framing':framing,'creative_motion':False}); cursor+=frame(duration)
            aclips=pool.AppendToTimeline([{'mediaPoolItem':audio,'startFrame':frame(ws),'endFrame':frame(we),'mediaType':2,'trackIndex':1,'recordFrame':origin+sum(frame(e-s) for s,e in c['timeline_windows_ms'][:wi-1])}])
            if len(aclips)!=1: raise RuntimeError('AUDIO_APPEND')
        expected=sum(frame(e-s) for s,e in c['timeline_windows_ms'])
        if cursor!=expected: raise RuntimeError('DURATION')
        if not project.SetCurrentRenderFormatAndCodec('mov','ProRes422HQ'): raise RuntimeError('PRORES')
        project.SetCurrentRenderMode(1); out=out_dir/'AAKHRI_V03_COLOR_CONSISTENCY_REVIEW_V01.mov'
        settings={'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+cursor-1,'TargetDir':str(out_dir),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS,'AudioCodec':'lpcm','AudioSampleRate':48000}
        if not project.SetRenderSettings(settings): raise RuntimeError('RENDER_SETTINGS')
        job=project.AddRenderJob()
        if not job or not project.StartRendering([job],False): raise RuntimeError('START')
        status=wait(project,job,out); receipt['outputs'].append({'role':'AUTHORITATIVE_HDR_V03_COLOR_CONSISTENCY_REVIEW','path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1],'frames':cursor,'duration_ms':round(cursor*1000/FPS),'status':status})
        if not pm.SaveProject() or not pm.ExportProject(project_name,str(out_dir/(project_name+'.drp')),False): raise RuntimeError('EXPORT')
        drp=out_dir/(project_name+'.drp'); receipt['resolve_project']={'path':str(drp),'sha256':sha256(drp)}
        receipt['sources_after']={a:{'sha256':sha(Path(r['path']))[0],'bytes':sha(Path(r['path']))[1]} for a,r in sources.items()}; receipt['master_after_sha256']=sha(master)[0]
        if any(receipt['sources_after'][a]['sha256']!=r['sha256'] for a,r in sources.items()) or receipt['master_after_sha256']!=MASTER_SHA: raise ValueError('SOURCE_CHANGED')
        receipt['status']='V03_COLOR_CONSISTENCY_RENDERED_PRIVATE_ONLY'; save()
    finally:
        if project: pm.SaveProject(); receipt['project_closed']=bool(pm.CloseProject(project)); save()
        if oldn: receipt['original_restored']=bool(pm.LoadProject(oldn)); save()
        if page: resolve.OpenPage(page)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('source_dir'); p.add_argument('contract'); p.add_argument('out_dir'); p.add_argument('project'); a=p.parse_args(); run(a.source_dir,a.contract,a.out_dir,a.project)
