"""Execute the bounded private Aakhri Ishq multi-take EDL in Resolve Studio.

The script is workload and SHA bound.  It creates only new local review outputs,
never changes source media, and contains no distribution or publication route.
"""
import argparse, hashlib, json, re, time, wave
from pathlib import Path

FPS=30
MASTER_SHA='670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2'
EDL_SHA='5d76c3d4ffcde938411b48319136214695226921b86fc3d2268272b64eadf9b5'
TAKES={
 '1xX_RH8gfRGkZGeHU0OeI3u9JCOAR23N8':('IMG_5739.MOV','8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971',0.989),
 '1Bw6cH1pqe1vAzKmsHMTzihcAxzLXOFin':('IMG_5740.MOV','4082202982f9d063197305f45ef27bbef95274cf909e3fc918b7a9f5e37ec9fb',0.976),
 '1jaUADjUEpyPN1qzdLs_Q-dKp62NzMsF8':('IMG_5741.MOV','8043ab5faac4e5ce768c98268234c9d28eac992ee17b90e063acae02707f8313',1.011),
 '1DUEqRsDHRDUE7aOV9q0akUyBEtPHjhsW':('IMG_5742.MOV','3697fd0193386e25c0d2c62e18dc5a97b62492b7f87e7eeddfb1c9bd876c09b9',1.090),
}

def sha(path):
 h=hashlib.sha256();size=0
 with Path(path).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b);size+=len(b)
 return h.hexdigest(),size

def frame(ms): return int(round(ms*FPS/1000))

def fade_audio(source,dest,startf,endf):
 count=(endf-startf)*1600
 with wave.open(str(source),'rb') as src:
  if (src.getframerate(),src.getnchannels(),src.getsampwidth())!=(48000,2,3):raise ValueError('MASTER_WAV_FORMAT')
  src.setpos(startf*1600);data=bytearray(src.readframes(count));params=src.getparams()
 for i in range(count):
  gain=min(1.0,i/4800,(count-1-i)/9600)
  if gain>=.999999:continue
  for ch in range(2):
   off=(i*2+ch)*3;n=int.from_bytes(data[off:off+3],'little',signed=True)
   data[off:off+3]=int(round(n*gain)).to_bytes(3,'little',signed=True)
 with wave.open(str(dest),'wb') as out:out.setparams(params);out.writeframes(data)
 return {'sha256':sha(dest)[0],'start_frame':startf,'end_frame_exclusive':endf}

def finish_clip(clip,frames,gain,push=False):
 comp=clip.AddFusionComp()
 if not comp:raise RuntimeError('FUSION_COMP')
 media=comp.FindTool('MediaIn1');out=comp.FindTool('MediaOut1')
 norm=comp.AddTool('BrightnessContrast');norm.SetAttrs({'TOOLS_Name':'UN_COLOR_NORMALIZATION'})
 norm.Input=media.Output;norm.Gain=gain
 match=comp.AddTool('BrightnessContrast');match.SetAttrs({'TOOLS_Name':'UN_SHOT_MATCH'})
 match.Input=norm.Output;match.Contrast=0.0
 look=comp.AddTool('BrightnessContrast');look.SetAttrs({'TOOLS_Name':'UN_UNCHAINED_LOOK_EVIDENCE_CLOSED'})
 # Keep the creative-look stage explicit and neutral: no numeric look was authorized.
 look.Input=match.Output;look.Contrast=0.0;look.Saturation=1.0
 transform=comp.AddTool('Transform');transform.SetAttrs({'TOOLS_Name':'UN_EVIDENCE_PUSH_IN'})
 transform.Input=look.Output
 if push and frames>30:
  transform.Size=comp.BezierSpline();transform.Size[0]=1.0;transform.Size[frames-1]=1.025
 else:transform.Size=1.0
 out.Input=transform.Output
 return {'normalization_gain':gain,'shot_match_contrast':0.0,'creative_look_status':'NONE_EVIDENCE_CLOSED',
         'creative_look_contrast':0.0,'creative_look_saturation':1.0,'push_in_end_scale':1.025 if push else 1.0}

def render(project,timeline,root,name,frames):
 if not project.SetCurrentTimeline(timeline):raise RuntimeError('TIMELINE_SELECT')
 if not project.SetCurrentRenderFormatAndCodec('mp4','H264'):raise RuntimeError('H264_UNAVAILABLE')
 project.SetCurrentRenderMode(1);origin=timeline.GetStartFrame()
 if not project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+frames-1,
  'TargetDir':str(root),'CustomName':name,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,
  'FormatHeight':1920,'FrameRate':30,'AudioCodec':'aac','AudioSampleRate':48000}):raise RuntimeError('RENDER_SETTINGS')
 job=project.AddRenderJob()
 if not job or not project.StartRendering([job],False):raise RuntimeError('RENDER_START')
 deadline=time.monotonic()+1800
 while project.IsRenderingInProgress() and time.monotonic()<deadline:time.sleep(1)
 if project.IsRenderingInProgress():project.StopRendering();raise RuntimeError('RENDER_TIMEOUT')
 status=project.GetRenderJobStatus(job);project.DeleteRenderJob(job);path=root/(name+'.mp4')
 if status.get('JobStatus')!='Complete' or not path.exists():raise RuntimeError('RENDER_FAILED:'+repr(status))
 got,size=sha(path);return {'name':name,'path':str(path),'sha256':got,'bytes':size,'frames':frames,'render_status':status}

def build_timeline(project,pool,name,items,audio,segments,audio_startf,audio_endf,root,derivative=False):
 t=pool.CreateEmptyTimeline(name);project.SetCurrentTimeline(t);origin=t.GetStartFrame();finishes=[]
 cursor=0
 for idx,s in enumerate(segments):
  frames=frame(s['timeline_end_ms'])-frame(s['timeline_start_ms'])
  start=frame(s['take_start_ms'])
  clips=pool.AppendToTimeline([{'mediaPoolItem':items[s['take_asset_id']],'startFrame':start,
   'endFrame':start+frames,'mediaType':1,'trackIndex':1,'recordFrame':origin+cursor}])
  if len(clips)!=1:raise RuntimeError('VIDEO_APPEND:'+s['segment_id'])
  finishes.append({'segment_id':s['segment_id'],**finish_clip(clips[0],frames,TAKES[s['take_asset_id']][2],idx == 0)})
  cursor+=frames
 audio_item=audio;astart=audio_startf;aend=audio_endf;alineage=None
 if derivative:
  wav=root/(name+'.wav');alineage=fade_audio(audio.GetClipProperty('File Path'),wav,audio_startf,audio_endf)
  imported=pool.ImportMedia([str(wav)]);audio_item=imported[0];astart=0;aend=cursor
 aclips=pool.AppendToTimeline([{'mediaPoolItem':audio_item,'startFrame':astart,'endFrame':aend,
  'mediaType':2,'trackIndex':1,'recordFrame':origin}])
 if len(aclips)!=1:raise RuntimeError('AUDIO_APPEND')
 return t,cursor,finishes,alineage

def clip_edl(edl,start_ms,end_ms):
 rows=[]
 for s in edl['segments']:
  a=max(start_ms,s['timeline_start_ms']);b=min(end_ms,s['timeline_end_ms'])
  if b<=a:continue
  x=dict(s);x['take_start_ms']=s['take_start_ms']+(a-s['timeline_start_ms']);x['take_end_ms']=x['take_start_ms']+(b-a)
  x['timeline_start_ms']=a-start_ms;x['timeline_end_ms']=b-start_ms;rows.append(x)
 return rows

def run(source_dir,edl_path,out_dir,project_name):
 source_dir=Path(source_dir).resolve();edl_path=Path(edl_path).resolve();root=Path(out_dir).resolve()
 if root.name!='aakhri-multitake-realization-v01' or root.parent.name!='.local':raise ValueError('PRIVATE_STAGING_ONLY')
 if not re.fullmatch(r'UNCHAINED_AAKHRI_MULTITAKE_V01_[A-Z0-9_]+',project_name):raise ValueError('PROJECT_NAME')
 root.mkdir(parents=True,exist_ok=True);report=root/(project_name+'.json')
 if report.exists():raise ValueError('NO_DUPLICATE_REPLAY')
 edl=json.loads(edl_path.read_text())
 if edl.get('edl_sha256')!=EDL_SHA:raise ValueError('EDL_DRIFT')
 before={'edl':{'path':str(edl_path),'sha256':sha(edl_path)[0]},'takes':{},'master':{}}
 for asset,(name,expected,_) in TAKES.items():
  path=source_dir/name;got,size=sha(path)
  if got!=expected:raise ValueError('TAKE_DRIFT:'+asset)
  before['takes'][asset]={'path':str(path),'sha256':got,'bytes':size}
 master=source_dir/'AAKHRI ISHQ MASTER 2.wav';got,size=sha(master)
 if got!=MASTER_SHA:raise ValueError('MASTER_DRIFT')
 before['master']={'path':str(master),'sha256':got,'bytes':size}
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve');pm=resolve.GetProjectManager()
 if not resolve or resolve.GetProductName()!='DaVinci Resolve Studio':raise RuntimeError('RESOLVE_UNAVAILABLE')
 if project_name in pm.GetProjectListInCurrentFolder():raise ValueError('NO_DUPLICATE_PROJECT')
 original=pm.GetCurrentProject();original_name=original.GetName() if original else None;page=resolve.GetCurrentPage();p=None
 receipt={'schema':'RESOLVE_MULTI_TAKE_REALIZATION_V01','scope':'PRIVATE_AAKHRI_ISHQ_ACCEPTANCE_ONLY',
  'project':project_name,'edl_sha256':EDL_SHA,'programme_audio_sha256':MASTER_SHA,'inputs_before':before,
  'color_pipeline':{'normalization':'PER_TAKE_MEASURED_THUMBNAIL_LUMA_GAIN','shot_match':'SEPARATE_FUSION_STAGE',
  'creative_look':'SEPARATE_BOUNDED_UNCHAINED_STAGE'},'outputs':[],'stills_pending_from_rendered_master':True,
  'governance':{'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'}}
 def save():report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 try:
  p=pm.CreateProject(project_name)
  if not p or not p.SetSettings({'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':'30'}):raise RuntimeError('PROJECT_SETUP')
  pool=p.GetMediaPool();paths=[v['path'] for v in before['takes'].values()]+[before['master']['path']]
  imported=pool.ImportMedia(paths)
  if len(imported)!=5:raise RuntimeError('IMPORT')
  by_name={x.GetName():x for x in imported};items={a:by_name[n] for a,(n,_,_) in TAKES.items()};audio=by_name[master.name]
  suffix=project_name.rsplit('_',1)[-1]
  master_name='AAKHRI_MULTITAKE_MASTER_V01_'+suffix
  t,frames,fin,alineage=build_timeline(p,pool,master_name,items,audio,edl['segments'],0,frame(214400),root)
  out=render(p,t,root,master_name,frames);out.update(fusion_finishing=fin,audio_route='AUTHORITATIVE_MASTER_ONLY');receipt['outputs'].append(out);save()
  for deriv in edl['derivatives']:
   segs=clip_edl(edl,deriv['start_ms'],deriv['end_ms']);sf=frame(deriv['start_ms']);ef=frame(deriv['end_ms'])
   name='AAKHRI_'+deriv['derivative_id']+'_V01_'+suffix;t,frames,fin,alineage=build_timeline(p,pool,name,items,audio,segs,sf,ef,root,True)
   out=render(p,t,root,name,frames);out.update(fusion_finishing=fin,audio_route='AUTHORITATIVE_MASTER_ONLY',audio_lineage=alineage,
    derivative_range_ms=[deriv['start_ms'],deriv['end_ms']]);receipt['outputs'].append(out);save()
  if not pm.SaveProject() or not pm.ExportProject(project_name,str(root/(project_name+'.drp')),False):raise RuntimeError('PROJECT_EXPORT')
  after={'takes':{a:{'sha256':sha(v['path'])[0],'bytes':sha(v['path'])[1]} for a,v in before['takes'].items()},
   'master':{'sha256':sha(master)[0],'bytes':sha(master)[1]}}
  if any(after['takes'][a]['sha256']!=before['takes'][a]['sha256'] for a in TAKES) or after['master']['sha256']!=MASTER_SHA:raise ValueError('SOURCE_CHANGED')
  receipt['inputs_after']=after;receipt['status']='RENDER_COMPLETE_PRIVATE_ONLY';save()
 finally:
  if p:pm.SaveProject();receipt['project_closed']=pm.CloseProject(p);save()
  if original_name:receipt['original_restored']=bool(pm.LoadProject(original_name));save()
  if page:resolve.OpenPage(page)
 return receipt

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('source_dir');ap.add_argument('edl');ap.add_argument('out_dir');ap.add_argument('project');x=ap.parse_args()
 run(x.source_dir,x.edl,x.out_dir,x.project)
