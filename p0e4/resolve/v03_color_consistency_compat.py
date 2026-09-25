"""Render a disclosed H.264 viewing/QC rendition from the exact V03 review timeline."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
from multitake.r1_peak_highlights_eyelids import sha256
from resolve.aakhri_multitake_realization import sha

def run(root,project_name):
    root=Path(root).resolve(); authoritative=root/'AAKHRI_V03_COLOR_CONSISTENCY_REVIEW_V01.mov'
    expected='6abcf3378ecce5df960c3d88df6bf0a1429e185996f321ecb37a0c7c381ca69b'
    if sha256(authoritative)!=expected: raise ValueError('AUTHORITATIVE_DRIFT')
    import DaVinciResolveScript as d
    resolve=d.scriptapp('Resolve'); pm=resolve.GetProjectManager(); old=pm.GetCurrentProject(); oldn=old.GetName() if old else None; page=resolve.GetCurrentPage()
    project=pm.LoadProject(project_name)
    if not project: raise RuntimeError('LOAD')
    tl=project.GetCurrentTimeline(); origin=tl.GetStartFrame(); frames=1860
    if not project.SetCurrentRenderFormatAndCodec('mp4','H264'): raise RuntimeError('H264')
    project.SetCurrentRenderMode(1); out=root/'AAKHRI_V03_COLOR_CONSISTENCY_GEMINI_COMPAT_V01.mp4'
    if not project.SetRenderSettings({'SelectAllFrames':False,'MarkIn':origin,'MarkOut':origin+frames-1,'TargetDir':str(root),'CustomName':out.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':1080,'FormatHeight':1920,'FrameRate':30,'AudioCodec':'aac','AudioSampleRate':48000}): raise RuntimeError('SETTINGS')
    job=project.AddRenderJob()
    if not job or not project.StartRendering([job],False): raise RuntimeError('START')
    deadline=time.monotonic()+1200
    while project.IsRenderingInProgress() and time.monotonic()<deadline: time.sleep(.5)
    status=project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
    if status.get('JobStatus')!='Complete' or not out.exists(): raise RuntimeError(repr(status))
    receipt={'schema':'V03_COLOR_CONSISTENCY_GEMINI_COMPAT_RENDITION_V01','authoritative_source':{'path':str(authoritative),'sha256':expected},'compatibility_output':{'path':str(out),'sha256':sha(out)[0],'bytes':sha(out)[1]},'same_resolve_timeline':project_name,'classification':'DISCLOSED_SDR_DISPLAY_COMPATIBILITY_RENDITION_FOR_GEMINI_QC_ONLY','hdr_judgement_limit':'NOT_AUTHORITATIVE_FOR_HDR_PEAK_OR_DISPLAY_IDENTITY','status':'GREEN'}
    (root/'V03_COLOR_CONSISTENCY_GEMINI_COMPAT_RENDITION_V01.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    pm.SaveProject(); pm.CloseProject(project)
    if oldn: pm.LoadProject(oldn)
    if page: resolve.OpenPage(page)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('project');a=p.parse_args();run(a.root,a.project)
