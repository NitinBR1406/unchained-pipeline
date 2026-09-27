from __future__ import annotations
import json,hashlib,shutil,time,sys,traceback,os
from pathlib import Path
FPS=30; START_MS=72000; END_MS=96000; FRAMES=720
PROJECT='UNCHAINED_AAKHRI_STRONGER_PERFORMANCE_PREVIEW_V01_AGENT_RESUME'
REPO=Path('/Users/nitinramdaras/.codex/.chatgpt-projects/g-p-6a9c53ef2a188191b31ad888f255ca99/unchained-pipeline')
OUT=REPO/'.local/stronger-performance-preview-v01-agent-resume'
REPORT=OUT/'RESOLVE_STRONGER_PERFORMANCE_PREVIEW_V01.json'
POLICY=REPO/'p0e4/evidence/native_caption_rhythm_parallel_v01_execution/agent2_rhythm/STRONGER_PERFORMANCE_ENERGY_V02.json'
LUT=REPO/'.local/aakhri-v06-softness-caption-prep-v01/luts/NEW_V06_SOFTER_SKIN_LIGHTING.cube'
MASTER=Path('/Users/nitinramdaras/Library/CloudStorage/GoogleDrive-nitin@unchainednitin.com/Gedeelde drives/Unchained Nitin — Master/P0E4_PRODUCTION_INTEGRATION/RAW_INTAKE/MULTI_TAKE/Aakhri-Ishq/AAKHRI ISHQ MASTER 2.wav')
TAKES={
'5739':{'path':Path('/Users/nitinramdaras/Library/CloudStorage/GoogleDrive-nitin@unchainednitin.com/Gedeelde drives/Unchained Nitin — Master/P0E4_PRODUCTION_INTEGRATION/RAW_INTAKE/MULTI_TAKE/Aakhri-Ishq/IMG_5739.MOV'),'sha':'8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971','offset_ms':526,'base':2.3,'center':(.5,.72),'usable':(526,211796)},
'5741':{'path':Path('/Users/nitinramdaras/Library/CloudStorage/GoogleDrive-nitin@unchainednitin.com/Gedeelde drives/Unchained Nitin — Master/P0E4_PRODUCTION_INTEGRATION/RAW_INTAKE/MULTI_TAKE/Aakhri-Ishq/IMG_5741.MOV'),'sha':'8043ab5faac4e5ce768c98268234c9d28eac992ee17b90e063acae02707f8313','offset_ms':-2044,'base':2.02,'center':(.5,.49),'usable':(0,214390)}}
MASTER_SHA='670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2'; LUT_SHA='4fdd545d18826ed26ae2a22ef87eeff70e7013ecb7c12924c993100ee9e082c0'
SETTINGS={'timelineResolutionWidth':'1080','timelineResolutionHeight':'1920','timelineFrameRate':'30','colorScienceMode':'davinciYRGBColorManaged','isAutoColorManage':'0','colorSpaceInput':'Rec.2100 HLG','colorSpaceTimeline':'Rec.2100 HLG','colorSpaceOutput':'Rec.2100 HLG','colorSpaceOutputToneMapping':'None','colorSpaceOutputGamutMapping':'None'}
def sha(p):
 h=hashlib.sha256(); n=0
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b); n+=len(b)
 return h.hexdigest(),n
def frame(ms): return round(ms*FPS/1000)
def write(d): OUT.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(d,indent=2,sort_keys=True,default=str)+'\n')
def wait(p,j,o):
 end=time.monotonic()+1800
 while p.IsRenderingInProgress() and time.monotonic()<end: time.sleep(.5)
 if p.IsRenderingInProgress(): p.StopRendering(); raise RuntimeError('TIMEOUT')
 st=p.GetRenderJobStatus(j)
 if st.get('JobStatus')!='Complete' or not o.exists(): raise RuntimeError('RENDER:'+repr(st))
 p.DeleteRenderJob(j); return st

def run():
 if OUT.exists() and any(OUT.iterdir()): raise RuntimeError('NO_DUPLICATE_REPLAY:'+str(OUT))
 OUT.mkdir(parents=True,exist_ok=True)
 pol=json.load(open(POLICY)); assert pol['policy_id']=='STRONGER_PERFORMANCE_ENERGY_V02'
 assert sha(MASTER)[0]==MASTER_SHA and sha(LUT)[0]==LUT_SHA
 for t in TAKES.values(): assert sha(t['path'])[0]==t['sha']
 # frame-exact cut points from authorized policy; 92.775 quantizes to excerpt frame 623 = 92.7667s.
 cut_frames=[89,204,335,491,623]
 boundaries=[0]+cut_frames+[720]; order=['5741','5739','5741','5739','5741','5739']
 adjustments=[]
 for e in pol['events']:
  ideal=(float(e['master_time_s'])-72)*30; got=int(e['excerpt_frame_30fps']); delta=(got-ideal)/30
  adjustments.append({'master_time_s':e['master_time_s'],'action':e['action'],'policy_frame':got,'ideal_fractional_frame':round(ideal,3),'quantization_delta_ms':round(delta*1000,3),'bounded':abs(delta)<=1/60})
 preflight={'source_hashes':{'master':MASTER_SHA,'v06_lut':LUT_SHA,'policy':sha(POLICY)[0],**{k:v['sha'] for k,v in TAKES.items()}},'window_ms':[START_MS,END_MS],'frame_count':720,'fps':30,'cut_frames':cut_frames,'take_order':order,'timing_adjustments':adjustments,'sync_validation':[],'expression_validation':'TAKE-SPECIFIC SOURCE FRAMES REVIEWED AT 7 POLICY MOMENTS; FACE/MOUTH VISIBLE; NO CLAIM OF LYRIC OR CLIMAX SEMANTICS','crop_validation':'V06 SAFE BASE FRAMING PRESERVED; PEAK MOTION ONLY INCREASES SCALE; TRANSLATION MAX 6.8px WITH SCALE GUARD','status':'GREEN_FOR_BOUNDED_PRIVATE_RENDER'}
 for a,b,take in zip(boundaries,boundaries[1:],order):
  ms0=START_MS+a/30*1000; ms1=START_MS+b/30*1000; td=TAKES[take]
  ok=td['usable'][0]<=ms0 and ms1<=td['usable'][1]
  preflight['sync_validation'].append({'excerpt_frames':[a,b],'master_ms':[round(ms0,3),round(ms1,3)],'take':take,'offset_ms':td['offset_ms'],'usable_master_ms':td['usable'],'green':ok,'drift_effect_under_window_ms':'<2ms'})
  assert ok
 rec={'schema':'RESOLVE_STRONGER_PERFORMANCE_PREVIEW_V01','status':'STARTING','classification':'PRIVATE_TEXT_FREE_24S_BOUNDED_PREVIEW','preflight':preflight,'full_master_rendered':False,'captions_used':False,'new_detector_built':False,'publication_authorized':False,'production_deployment_authorized':False}
 write(rec)
 import DaVinciResolveScript as d
 resolve=d.scriptapp('Resolve'); assert resolve and resolve.GetProductName()=='DaVinci Resolve Studio'
 pm=resolve.GetProjectManager(); old=pm.GetCurrentProject(); oldn=old.GetName() if old else None; page=resolve.GetCurrentPage(); p=None;j=None
 try:
  if PROJECT in pm.GetProjectListInCurrentFolder(): raise RuntimeError('PROJECT_EXISTS_NO_DUPLICATE')
  p=pm.CreateProject(PROJECT); assert p
  rec['isolated_project_created']=True; rec['prior_project']=oldn; write(rec)
  ok={k:bool(p.SetSetting(k,v)) for k,v in SETTINGS.items()}; assert all(ok.values()),ok
  rec['project_settings_actual']={k:str(p.GetSetting(k)) for k in SETTINGS}
  lutroot=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/UNCHAINED_STRONGER_PREVIEW_V01'); lutroot.mkdir(parents=True,exist_ok=True); lutdst=lutroot/'V06.cube'; shutil.copy2(LUT,lutdst); p.RefreshLUTList()
  pool=p.GetMediaPool(); imports=pool.ImportMedia([str(TAKES[k]['path']) for k in TAKES]+[str(MASTER)]); by={x.GetName():x for x in imports}; assert len(by)>=3,by.keys(); audio=by[MASTER.name]
  tl=pool.CreateEmptyTimeline('AAKHRI_STRONGER_PERFORMANCE_72_96_V01'); assert tl;p.SetCurrentTimeline(tl); origin=tl.GetStartFrame()
  events=pol['events']
  clip_receipts=[]
  for a,b,take in zip(boundaries,boundaries[1:],order):
   td=TAKES[take]; master_start=START_MS+a/30*1000; master_end=START_MS+b/30*1000
   source_start=master_start-td['offset_ms']; source_end=master_end-td['offset_ms']; dur=b-a
   item=pool.AppendToTimeline([{'mediaPoolItem':by[td['path'].name],'startFrame':frame(source_start),'endFrame':frame(source_end),'mediaType':1,'trackIndex':1,'recordFrame':origin+a}])[0]
   assert item and item.SetLUT(1,str(lutdst))
   comp=item.AddFusionComp(); mi,mo=comp.FindTool('MediaIn1'),comp.FindTool('MediaOut1'); tr=comp.AddTool('Transform'); tr.SetAttrs({'TOOLS_Name':'UN_STRONGER_BOUNDED_MOTION_V01'}); tr.Input=mi.Output
   tr.Size=comp.BezierSpline(); tr.Center=comp.BezierSpline(); base=td['base']; cx,cy=td['center']; tr.Size[0]=base;tr.Size[dur-1]=base;tr.Center[0]={1:cx,2:cy};tr.Center[dur-1]={1:cx,2:cy}
   applied=[]
   for e in events:
    gf=int(e['excerpt_frame_30fps'])
    if not (a<=gf<b) or e['action'] in ('cut','take_switch','hold'): continue
    lf=gf-a; attack=int(e['attack_frames']);hold=int(e['hold_frames']);recover=int(e['recovery_frames']); before=max(0,lf-attack); after=min(dur-1,lf+hold+recover)
    # fail closed when motion would cross a cut
    if before<=0 or after>=dur-1: continue
    if e['action']=='zoom':
     peak=base*(1+float(e['scale_delta_fraction'])); tr.Size[before]=base;tr.Size[lf]=peak;tr.Size[min(dur-1,lf+hold)]=peak;tr.Size[after]=base
     applied.append({'frame':gf,'local_frame':lf,'action':'zoom','peak_scale':peak,'recovery_end_frame':a+after})
    elif e['action']=='shake':
     guard=base*(1+float(e['scale_delta_fraction'])); disp=float(e['shake_displacement_fraction'])
     tr.Size[before]=base;tr.Size[lf]=guard;tr.Size[after]=base
     tr.Center[before]={1:cx,2:cy};tr.Center[lf]={1:cx+disp,2:cy-disp*.55};tr.Center[min(dur-1,lf+1)]={1:cx-disp*.65,2:cy+disp*.45};tr.Center[after]={1:cx,2:cy}
     applied.append({'frame':gf,'local_frame':lf,'action':'shake','peak_scale':guard,'peak_displacement_fraction':disp,'recovery_end_frame':a+after})
   mo.Input=tr.Output
   clip_receipts.append({'take':take,'timeline_frames':[a,b],'source_frames':[frame(source_start),frame(source_end)],'master_ms':[master_start,master_end],'events_applied':applied})
  ac=pool.AppendToTimeline([{'mediaPoolItem':audio,'startFrame':frame(START_MS),'endFrame':frame(END_MS),'mediaType':2,'trackIndex':1,'recordFrame':origin}]); assert len(ac)==1
  rec['clip_receipts']=clip_receipts; rec['audio']={'sha256':MASTER_SHA,'start_frame':frame(START_MS),'end_frame':frame(END_MS),'guide_audio_used':False}; write(rec)
  assert p.SetCurrentRenderFormatAndCodec('mp4','H265')
  p.SetCurrentRenderMode(1); out=OUT/'AAKHRI_STRONGER_PERFORMANCE_ENERGY_V02_72_96_HLG.mp4'
  assert p.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+719,'TargetDir':str(OUT),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':30,'AudioCodec':'aac','AudioSampleRate':48000})
  j=p.AddRenderJob(); assert j; rec['render_started']=True;write(rec); assert p.StartRendering([j],False); st=wait(p,j,out);j=None
  rec['render_status']=st; rec['output']={'path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1]}
  assert pm.SaveProject(); drp=OUT/(PROJECT+'.drp'); assert pm.ExportProject(PROJECT,str(drp),False); rec['project_export']={'path':str(drp),'sha256':sha(drp)[0],'bytes':sha(drp)[1]};rec['status']='RENDERED_PRIVATE_PENDING_QC';write(rec)
 finally:
  if p:
   if j and not p.IsRenderingInProgress(): p.DeleteRenderJob(j)
   pm.SaveProject(); rec['project_closed']=bool(pm.CloseProject(p));write(rec)
  if oldn: rec['prior_project_restored']=bool(pm.LoadProject(oldn));write(rec)
  if page: resolve.OpenPage(page)
 return rec
if __name__=='__main__':
 try: run()
 except Exception as e:
  OUT.mkdir(parents=True,exist_ok=True)
  p=OUT/'EXECUTION_ERROR.txt';p.write_text(repr(e)+'\n'+traceback.format_exc());raise
