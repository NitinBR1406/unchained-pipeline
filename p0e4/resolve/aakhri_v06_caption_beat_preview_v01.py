"""Render bounded 24s V06 A/B caption and shared beat-motion previews."""
from __future__ import annotations
import argparse,json,shutil,time
from pathlib import Path
from multitake.r1_peak_highlights_eyelids import sha256
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS,MASTER_SHA,TAKES,sha
SETTINGS={'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':str(FPS),'colorScienceMode':'davinciYRGBColorManaged','isAutoColorManage':'0','colorSpaceInput':'Rec.2100 HLG','colorSpaceTimeline':'Rec.2100 HLG','colorSpaceOutput':'Rec.2100 HLG','colorSpaceOutputToneMapping':'None','colorSpaceOutputGamutMapping':'None'}
START,END=72000,96000;V06_SHA='4fdd545d18826ed26ae2a22ef87eeff70e7013ecb7c12924c993100ee9e082c0';BEATS=(72760,78760,92760)
def frame(ms):return round(ms*FPS/1000)
def point(t,n,v):setattr(t,n,{1:float(v[0]),2:float(v[1])})
def wait(p,j,o):
 d=time.monotonic()+1800
 while p.IsRenderingInProgress() and time.monotonic()<d:time.sleep(.5)
 if p.IsRenderingInProgress():p.StopRendering();raise RuntimeError('TIMEOUT')
 s=p.GetRenderJobStatus(j);p.DeleteRenderJob(j)
 if s.get('JobStatus')!='Complete' or not o.exists():raise RuntimeError('RENDER:'+repr(s))
 return s
def run(source_dir,edl_path,v06_lut,out_dir,project_name):
 source_dir,edl_path,v06_lut,out_dir=[Path(x).resolve() for x in (source_dir,edl_path,v06_lut,out_dir)]
 if out_dir.parent.name!='.local' or out_dir.name!='aakhri-v06-caption-beat-preview-v01':raise ValueError('PRIVATE_STAGING')
 out_dir.mkdir(parents=True,exist_ok=True);report=out_dir/'RESOLVE_V06_CAPTION_BEAT_PREVIEW_V01.json'
 if report.exists():raise ValueError('NO_DUPLICATE_REPLAY')
 if sha256(v06_lut)!=V06_SHA:raise ValueError('V06_DRIFT')
 edl=json.loads(edl_path.read_text());master=source_dir/'AAKHRI ISHQ MASTER 2.wav';mh,ms=sha(master)
 if mh!=MASTER_SHA or edl['edl_sha256']!='5d76c3d4ffcde938411b48319136214695226921b86fc3d2268272b64eadf9b5':raise ValueError('INPUT_DRIFT')
 sources={}
 for aid,(name,expected,_) in TAKES.items():
  p=source_dir/name;got,n=sha(p)
  if got!=expected:raise ValueError('SOURCE_DRIFT:'+aid)
  sources[aid]={'path':str(p),'sha256':got,'bytes':n}
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve');pm=resolve.GetProjectManager()
 if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio':raise RuntimeError('RESOLVE')
 if project_name in pm.GetProjectListInCurrentFolder():raise ValueError('NO_DUPLICATE_PROJECT')
 old=pm.GetCurrentProject();oldn=old.GetName() if old else None;page=resolve.GetCurrentPage();project=None
 rec={'schema':'RESOLVE_V06_CAPTION_BEAT_PREVIEW_V01','classification':'PRIVATE_24S_CAPTION_BEAT_PREVIEW','sources_before':sources,'master':{'sha256':mh,'bytes':ms},'beat_events':[{'master_ms':x,'preview_ms':x-START,'source':'BEAT_SECTION_MOTION_INTELLIGENCE_V01'} for x in BEATS],'caption_variants':{'A':None,'B':{'text':'Some love stories never really end.','timing_ms':[250,3850],'provenance':'ORIGINAL_REVIEW_COPY_NOT_LYRIC_OR_TRANSLATION'},'C':{'status':'HOLD_PENDING_AUTHORITATIVE_LYRIC_TEXT_AND_WORD_TIMING'}},'outputs':[],'full_master_rendered':False,'caption_c_rendered':False,'shake_used':False}
 def save():report.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n')
 try:
  project=pm.CreateProject(project_name);ok={k:bool(project.SetSetting(k,v)) for k,v in SETTINGS.items()}
  if not all(ok.values()):raise RuntimeError('SETTINGS')
  actual={k:str(project.GetSetting(k)) for k in SETTINGS};validate_resolve_hlg_settings(actual);rec['project_settings_actual']=actual
  lutroot=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_V06_CAPTION_BEAT');lutroot.mkdir(parents=True,exist_ok=True);lutdst=lutroot/'V06.cube';shutil.copy2(v06_lut,lutdst);project.RefreshLUTList()
  pool=project.GetMediaPool();imports=pool.ImportMedia([r['path'] for r in sources.values()]+[str(master)]);by={x.GetName():x for x in imports};audio=by[master.name]
  framing={'1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8':(2.3,[.5,.72]),'1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin':(2.02,[.5,.5]),'1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8':(2.02,[.5,.49]),'1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW':(2.02,[.5,.5])}
  def build(name,variants):
   tl=pool.CreateEmptyTimeline(name);project.SetCurrentTimeline(tl);origin=tl.GetStartFrame();cursor=0
   for variant in variants:
    block=cursor
    for seg in edl['segments']:
     a=max(START,seg['timeline_start_ms']);b=min(END,seg['timeline_end_ms'])
     if a>=b:continue
     aid=seg['take_asset_id'];sa=seg['take_start_ms']+(a-seg['timeline_start_ms']);dur=b-a
     clip=pool.AppendToTimeline([{'mediaPoolItem':by[Path(sources[aid]['path']).name],'startFrame':frame(sa),'endFrame':frame(sa+dur),'mediaType':1,'trackIndex':1,'recordFrame':origin+cursor}])[0]
     if not clip.SetLUT(1,str(lutdst)):raise RuntimeError('LUT')
     comp=clip.AddFusionComp();mi,mo=comp.FindTool('MediaIn1'),comp.FindTool('MediaOut1');tr=comp.AddTool('Transform');tr.Input=mi.Output;base,center=framing[aid];tr.Size=comp.BezierSpline();point(tr,'Center',center);tr.Size[0]=base;tr.Size[frame(dur)-1]=base
     for beat in BEATS:
      if a<=beat<b:
       f=frame(beat-a);peak=base*(1.012 if beat in (72760,92760) else 1.022)
       tr.Size[max(0,f-8)]=base;tr.Size[f]=peak;tr.Size[min(frame(dur)-1,f+16)]=base
     final=tr.Output
     if variant=='B' and a==START:
      text=comp.AddTool('TextPlus');text.StyledText='Some love stories never really end.';text.Font='Helvetica';text.Size=.024;point(text,'Center',[.5,.145]);text.Red1=.94;text.Green1=.86;text.Blue1=.68
      merge=comp.AddTool('Merge');merge.Background=final;merge.Foreground=text.Output;merge.Blend=comp.BezierSpline();merge.Blend[0]=0;merge.Blend[8]=.92;merge.Blend[frame(3600)-8]=.92;merge.Blend[frame(3600)]=0;final=merge.Output
     mo.Input=final;cursor+=frame(dur)
    ac=pool.AppendToTimeline([{'mediaPoolItem':audio,'startFrame':frame(START),'endFrame':frame(END),'mediaType':2,'trackIndex':1,'recordFrame':origin+block}])
    if len(ac)!=1:raise RuntimeError('AUDIO')
   return tl,cursor
  specs=[('A_PERFORMANCE_ONLY',['A']),('B_ORIGINAL_OPENING_LINE',['B']),('AB_COMPARISON',['A','B'])]
  for role,variants in specs:
   tl,frames=build('AAKHRI_V06_'+role,variants)
   if not project.SetCurrentRenderFormatAndCodec('mp4','H265'):raise RuntimeError('H265')
   project.SetCurrentRenderMode(1);project.SetCurrentTimeline(tl);out=out_dir/('AAKHRI_V06_'+role+'_HLG_V01.mp4');start=tl.GetStartFrame();project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':start,'MarkOut':start+frames-1,'TargetDir':str(out_dir),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS,'AudioCodec':'aac','AudioSampleRate':48000});j=project.AddRenderJob();project.StartRendering([j],False);s=wait(project,j,out);rec['outputs'].append({'role':role,'path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1],'frames':frames,'status':s})
  pm.SaveProject();pm.ExportProject(project_name,str(out_dir/(project_name+'.drp')),False);rec['resolve_project_sha256']=sha256(out_dir/(project_name+'.drp'));rec['status']='RENDERED_PRIVATE_ONLY';save()
 finally:
  if project:pm.SaveProject();rec['project_closed']=bool(pm.CloseProject(project));save()
  if oldn:rec['original_restored']=bool(pm.LoadProject(oldn));save()
  if page:resolve.OpenPage(page)
 return rec
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source_dir');p.add_argument('edl');p.add_argument('v06_lut');p.add_argument('out_dir');p.add_argument('project');a=p.parse_args();run(a.source_dir,a.edl,a.v06_lut,a.out_dir,a.project)
