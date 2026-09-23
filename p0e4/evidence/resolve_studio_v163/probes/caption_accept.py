import DaVinciResolveScript as d,json,pathlib,time
root=pathlib.Path(__file__).resolve().parent;r=d.scriptapp('Resolve');pm=r.GetProjectManager();p=pm.GetCurrentProject();assert p.GetName()=='UNCHAINED_V163_SYNTHETIC_20260923';m=p.GetMediaPool();main=p.GetTimelineByIndex(1);p.SetCurrentTimeline(main);out={}
def rec(k,v):
 out[k]=v;(root/'captions_acceptance.json').write_text(json.dumps(out,indent=2,default=str));print(k,v,flush=True)
if main.GetTrackCount('subtitle')==0:assert main.AddTrack('subtitle')
assert main.SetCurrentTimecode('01:00:00:00');sub=m.ImportMedia([str(root/'captions.srt')])[0];m.AppendToTimeline([sub])
items=main.GetItemListInTrack('subtitle',1);bounds=[dict(text=x.GetName(),start=x.GetStart()-90000,end=x.GetEnd()-90000) for x in items];rec('captions',bounds);assert bounds==[dict(text='UNCHAINED SYNTHETIC',start=0,end=50),dict(text='CAPTION ACCEPTANCE',start=50,end=100)]
assert p.SetRenderSettings(dict(SelectAllFrames=False,MarkIn=90000,MarkOut=90099,TargetDir=str(root),CustomName='UNCHAINED_V163_CAPTIONS',ExportSubtitle=True,SubtitleFormat='BurnIn'))
j=p.AddRenderJob();assert j and p.StartRendering([j],False)
for _ in range(120):
 if not p.IsRenderingInProgress():break
 time.sleep(.5)
rec('render',p.GetRenderJobStatus(j));rec('job_removed',p.DeleteRenderJob(j));pm.SaveProject()
probe=p.GetTimelineByIndex(2);rec('native_titles',[[dict(name=x.GetName(),fusion_comps=x.GetFusionCompCount()) for x in probe.GetItemListInTrack('video',i)] for i in range(1,probe.GetTrackCount('video')+1)])
# Restore the user project that was active before this task; retain test projects as private diagnostics.
rec('closed',pm.CloseProject(p));rec('original_project_restored',bool(pm.LoadProject('Untitled Project')));r.OpenPage('cut')
