"""Render matched V05 versus V06 longer real-EDL HLG review excerpts."""
from __future__ import annotations
import argparse,json,shutil,time
from pathlib import Path
from multitake.r1_peak_highlights_eyelids import sha256
from multitake.v06_softness import write_cube
from multitake.source_color_management import validate_resolve_hlg_settings
from resolve.aakhri_multitake_realization import FPS,MASTER_SHA,TAKES,sha
SETTINGS={'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':str(FPS),'colorScienceMode':'davinciYRGBColorManaged','isAutoColorManage':'0','colorSpaceInput':'Rec.2100 HLG','colorSpaceTimeline':'Rec.2100 HLG','colorSpaceOutput':'Rec.2100 HLG','colorSpaceOutputToneMapping':'None','colorSpaceOutputGamutMapping':'None'}
WINDOWS=((8000,24000),(72000,96000),(108000,130000));VARIANTS=('CURRENT_V05_SOFT_SKIN_LIGHTING','NEW_V06_SOFTER_SKIN_LIGHTING')
def frame(ms):return round(ms*FPS/1000)
def point(t,n,v):setattr(t,n,{1:float(v[0]),2:float(v[1])})
def wait(p,j,o):
 d=time.monotonic()+2400
 while p.IsRenderingInProgress() and time.monotonic()<d:time.sleep(.5)
 if p.IsRenderingInProgress():p.StopRendering();raise RuntimeError('TIMEOUT')
 s=p.GetRenderJobStatus(j);p.DeleteRenderJob(j)
 if s.get('JobStatus')!='Complete' or not o.exists():raise RuntimeError('RENDER:'+repr(s))
 return s
def run(source_dir,edl_path,baseline_v05_lut,out_dir,project_name):
 source_dir,edl_path,baseline_v05_lut,out_dir=[Path(x).resolve() for x in (source_dir,edl_path,baseline_v05_lut,out_dir)]
 if out_dir.parent.name!='.local' or out_dir.name!='aakhri-v06-softness-caption-prep-v01':raise ValueError('PRIVATE_STAGING')
 out_dir.mkdir(parents=True,exist_ok=True);report=out_dir/'RESOLVE_V06_SOFTNESS_V01.json'
 if report.exists():raise ValueError('NO_DUPLICATE_REPLAY')
 edl=json.loads(edl_path.read_text());master=source_dir/'AAKHRI ISHQ MASTER 2.wav';mh,ms=sha(master)
 if mh!=MASTER_SHA or edl['edl_sha256']!='5d76c3d4ffcde938411b48319136214695226921b86fc3d2268272b64eadf9b5':raise ValueError('INPUT_DRIFT')
 if sha256(baseline_v05_lut)!='10a5cf0e249e56b9292f9f054c5bfb0e1a1cfd65f1702636ea16b00d1d569fc1':raise ValueError('V05_DRIFT')
 v06_path=out_dir/'luts'/'NEW_V06_SOFTER_SKIN_LIGHTING.cube'
 if v06_path==baseline_v05_lut:raise ValueError('BASELINE_OVERWRITE_FORBIDDEN')
 v06=write_cube(v06_path);luts={'CURRENT_V05_SOFT_SKIN_LIGHTING':str(baseline_v05_lut),'NEW_V06_SOFTER_SKIN_LIGHTING':v06['path']};sources={}
 for aid,(name,expected,_) in TAKES.items():
  p=source_dir/name;got,n=sha(p)
  if got!=expected:raise ValueError('SOURCE_DRIFT:'+aid)
  sources[aid]={'path':str(p),'sha256':got,'bytes':n}
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve');pm=resolve.GetProjectManager()
 if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio':raise RuntimeError('RESOLVE')
 if project_name in pm.GetProjectListInCurrentFolder():raise ValueError('NO_DUPLICATE_PROJECT')
 old=pm.GetCurrentProject();oldn=old.GetName() if old else None;page=resolve.GetCurrentPage();project=None
 rec={'schema':'RESOLVE_V06_SOFTNESS_V01','classification':'PRIVATE_V05_VS_V06_COLOR_REVIEW','sources_before':sources,'master':{'sha256':mh,'bytes':ms},'segments':[],'outputs':[],'full_master_rendered':False,'creative_motion':False}
 def save():report.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n')
 try:
  project=pm.CreateProject(project_name);results={k:bool(project.SetSetting(k,v)) for k,v in SETTINGS.items()}
  if not all(results.values()):raise RuntimeError('SETTINGS')
  actual={k:str(project.GetSetting(k)) for k in SETTINGS};validate_resolve_hlg_settings(actual);rec['project_settings_actual']=actual
  lutroot=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_V06_SOFTNESS');lutroot.mkdir(parents=True,exist_ok=True)
  for k,p in luts.items():dst=lutroot/(k+'.cube');shutil.copy2(p,dst);luts[k]=str(dst)
  project.RefreshLUTList();pool=project.GetMediaPool();imports=pool.ImportMedia([r['path'] for r in sources.values()]+[str(master)]);by={x.GetName():x for x in imports};audio=by[master.name]
  tl=pool.CreateEmptyTimeline('AAKHRI_V05_VS_V06_SOFTNESS');project.SetCurrentTimeline(tl);origin=tl.GetStartFrame();cursor=0
  framing={'1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8':(2.3,[.5,.72]),'1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin':(2.02,[.5,.5]),'1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8':(2.02,[.5,.49]),'1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW':(2.02,[.5,.5])}
  for wi,(ws,we) in enumerate(WINDOWS,1):
   for variant in VARIANTS:
    block_start=cursor
    for seg in edl['segments']:
     a=max(ws,seg['timeline_start_ms']);b=min(we,seg['timeline_end_ms'])
     if a>=b:continue
     aid=seg['take_asset_id'];sa=seg['take_start_ms']+(a-seg['timeline_start_ms']);dur=b-a
     clips=pool.AppendToTimeline([{'mediaPoolItem':by[Path(sources[aid]['path']).name],'startFrame':frame(sa),'endFrame':frame(sa+dur),'mediaType':1,'trackIndex':1,'recordFrame':origin+cursor}]);clip=clips[0]
     if not clip.SetLUT(1,luts[variant]):raise RuntimeError('LUT')
     comp=clip.AddFusionComp();mi,mo=comp.FindTool('MediaIn1'),comp.FindTool('MediaOut1');t=comp.AddTool('Transform');t.Input=mi.Output;t.Size=framing[aid][0];point(t,'Center',framing[aid][1]);mo.Input=t.Output
     rec['segments'].append({'window':wi,'variant':variant,'take_asset_id':aid,'original_timeline_ms':[a,b],'source_ms':[sa,sa+dur],'review_ms':[round(cursor*1000/FPS),round((cursor+frame(dur))*1000/FPS)]});cursor+=frame(dur)
    ac=pool.AppendToTimeline([{'mediaPoolItem':audio,'startFrame':frame(ws),'endFrame':frame(we),'mediaType':2,'trackIndex':1,'recordFrame':origin+block_start}])
    if len(ac)!=1:raise RuntimeError('AUDIO')
  if cursor!=3720:raise RuntimeError('DURATION:'+str(cursor))
  if not project.SetCurrentRenderFormatAndCodec('mov','ProRes422HQ'):raise RuntimeError('PRORES')
  project.SetCurrentRenderMode(1);out=out_dir/'AAKHRI_V05_VS_V06_SOFTNESS_HLG_REVIEW_V01.mov';project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+cursor-1,'TargetDir':str(out_dir),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS,'AudioCodec':'lpcm','AudioSampleRate':48000});j=project.AddRenderJob();project.StartRendering([j],False);s=wait(project,j,out);rec['outputs'].append({'role':'AUTHORITATIVE_HLG_REVIEW','path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1],'frames':cursor,'status':s})
  if not project.SetCurrentRenderFormatAndCodec('mp4','H265'):raise RuntimeError('H265')
  proxy=out_dir/'AAKHRI_V05_VS_V06_SOFTNESS_HLG_DECODE_PROXY_V01.mp4';project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+cursor-1,'TargetDir':str(out_dir),'CustomName':proxy.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS,'AudioCodec':'aac','AudioSampleRate':48000});j=project.AddRenderJob();project.StartRendering([j],False);s=wait(project,j,proxy);rec['outputs'].append({'role':'10BIT_HLG_DECODE_AND_GEMINI_PROXY','path':str(proxy),'sha256':sha(proxy)[0],'bytes':sha(proxy)[1],'frames':cursor,'status':s})
  pm.SaveProject();pm.ExportProject(project_name,str(out_dir/(project_name+'.drp')),False);rec['resolve_project_sha256']=sha256(out_dir/(project_name+'.drp'));rec['v06_lut']=v06;rec['baseline_v05_lut']={'path':str(baseline_v05_lut),'sha256':sha256(baseline_v05_lut),'read_only':True};rec['status']='RENDERED_PRIVATE_ONLY';save()
 finally:
  if project:pm.SaveProject();rec['project_closed']=bool(pm.CloseProject(project));save()
  if oldn:rec['original_restored']=bool(pm.LoadProject(oldn));save()
  if page:resolve.OpenPage(page)
 return rec
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source_dir');p.add_argument('edl');p.add_argument('baseline_v05_lut');p.add_argument('out_dir');p.add_argument('project');a=p.parse_args();run(a.source_dir,a.edl,a.baseline_v05_lut,a.out_dir,a.project)
