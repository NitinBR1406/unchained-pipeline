import DaVinciResolveScript as d,json,pathlib
root=pathlib.Path(__file__).resolve().parent;r=d.scriptapp('Resolve');pm=r.GetProjectManager();p=pm.GetCurrentProject();assert p.GetName()=='UNCHAINED_V163_SYNTHETIC_20260923';m=p.GetMediaPool();main=p.GetCurrentTimeline();t=m.CreateEmptyTimeline('Supplemental_Probes');p.SetCurrentTimeline(t);out={}
def rec(k,v):
 out[k]=v;(root/'extra.json').write_text(json.dumps(out,indent=2,default=str));print(k,v,flush=True)
(root/'captions.srt').write_text('1\n00:00:00,000 --> 00:00:02,000\nUNCHAINED SYNTHETIC\n\n2\n00:00:02,000 --> 00:00:04,000\nCAPTION ACCEPTANCE\n')
sub=m.ImportMedia([str(root/'captions.srt')]);rec('srt_import',len(sub) if sub else 0)
try:
 sc=m.AppendToTimeline(sub) if sub else [];rec('srt_append',len(sc) if sc else 0);rec('subtitle_tracks',t.GetTrackCount('subtitle'));rec('subtitle_items',[[dict(text=x.GetName(),start=x.GetStart(),end=x.GetEnd()) for x in t.GetItemListInTrack('subtitle',i)] for i in range(1,t.GetTrackCount('subtitle')+1)])
except Exception as e:rec('srt_error',str(e))
rec('native_title',bool(t.InsertTitleIntoTimeline('Text')))
rec('fusion_title',bool(t.InsertFusionTitleIntoTimeline('Text+')))
rec('fairlight_open',r.OpenPage('fairlight'))
rec('audio_track',t.AddTrack('audio','stereo'));rec('timecode',t.SetCurrentTimecode('01:00:00:00'))
rec('fairlight_sample_insert',p.InsertAudioToCurrentTrackAtPlayhead(str(root/'synthetic.wav'),4800,48000))
rec('audio_items',[[dict(start=x.GetStart(True),end=x.GetEnd(True),left=x.GetLeftOffset(True)) for x in t.GetItemListInTrack('audio',i)] for i in range(1,t.GetTrackCount('audio')+1)])
rec('save',pm.SaveProject());p.SetCurrentTimeline(main)
