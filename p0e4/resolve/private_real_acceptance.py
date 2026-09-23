"""Bound Aakhri Ishq private render harness; never deploys or publishes."""
import argparse,hashlib,json,re,time,shutil
from pathlib import Path

EXPECTED={
 'raw_video':('AKI_SOURCE_0902_V01.mov','50144b7d4754355cdfa69a2be626709116e5aead1faa566bbb4e1ab361ea8790',323607983),
 'authoritative_audio':('AAKHRI ISHQ MASTER 2.wav','670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2',61749398)}
VERSION=[21,1,0,17,''];PRODUCT='DaVinci Resolve Studio';BOUND_RAW_FPS='30'

def stream_hash(path):
 h=hashlib.sha256();size=0
 with Path(path).open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk);size+=len(chunk)
 return h.hexdigest(),size

def check_inputs(raw,audio,output_root,project):
 raw=Path(raw).resolve();audio=Path(audio).resolve();output_root=Path(output_root).resolve()
 if output_root.name!='private-real-media-v01' or output_root.parent.name!='.local':raise ValueError('PRIVATE_STAGING_ONLY')
 if not re.fullmatch(r'UNCHAINED_AKI_PRIVATE_V01_[A-Z0-9_]+',project):raise ValueError('PRIVATE_PROJECT_NAME_REQUIRED')
 observations={}
 for role,path in [('raw_video',raw),('authoritative_audio',audio)]:
  name,expected_sha,expected_size=EXPECTED[role]
  if path.name!=name or path.is_symlink():raise ValueError('EXACT_BOUND_INPUT_REQUIRED:'+role)
  digest,size=stream_hash(path)
  if (digest,size)!=(expected_sha,expected_size):raise ValueError('BOUND_INPUT_BYTES_DRIFT:'+role)
  observations[role]={'uri':str(path),'sha256':digest,'bytes':size,'mtime_ns':path.stat().st_mtime_ns}
 return raw,audio,output_root,observations

def run(raw,audio,output_root,project):
 raw,audio,root,before=check_inputs(raw,audio,output_root,project);root.mkdir(parents=True,exist_ok=True)
 cache=root/'bound-inputs';cache.mkdir(parents=True,exist_ok=True)
 staged={}
 for role,source in [('raw_video',raw),('authoritative_audio',audio)]:
  target=cache/source.name
  if not target.exists():shutil.copyfile(source,target)
  digest,size=stream_hash(target)
  if (digest,size)!=(before[role]['sha256'],before[role]['bytes']):raise ValueError('PRIVATE_STAGED_COPY_DRIFT:'+role)
  staged[role]={'uri':str(target),'sha256':digest,'bytes':size}
 report=root/(project+'.json');output=root/(project+'.mp4');drp=root/(project+'.drp')
 if any(x.exists() for x in (report,output,drp)):raise ValueError('NO_OVERWRITE_OR_DUPLICATE_REPLAY')
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve')
 if not resolve or resolve.GetProductName()!=PRODUCT or resolve.GetVersion()!=VERSION:raise ValueError('UNVERIFIED_INSTALLED_VERSION')
 pm=resolve.GetProjectManager()
 if pm.GetCurrentDatabase()['DbType']!='Disk':raise ValueError('LOCAL_DISK_DATABASE_REQUIRED')
 if project in pm.GetProjectListInCurrentFolder():raise ValueError('NO_OVERWRITE_OR_DUPLICATE_REPLAY')
 original=pm.GetCurrentProject();original_name=original.GetName() if original else None;original_page=resolve.GetCurrentPage()
 receipt={'schema':'PRIVATE_REAL_MEDIA_EXECUTION_RECEIPT_V01','schema_version':1,'run_id':project,'mode':'PRIVATE_LOCAL_REVIEW_ONLY','project_name':project,
  'input_hashes':{k:v['sha256'] for k,v in before.items()},'input_observations_before':before,'private_staged_copies':staged,
  'camera_audio_included':False,'authoritative_audio_included':True,'source_mutations':0,
  'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN','render_status':'STARTED'}
 def rec(key,value):receipt[key]=value;report.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(key,json.dumps(value,default=str),flush=True)
 p=None;job=None
 try:
  p=pm.CreateProject(project)
  if not p:raise RuntimeError('CREATE_PRIVATE_PROJECT_FAILED')
  if not p.SetSettings({'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':BOUND_RAW_FPS}):raise RuntimeError('PRIVATE_PROJECT_SETTINGS_FAILED')
  pool=p.GetMediaPool();videos=pool.ImportMedia([staged['raw_video']['uri']]);audios=pool.ImportMedia([staged['authoritative_audio']['uri']])
  if len(videos)!=1 or len(audios)!=1:raise RuntimeError('BOUND_MEDIA_IMPORT_FAILED')
  vp=videos[0].GetClipProperty();ap=audios[0].GetClipProperty();rec('import_properties',{'raw_video':vp,'authoritative_audio':ap})
  fps=str(vp.get('FPS') or vp.get('Video Frame Rate') or '')
  if fps not in (BOUND_RAW_FPS,BOUND_RAW_FPS+'.0'):raise ValueError('RAW_FRAME_RATE_REQUIRES_EXPLICIT_REVISION:'+fps)
  timeline=pool.CreateEmptyTimeline('AKI_PRIVATE_BOUND_MASTER2');
  if not timeline or not p.SetCurrentTimeline(timeline):raise RuntimeError('TIMELINE_CREATE_FAILED')
  start=timeline.GetStartFrame()
  vclips=pool.AppendToTimeline([{'mediaPoolItem':videos[0],'mediaType':1,'trackIndex':1,'recordFrame':start}])
  aclips=pool.AppendToTimeline([{'mediaPoolItem':audios[0],'mediaType':2,'trackIndex':1,'recordFrame':start}])
  if len(vclips)!=1 or len(aclips)!=1:raise RuntimeError('BOUND_TIMELINE_APPEND_FAILED')
  timeline_binding={'start_frame':start,'video':{'name':vclips[0].GetName(),'start':vclips[0].GetStart()-start,'end':vclips[0].GetEnd()-start,'duration':vclips[0].GetDuration()},
   'audio':{'name':aclips[0].GetName(),'start':aclips[0].GetStart()-start,'end':aclips[0].GetEnd()-start,'duration':aclips[0].GetDuration()},'video_track':1,'audio_track':1,'camera_audio_tracks_appended':0}
  if timeline_binding['video']['start']!=0 or timeline_binding['audio']['start']!=0:raise ValueError('BOUND_MEDIA_NOT_ZERO_ALIGNED')
  rec('timeline_binding',timeline_binding)
  if not p.SetCurrentRenderFormatAndCodec('mp4','H264'):raise RuntimeError('PRIVATE_H264_PROFILE_UNAVAILABLE')
  if not p.SetCurrentRenderMode(1):raise RuntimeError('SINGLE_CLIP_RENDER_MODE_FAILED')
  if not p.SetRenderSettings({'SelectAllFrames':True,'TargetDir':str(root),'CustomName':project,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':int(BOUND_RAW_FPS),'AudioCodec':'aac','AudioSampleRate':48000}):raise RuntimeError('PRIVATE_RENDER_SETTINGS_FAILED')
  job=p.AddRenderJob()
  if not job:raise RuntimeError('PRIVATE_RENDER_JOB_FAILED')
  rec('job_id',job)
  if not p.StartRendering([job],False):raise RuntimeError('PRIVATE_RENDER_START_FAILED')
  deadline=time.monotonic()+900
  while p.IsRenderingInProgress() and time.monotonic()<deadline:time.sleep(1)
  if p.IsRenderingInProgress():p.StopRendering();raise RuntimeError('PRIVATE_RENDER_TIMEOUT')
  status=p.GetRenderJobStatus(job);rec('render_job_status',status)
  if status['JobStatus']!='Complete' or not output.exists():raise RuntimeError('PRIVATE_RENDER_INCOMPLETE')
  out_sha,out_size=stream_hash(output)
  after={}
  for role,path in [('raw_video',raw),('authoritative_audio',audio)]:
   digest,size=stream_hash(path);after[role]={'uri':str(path),'sha256':digest,'bytes':size,'mtime_ns':path.stat().st_mtime_ns}
  if after!=before:raise ValueError('SOURCE_BYTES_OR_METADATA_CHANGED')
  receipt.update(output={'uri':str(output),'sha256':out_sha,'bytes':out_size,'classification':'PRIVATE_LOCAL_REVIEW_ONLY'},input_observations_after=after,render_status='COMPLETE')
  rec('status','PRIVATE_TECHNICAL_RENDER_COMPLETE')
  if not pm.SaveProject() or not pm.ExportProject(project,str(drp),False):raise RuntimeError('PRIVATE_PROJECT_EXPORT_FAILED')
 except Exception as e:rec('error',repr(e));receipt['render_status']='FAILED';report.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');raise
 finally:
  if p:
   if job and not p.IsRenderingInProgress():rec('render_job_removed',p.DeleteRenderJob(job))
   pm.SaveProject();rec('project_closed',pm.CloseProject(p))
  if original_name:rec('original_project_restored',bool(pm.LoadProject(original_name)))
  if original_page:resolve.OpenPage(original_page)
 return receipt

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('raw');a.add_argument('audio');a.add_argument('output_root');a.add_argument('project');x=a.parse_args();run(x.raw,x.audio,x.output_root,x.project)
