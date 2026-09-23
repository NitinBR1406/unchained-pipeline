import DaVinciResolveScript as d,json,pathlib
root=pathlib.Path(__file__).resolve().parent;r=d.scriptapp('Resolve');pm=r.GetProjectManager();p=pm.GetCurrentProject();assert p.GetName()=='UNCHAINED_V163_SYNTHETIC_20260923';m=p.GetMediaPool();main=p.GetCurrentTimeline();probe=p.GetTimelineByIndex(2);p.SetCurrentTimeline(probe);out={}
def rec(k,v):
 out[k]=v;(root/'final_probe.json').write_text(json.dumps(out,indent=2,default=str));print(k,v,flush=True)
media=m.GetRootFolder().GetClipList();sub=m.ImportMedia([str(root/'captions.srt')])[0];rec('srt_properties',sub.GetClipProperty())
items=m.AppendToTimeline([dict(mediaPoolItem=sub,trackIndex=1,recordFrame=probe.GetStartFrame())]);rec('srt_items',[dict(name=x.GetName(),start=x.GetStart(),end=x.GetEnd(),track=x.GetTrackTypeAndIndex()) for x in items] if items else [])
rec('subtitle_count',probe.GetTrackCount('subtitle'));rec('subtitle_readback',[[dict(text=x.GetName(),start=x.GetStart(),end=x.GetEnd()) for x in probe.GetItemListInTrack('subtitle',i)] for i in range(1,probe.GetTrackCount('subtitle')+1)])
v=next(x for x in media if x.GetName()=='synthetic.mov');a=next(x for x in media if x.GetName()=='synthetic.wav')
rec('waveform_sync_return',m.AutoSyncAudio([v,a],dict(syncMode=r.AUDIO_SYNC_WAVEFORM,channelNumber=1,retainEmbeddedAudio=True,retainVideoMetadata=True)))
rec('video_audio_mapping',v.GetAudioMapping());p.SetCurrentTimeline(main);rec('save',pm.SaveProject())
