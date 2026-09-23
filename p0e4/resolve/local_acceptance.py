"""Resolve 21.1.0.17 synthetic-only acceptance. Never a production transport.

Uses the installed ResolvePython runtime. Requires the two hash-bound synthetic
fixtures, a disk project library and a new UNCHAINED_V163_SYNTHETIC project name.
No external template execution, uploads, preset changes or unscoped queue starts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

VERSION = [21, 1, 0, 17, '']
PRODUCT = 'DaVinci Resolve Studio'
FIXTURES = {'synthetic.mov': '8895e4e431120d5ca12bc2c8e20d64136ea0b534dc7dd27fd6883cb355d7b348', 'synthetic.wav': '7760bdedc79a1d2374a9ff850ef7a482937c25c1bbb8f39263071cb053b56038'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def cut_specs(media, origin):
    # Installed 21.1 probe proves endFrame is EXCLUSIVE, unlike older examples.
    return [dict(mediaPoolItem=media, startFrame=a, endFrame=b,
                 mediaType=1, trackIndex=1, recordFrame=origin+a)
            for a,b in ((0,50),(50,100))]

def check_root(root, name):
    root=Path(root).resolve()
    if not re.fullmatch(r'UNCHAINED_V163_SYNTHETIC_[A-Z0-9_]+',name):
        raise ValueError('SYNTHETIC_PROJECT_NAME_REQUIRED')
    if root.name!='resolve-v163' or root.parent.name!='.local':
        raise ValueError('PRIVATE_STAGING_ONLY')
    for file, expected in FIXTURES.items():
        p=root/file
        if p.is_symlink() or sha(p)!=expected:
            raise ValueError('SYNTHETIC_FIXTURE_SHA_MISMATCH')
    if len(FIXTURES)!=2:
        raise ValueError('MISSING_FIXTURE_BINDING')
    return root

def run(root,name):
    root=check_root(root,name)
    import DaVinciResolveScript as d
    r=d.scriptapp('Resolve')
    if not r or r.GetProductName()!=PRODUCT or r.GetVersion()!=VERSION:
        raise ValueError('UNVERIFIED_INSTALLED_VERSION')
    pm=r.GetProjectManager()
    if pm.GetCurrentDatabase()['DbType']!='Disk':
        raise ValueError('LOCAL_DISK_DATABASE_REQUIRED')
    if name in pm.GetProjectListInCurrentFolder():
        raise ValueError('NO_OVERWRITE_OR_DUPLICATE_REPLAY')
    report=root/(name+'.json')
    if report.exists() or (root/(name+'.mov')).exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    original=pm.GetCurrentProject();original_name=original.GetName() if original else None
    original_page=r.GetCurrentPage()
    out=dict(schema_version=1,project=name,installation=dict(product=PRODUCT,version=VERSION),
             synthetic_input_sha256=FIXTURES,production_deployment_authorized=False,
             publication_authorized=False,first_real_poster='PAUSED_BY_NITIN',
             nitin_audio_source_binding_inferred=False)
    def rec(k,v):
        out[k]=v;report.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
        print(k,json.dumps(v,default=str),flush=True)
    p=None;job=None
    try:
        p=pm.CreateProject(name);assert p,'create project'
        assert p.SetSettings(dict(timelineResolutionWidth='640',timelineResolutionHeight='360',timelineFrameRate='25'))
        m=p.GetMediaPool();v=m.ImportMedia([str(root/'synthetic.mov')]);a=m.ImportMedia([str(root/'synthetic.wav')]);assert len(v)==len(a)==1
        t=m.CreateEmptyTimeline('Synthetic_100_Frames');assert t and p.SetCurrentTimeline(t)
        s=t.GetStartFrame();clips=m.AppendToTimeline(cut_specs(v[0],s));assert len(clips)==2
        bounds=[dict(start=x.GetStart()-s,end=x.GetEnd()-s,duration=x.GetDuration(),source_start=x.GetLeftOffset()) for x in clips]
        assert bounds==[dict(start=0,end=50,duration=50,source_start=0),dict(start=50,end=100,duration=50,source_start=50)]
        rec('cuts',bounds)
        expected=dict(ZoomX=1.1,ZoomY=1.1,Pan=12.,Tilt=-6.)
        assert clips[0].SetProperties(expected)
        actual=clips[0].GetProperties();assert all(actual[k]==v for k,v in expected.items());rec('transform',expected)
        audio=m.AppendToTimeline([dict(mediaPoolItem=a[0],startFrame=0,endFrame=100,mediaType=2,trackIndex=1,recordFrame=s)])
        assert len(audio)==1 and audio[0].GetStart()==s and audio[0].GetEnd()==s+100
        assert audio[0].SetProperties(dict(AudioVolume=-6.))
        assert audio[0].GetProperties()['AudioVolume']==-6.
        rec('audio',dict(start=0,end=100,volume_db=-6.,offset_samples=0,sample_rate=48000))
        c=clips[0].AddFusionComp();assert c
        x=c.AddTool('Transform');x.SetAttrs({'TOOLS_Name':'UN_PushShake'});x.Input=c.FindTool('MediaIn1').Output
        x.Size=c.BezierSpline();x.Size[0]=1.;x.Size[49]=1.2
        x.Angle=c.BezierSpline()
        for f,value in [(0,0.),(12,0.8),(24,-0.8),(36,0.4),(49,0.)]:x.Angle[f]=value
        g=c.AddTool('SoftGlow');g.SetAttrs({'TOOLS_Name':'UN_Glow'});g.Input=x.Output;g.Gain=0.15
        text=c.AddTool('TextPlus');text.SetAttrs({'TOOLS_Name':'UN_Lyric'});text.StyledText='UNCHAINED\nSYNTHETIC TEST';text.Font='Arial';text.Size=c.BezierSpline()
        for f,value in [(0,0.055),(24,0.08),(49,0.055)]:text.Size[f]=value
        merge=c.AddTool('Merge');merge.Background=g.Output;merge.Foreground=text.Output;c.FindTool('MediaOut1').Input=merge.Output
        assert x.GetInput('Size',49)==1.2 and x.GetInput('Angle',24)==-0.8
        assert text.GetInput('Size',24)==0.08 and g.GetInput('Gain')==0.15
        template=root/(name+'.comp');assert clips[0].ExportFusionComp(str(template),1)
        imported=clips[1].ImportFusionComp(str(template));assert imported
        assert imported.FindTool('UN_Lyric').GetInput('StyledText')=='UNCHAINED\nSYNTHETIC TEST'
        assert imported.FindTool('UN_PushShake').GetInput('Size',49)==1.2
        rec('fusion',dict(zoom_end=1.2,shake_frame24=-0.8,text_peak_size=0.08,glow_gain=0.15,template_import_readback=True,template_sha256=sha(template)))
        assert r.OpenPage('fairlight');rec('fairlight',dict(presets=r.GetFairlightPresets(),normalization_modes=t.GetNormalizeAudioModes(),page=r.GetCurrentPage()))
        assert p.SetCurrentRenderFormatAndCodec('mov','ProRes422LT') and p.SetCurrentRenderMode(1)
        assert p.SetRenderSettings(dict(SelectAllFrames=False,MarkIn=s,MarkOut=s+99,TargetDir=str(root),CustomName=name,ExportVideo=True,ExportAudio=True,FormatWidth=640,FormatHeight=360,FrameRate=25,AudioCodec='lpcm',AudioBitDepth=16,AudioSampleRate=48000))
        job=p.AddRenderJob();assert job;rec('job_id',job)
        assert p.StartRendering([job],False)
        deadline=time.monotonic()+120
        while p.IsRenderingInProgress() and time.monotonic()<deadline:time.sleep(0.5)
        if p.IsRenderingInProgress():p.StopRendering();raise RuntimeError('SYNTHETIC_RENDER_TIMEOUT')
        status=p.GetRenderJobStatus(job);assert status['JobStatus']=='Complete',status
        output=root/(name+'.mov');rec('render',dict(status=status,sha256=sha(output),bytes=output.stat().st_size,private_output=str(output)))
        assert pm.SaveProject();assert pm.ExportProject(name,str(root/(name+'.drp')),False)
        rec('status','PASS_SYNTHETIC_BOUNDED_CAPABILITIES')
    except Exception as e:
        rec('error',repr(e));raise
    finally:
        if p:
            if job and not p.IsRenderingInProgress():rec('render_job_removed',p.DeleteRenderJob(job))
            pm.SaveProject();rec('closed',pm.CloseProject(p))
        if original_name:rec('original_project_restored',bool(pm.LoadProject(original_name)))
        if original_page:r.OpenPage(original_page)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('name');args=parser.parse_args();run(args.root,args.name)
