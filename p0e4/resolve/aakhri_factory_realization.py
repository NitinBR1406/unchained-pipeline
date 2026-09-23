"""Bounded Aakhri Ishq local/private production realization in Resolve/Fusion.

This harness is workload-specific. It never deploys, uploads, schedules, publishes,
or mutates the bound inputs. Every output is a new private review artifact.
"""
import argparse, hashlib, json, re, time, wave
from pathlib import Path

VERSION=[21,1,0,17,'']; PRODUCT='DaVinci Resolve Studio'; FPS=30
EXPECTED={
 'raw':('AKI_SOURCE_0902_V01.mov','50144b7d4754355cdfa69a2be626709116e5aead1faa566bbb4e1ab361ea8790',323607983),
 'audio':('AAKHRI ISHQ MASTER 2.wav','670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2',61749398),
 'run4':('UNCHAINED_AKI_PRIVATE_V01_RUN4.mp4','7f5b96e8a42377263ba9b0953d7c8edf92f4d9cb5447fc80e2527e33a02da501',382264829)}
SEGMENTS=[('D1_CHORUS_ENERGY',1230,1695),('D2_DIRECT_EYE_CONTACT',3540,3990),('D3_CLIMAX',4500,4950),('D4_INTIMATE_CONCLUSION',5850,6315)]

def digest(path):
 h=hashlib.sha256(); size=0
 with Path(path).open('rb') as f:
  while chunk:=f.read(1024*1024): h.update(chunk); size+=len(chunk)
 return h.hexdigest(),size

def verify(role,path):
 path=Path(path).resolve(); name,sha,size=EXPECTED[role]
 if path.name!=name or path.is_symlink(): raise ValueError('EXACT_BOUND_INPUT_REQUIRED:'+role)
 got=digest(path)
 if got!=(sha,size): raise ValueError('BOUND_INPUT_DRIFT:'+role)
 return {'path':str(path),'sha256':got[0],'bytes':got[1],'mtime_ns':path.stat().st_mtime_ns}

def fusion(comp, frames, derivative=False):
 media=comp.FindTool('MediaIn1'); out=comp.FindTool('MediaOut1')
 transform=comp.AddTool('Transform'); transform.SetAttrs({'TOOLS_Name':'UN_SUBTLE_PUSH'})
 transform.Input=media.Output
 transform.Size=comp.BezierSpline(); transform.Size[0]=1.0
 if derivative:
  transform.Size[frames-1]=1.025
 else:
  # Sparse, centered, bounded motion; protected windows remain exactly 1.0.
  for f,v in [(449,1.0),(1230,1.0),(2009,1.03),(2129,1.0),(4319,1.0),(5099,1.035),(5219,1.0),(5459,1.0),(5999,1.03),(6149,1.0),(frames-1,1.0)]:
   if f<frames: transform.Size[f]=v
 text=comp.AddTool('TextPlus'); text.SetAttrs({'TOOLS_Name':'UN_TITLE_ARTIST'})
 text.StyledText='AAKHRI ISHQ\nUNCHAINED NITIN'; text.Font='Helvetica'; text.Size=0.028
 text.Center={1:0.34,2:0.20}; text.Red1=0.831; text.Green1=0.686; text.Blue1=0.216
 merge=comp.AddTool('Merge'); merge.SetAttrs({'TOOLS_Name':'UN_MINIMAL_TITLE'})
 merge.Background=transform.Output; merge.Foreground=text.Output; merge.Blend=comp.BezierSpline()
 if derivative:
  for f,v in [(0,0.0),(8,0.9),(78,0.9),(89,0.0),(frames-1,0.0)]: merge.Blend[f]=v
 else:
  for f,v in [(0,0.0),(479,0.0),(491,0.9),(618,0.9),(630,0.0),(frames-1,0.0)]: merge.Blend[f]=v
 if derivative:
  bg=comp.AddTool('Background'); bg.SetAttrs({'TOOLS_Name':'UN_FADE_BACKGROUND'}); bg.TopLeftRed=0; bg.TopLeftGreen=0; bg.TopLeftBlue=0
  final=comp.AddTool('Merge'); final.SetAttrs({'TOOLS_Name':'UN_BOUNDED_VISUAL_FADE'}); final.Background=bg.Output; final.Foreground=merge.Output
  final.Blend=comp.BezierSpline(); final.Blend[0]=0.0; final.Blend[5]=1.0; final.Blend[max(6,frames-10)]=1.0; final.Blend[frames-1]=0.0
  out.Input=final.Output
 else: out.Input=merge.Output
 return {'title':'AAKHRI ISHQ / UNCHAINED NITIN','font':'Helvetica','max_zoom':1.035 if not derivative else 1.025,'frames':frames}

def faded_audio(source,dest,start_frame,end_frame):
 samples_per_frame=1600; start=start_frame*samples_per_frame; count=(end_frame-start_frame)*samples_per_frame
 with wave.open(str(source),'rb') as src:
  if (src.getframerate(),src.getnchannels(),src.getsampwidth())!=(48000,2,3): raise ValueError('UNEXPECTED_MASTER_WAV_FORMAT')
  src.setpos(start); data=bytearray(src.readframes(count)); params=src.getparams()
 fade_in=9600; fade_out=14400; total=count
 for i in range(total):
  gain=min(1.0,i/max(1,fade_in),(total-1-i)/max(1,fade_out))
  if gain>=0.999999: continue
  for ch in range(2):
   off=(i*2+ch)*3; n=int.from_bytes(data[off:off+3],'little',signed=True); n=int(round(n*gain)); data[off:off+3]=n.to_bytes(3,'little',signed=True)
 with wave.open(str(dest),'wb') as out:
  out.setparams(params); out.writeframes(data)
 return {'path':str(dest),'sha256':digest(dest)[0],'frames':end_frame-start_frame,'fade_in_samples':fade_in,'fade_out_samples':fade_out}

def render(project,timeline,root,name,frames):
 if not project.SetCurrentTimeline(timeline): raise RuntimeError('SET_TIMELINE_FAILED')
 if not project.SetCurrentRenderFormatAndCodec('mp4','H264'): raise RuntimeError('H264_UNAVAILABLE')
 if not project.SetCurrentRenderMode(1): raise RuntimeError('SINGLE_CLIP_MODE_FAILED')
 start=timeline.GetStartFrame()
 settings={'SelectAllFrames':False,'MarkIn':start,'MarkOut':start+frames-1,'TargetDir':str(root),'CustomName':name,
  'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':FPS,
  'AudioCodec':'aac','AudioSampleRate':48000}
 if not project.SetRenderSettings(settings): raise RuntimeError('RENDER_SETTINGS_FAILED')
 job=project.AddRenderJob()
 if not job or not project.StartRendering([job],False): raise RuntimeError('RENDER_START_FAILED')
 deadline=time.monotonic()+1200
 while project.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(1)
 if project.IsRenderingInProgress(): project.StopRendering(); raise RuntimeError('RENDER_TIMEOUT')
 status=project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
 output=root/(name+'.mp4')
 if status.get('JobStatus')!='Complete' or not output.exists(): raise RuntimeError('RENDER_INCOMPLETE:'+repr(status))
 sha,size=digest(output)
 return {'name':name,'path':str(output),'sha256':sha,'bytes':size,'frames':frames,'status':status}

def run(raw,audio,run4,root,project_name):
 root=Path(root).resolve()
 if root.name!='aakhri-factory-realization-v01' or root.parent.name!='.local': raise ValueError('PRIVATE_STAGING_ONLY')
 if not re.fullmatch(r'UNCHAINED_AAKHRI_FACTORY_V01_[A-Z0-9_]+',project_name): raise ValueError('PRIVATE_PROJECT_NAME_REQUIRED')
 root.mkdir(parents=True,exist_ok=True); report=root/(project_name+'.json')
 if report.exists(): raise ValueError('NO_DUPLICATE_REPLAY')
 before={r:verify(r,p) for r,p in [('raw',raw),('audio',audio),('run4',run4)]}
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve')
 if not resolve or resolve.GetProductName()!=PRODUCT or resolve.GetVersion()!=VERSION: raise ValueError('UNVERIFIED_RESOLVE')
 pm=resolve.GetProjectManager()
 if pm.GetCurrentDatabase()['DbType']!='Disk' or project_name in pm.GetProjectListInCurrentFolder(): raise ValueError('LOCAL_NEW_PROJECT_REQUIRED')
 original=pm.GetCurrentProject(); original_name=original.GetName() if original else None; original_page=resolve.GetCurrentPage()
 receipt={'schema':'AAKHRI_FACTORY_REALIZATION_EXECUTION_V01','scope':'PRIVATE_LOCAL_NON_PUBLISHING_AAKHRI_ONLY','project':project_name,
  'inputs_before':before,'authorization':{'bounded_aakhri_realization':True,'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'},'outputs':[]}
 def rec(): report.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 p=None
 try:
  p=pm.CreateProject(project_name)
  if not p or not p.SetSettings({'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':'30'}): raise RuntimeError('PROJECT_SETUP_FAILED')
  pool=p.GetMediaPool(); v=pool.ImportMedia([before['raw']['path']]); a=pool.ImportMedia([before['audio']['path']])
  if len(v)!=1 or len(a)!=1: raise RuntimeError('IMPORT_FAILED')
  specs=[('AAKHRI_MASTER_REALIZED_V01_R2',0,6432,False)]+[(f'AAKHRI_{name}_V01_R2',s,e,True) for name,s,e in SEGMENTS]
  for name,startf,endf,is_deriv in specs:
   frames=endf-startf; t=pool.CreateEmptyTimeline(name)
   if not t or not p.SetCurrentTimeline(t): raise RuntimeError('TIMELINE_FAILED:'+name)
   origin=t.GetStartFrame()
   vc=pool.AppendToTimeline([{'mediaPoolItem':v[0],'startFrame':startf,'endFrame':endf,'mediaType':1,'trackIndex':1,'recordFrame':origin}])
   audio_item=a[0]; audio_start=startf; audio_end=endf
   if is_deriv:
    wav=root/(name+'.wav'); fade=faded_audio(before['audio']['path'],wav,startf,endf); imported=pool.ImportMedia([str(wav)])
    if len(imported)!=1: raise RuntimeError('FADED_AUDIO_IMPORT_FAILED:'+name)
    audio_item=imported[0]; audio_start=0; audio_end=endf-startf; receipt.setdefault('derivative_audio_lineage',[]).append(fade)
   ac=pool.AppendToTimeline([{'mediaPoolItem':audio_item,'startFrame':audio_start,'endFrame':audio_end,'mediaType':2,'trackIndex':1,'recordFrame':origin}])
   if len(vc)!=1 or len(ac)!=1 or vc[0].GetDuration()!=frames or ac[0].GetDuration()!=frames: raise RuntimeError('APPEND_FAILED:'+name)
   comp=vc[0].AddFusionComp()
   if not comp: raise RuntimeError('FUSION_FAILED:'+name)
   fg=fusion(comp,frames,is_deriv)
   rendered=render(p,t,root,name,frames); rendered.update(source_frames=[startf,endf],fusion=fg)
   receipt['outputs'].append(rendered); rec()
  receipt['inputs_after']={r:verify(r,pth) for r,pth in [('raw',raw),('audio',audio),('run4',run4)]}
  if receipt['inputs_after']!=before: raise ValueError('SOURCE_CHANGED')
  if not pm.SaveProject() or not pm.ExportProject(project_name,str(root/(project_name+'.drp')),False): raise RuntimeError('PROJECT_EXPORT_FAILED')
  receipt['status']='RENDER_COMPLETE_PRIVATE_ONLY'; rec()
 finally:
  if p: pm.SaveProject(); receipt['project_closed']=pm.CloseProject(p); rec()
  if original_name: receipt['original_restored']=bool(pm.LoadProject(original_name)); rec()
  if original_page: resolve.OpenPage(original_page)
 return receipt

if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('raw');ap.add_argument('audio');ap.add_argument('run4');ap.add_argument('root');ap.add_argument('project')
 x=ap.parse_args(); run(x.raw,x.audio,x.run4,x.root,x.project)
