"""Create private synchronized review proxies for the authorized Aakhri workload."""
import argparse, hashlib, json, time
from pathlib import Path

FPS=30
MASTER_SHA='670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2'
TAKES={
 '1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8':('IMG_5739.MOV','8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971',0,211270,526,211796),
 '1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin':('IMG_5740.MOV','4082202982f9d063197305f45ef27bbef95274cf909e3fc918b7a9f5e37ec9fb',1627,49590,0,47963),
 '1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8':('IMG_5741.MOV','8043ab5faac4e5ce768c98268234c9d28eac992ee17b90e063acae02707f8313',2044,216434,0,214390),
 '1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW':('IMG_5742.MOV','3697fd0193386e25c0d2c62e18dc5a97b62492b7f87e7eeddfb1c9bd876c09b9',0,120752,92805,213557),
}

def sha(path):
 h=hashlib.sha256(); size=0
 with open(path,'rb') as f:
  while b:=f.read(1024*1024): h.update(b);size+=len(b)
 return h.hexdigest(),size

def frame(ms): return int(round(ms*FPS/1000))

def run(source_dir,out_dir):
 source_dir=Path(source_dir).resolve();out_dir=Path(out_dir).resolve();out_dir.mkdir(parents=True,exist_ok=True)
 master=source_dir/'AAKHRI ISHQ MASTER 2.wav'
 if sha(master)[0]!=MASTER_SHA: raise ValueError('MASTER_SOURCE_DRIFT')
 source=[]
 for asset,(name,expected,*_) in TAKES.items():
  path=source_dir/name
  if sha(path)[0]!=expected: raise ValueError('TAKE_SOURCE_DRIFT:'+asset)
  source.append(str(path))
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve'); pm=resolve.GetProjectManager()
 if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio': raise RuntimeError('RESOLVE_UNAVAILABLE')
 project_name='UNCHAINED_AAKHRI_MULTI_TAKE_SYNC_V01'
 if project_name in pm.GetProjectListInCurrentFolder(): raise ValueError('NO_DUPLICATE_PROJECT')
 original=pm.GetCurrentProject();original_name=original.GetName() if original else None;page=resolve.GetCurrentPage()
 receipt={'schema':'RESOLVE_SYNCHRONIZED_TAKE_PROXY_RUN_V01','scope':'PRIVATE_NON_PUBLISHING_AAKHRI_ONLY',
  'project':project_name,'master_audio_sha256':MASTER_SHA,'guide_audio_in_final_mix':False,'outputs':[],
  'governance':{'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'}}
 p=None
 try:
  p=pm.CreateProject(project_name)
  if not p.SetSettings({'timelineResolutionWidth':'540','timelineResolutionHeight':'960','timelineFrameRate':'30'}): raise RuntimeError('PROJECT_SETTINGS')
  pool=p.GetMediaPool();items=pool.ImportMedia(source+[str(master)])
  if len(items)!=5: raise RuntimeError('IMPORT_FAILED')
  by_name={x.GetName():x for x in items};audio=by_name[master.name]
  for asset,(name,expected,take_start,take_end,timeline_start,timeline_end) in TAKES.items():
   duration=timeline_end-timeline_start; frames=frame(duration); start=frame(take_start); audio_start=frame(timeline_start)
   t=pool.CreateEmptyTimeline('SYNC_'+asset[-8:]); p.SetCurrentTimeline(t); origin=t.GetStartFrame()
   v=pool.AppendToTimeline([{'mediaPoolItem':by_name[name],'startFrame':start,'endFrame':start+frames,'mediaType':1,'trackIndex':1,'recordFrame':origin}])
   a=pool.AppendToTimeline([{'mediaPoolItem':audio,'startFrame':audio_start,'endFrame':audio_start+frames,'mediaType':2,'trackIndex':1,'recordFrame':origin}])
   if len(v)!=1 or len(a)!=1: raise RuntimeError('APPEND_FAILED:'+asset)
   if not p.SetCurrentRenderFormatAndCodec('mp4','H264'): raise RuntimeError('H264_UNAVAILABLE')
   p.SetCurrentRenderMode(1)
   output='SYNC_'+asset[-8:]
   settings={'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+frames-1,'TargetDir':str(out_dir),'CustomName':output,
    'ExportVideo':True,'ExportAudio':True,'FormatWidth':540,'FormatHeight':960,'FrameRate':30,'AudioCodec':'aac','AudioSampleRate':48000}
   if not p.SetRenderSettings(settings): raise RuntimeError('RENDER_SETTINGS')
   job=p.AddRenderJob()
   if not job or not p.StartRendering([job],False): raise RuntimeError('RENDER_START')
   deadline=time.monotonic()+1200
   while p.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(1)
   status=p.GetRenderJobStatus(job);p.DeleteRenderJob(job)
   path=out_dir/(output+'.mp4')
   if status.get('JobStatus')!='Complete' or not path.exists(): raise RuntimeError('RENDER_FAILED:'+repr(status))
   got,size=sha(path)
   receipt['outputs'].append({'asset_id':asset,'take_sha256':expected,'timeline_start_ms':timeline_start,'timeline_end_ms':timeline_end,
    'take_start_ms':take_start,'take_end_ms':take_end,'path':str(path),'sha256':got,'bytes':size,'frames':frames,'render_status':status})
  if not pm.SaveProject() or not pm.ExportProject(project_name,str(out_dir/(project_name+'.drp')),False): raise RuntimeError('PROJECT_EXPORT')
  receipt['status']='GREEN_PRIVATE_SYNC_PROXIES';(out_dir/'RESOLVE_SYNCHRONIZED_TAKE_PROXY_RUN_V01.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 finally:
  if p: pm.CloseProject(p)
  if original_name: pm.LoadProject(original_name)
  if page: resolve.OpenPage(page)
 return receipt

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('source_dir');ap.add_argument('out_dir');x=ap.parse_args();run(x.source_dir,x.out_dir)
