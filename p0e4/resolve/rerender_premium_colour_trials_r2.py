"""Rerender only the corrected performance-only ranges from existing colour projects."""
import hashlib, json, time
from pathlib import Path
import DaVinciResolveScript as d

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'.local/premium-qc-research-v01'; SAMPLE=(204,563)
PROJECTS=['UNCHAINED_PREMIUM_QC_C0_CURRENT_REFERENCE_V01','UNCHAINED_PREMIUM_QC_C1_WARM_CINEMATIC_V01','UNCHAINED_PREMIUM_QC_C2_DRAMATIC_STAGE_V01']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
resolve=d.scriptapp('Resolve'); assert resolve and resolve.GetProductName()=='DaVinci Resolve Studio'
pm=resolve.GetProjectManager(); initial=pm.GetCurrentProject(); initial_name=initial.GetName() if initial else None; rows=[]
try:
 for name in PROJECTS:
  project=pm.LoadProject(name); assert project and not project.IsRenderingInProgress(); tl=project.GetCurrentTimeline(); origin=tl.GetStartFrame()
  stem=name.replace('UNCHAINED_PREMIUM_QC_','AAKHRI_PREMIUM_')+'_PERFORMANCE_ONLY_R2_HLG'; target=OUT/(stem+'.mov'); assert not target.exists()
  assert project.SetCurrentRenderFormatAndCodec('mov','ProRes422HQ'); project.SetCurrentRenderMode(1)
  assert project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin+SAMPLE[0],'MarkOut':origin+SAMPLE[1],'TargetDir':str(OUT),'CustomName':stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':30,'AudioCodec':'lpcm','AudioSampleRate':48000})
  job=project.AddRenderJob(); assert job and project.StartRendering([job],False); deadline=time.monotonic()+1200
  while project.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(.5)
  status=project.GetRenderJobStatus(job); project.DeleteRenderJob(job); assert status.get('JobStatus')=='Complete' and target.exists(),status
  rows.append({'variant':name,'sample_frames':list(SAMPLE),'render':{'path':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'status':status}})
  pm.CloseProject(project)
finally:
 if initial_name: pm.LoadProject(initial_name)
receipt={'schema':'PREMIUM_QC_COLOUR_TRIALS_R2','reason':'R1_RANGE_INCLUDED_EXISTING_OUTRO','r1_creative_selection_valid':False,'performance_only':True,'identical_frame_range':list(SAMPLE),'renders':rows,'full_master_rendered':False,'publication_authorized':False}
(OUT/'PREMIUM_QC_COLOUR_TRIALS_R2.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n'); print(json.dumps(receipt,indent=2))
