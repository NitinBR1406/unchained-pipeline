"""Pure canonical adapter. It never imports Resolve or executes a render.

The existing edit contract intentionally lacks geometry, caption text and effect
presets. Preserve those recommendations verbatim and block execution rather than
inventing their meaning. Frame conversion is exact or rejected, never rounded.
"""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from canonical.consumer import compile_preflight
from integration.contracts import canonical,digest,require,keys,sha,timestamp,verify_refs

CAPABILITIES=json.loads((Path(__file__).parent/'CAPABILITY_MATRIX_V01.json').read_bytes())
DIMENSIONS={'9:16':(1080,1920),'16:9':(1920,1080),'1:1':(1080,1080),'4:5':(1080,1350)}
GATES=dict(production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')


def frame(ms,fps):
    require(type(ms) is int and ms>=0,'invalid milliseconds')
    value=Fraction(ms*fps[0],1000*fps[1])
    require(value.denominator==1,'FRAME_ALIGNMENT_REQUIRES_EXPLICIT_TIMING_REVISION')
    return value.numerator


def build(data,creative,resolver,fps=(25,1)):
    require(type(fps) in (tuple,list) and len(fps)==2 and all(type(x) is int and x>0 for x in fps),'invalid frame rate')
    require(Fraction(*fps)<=60,'PROFILE_REQUIRES_STUDIO_CAPABILITY_REVIEW')
    preflight=compile_preflight(data,creative,resolver)
    jobs=[]
    for job in preflight['jobs']:
        g=job['groups'];lo,hi=g['timestamps']['start_ms'],g['timestamps']['end_ms']
        require(hi>lo,'empty derivative')
        require(g['aspect_ratios'] in DIMENSIONS,'UNSUPPORTED_ASPECT_RATIO')
        cuts=[];performance=0
        for s in g['edit_effects']['segments']:
            start,end=max(lo,s['start_ms']),min(hi,s['end_ms'])
            if end<=start:continue
            ss=s['source_start_ms']+start-s['start_ms'];se=ss+end-start
            cuts.append(dict(start_frame=frame(start-lo,fps),end_frame_exclusive=frame(end-lo,fps),source_start_frame=frame(ss,fps),source_end_frame_exclusive=frame(se,fps),source_sha256=s['source_sha256'],performer_visible=s['performer_visible']))
            if s['performer_visible']:performance+=end-start
        require(performance*5 >= (hi-lo)*4,'DERIVATIVE_80_PERCENT_PERFORMANCE_RULE')
        width,height=DIMENSIONS[g['aspect_ratios']]
        blockers=['RESOLVE_INSTALLATION_AND_LOCAL_CAPABILITY_NOT_PROVEN','OUTPUT_PROFILE_CODEC_SUPPORT_NOT_PROVEN','NITIN_AUDIO_SOURCE_BINDING_REQUIRED']
        operations=[]
        for e in g['edit_effects']['effects']:
            if e['end_ms']<=lo or e['start_ms']>=hi:continue
            require(e['kind'] in CAPABILITIES['operations'],'UNSUPPORTED_OPERATION')
            start,end=max(lo,e['start_ms']),min(hi,e['end_ms'])
            operations.append(dict(recommendation=deepcopy(e),start_frame=frame(start-lo,fps),end_frame_exclusive=frame(end-lo,fps),capability_id=e['kind'],execution_status='BLOCKED_MISSING_EXACT_OPERATION_PARAMETERS'))
            blockers.append('EXACT_PARAMETERS_REQUIRED:'+e['kind'])
        jobs.append(dict(package_id=job['package_id'],derivative_id=g['derivatives']['derivative_id'],platform=g['platform_targeting'],cuts=cuts,operations=operations,performance=dict(visible_ms=performance,duration_ms=hi-lo,minimum_fraction='4/5'),render_profile=dict(profile_id='LOCAL_REVIEW_H264_V01',width=width,height=height,aspect_ratio=g['aspect_ratios'],fps_numerator=fps[0],fps_denominator=fps[1],container='mp4',video_codec='H264',audio_codec='AAC',audio_sample_rate=48000,output_destination='PRIVATE_LOCAL_STAGING_ONLY',quick_export_upload=False,codec_probe_required=True),canonical_groups=deepcopy(g),blocking_reasons=sorted(set(blockers))))
    return dict(schema='RESOLVE_EXECUTION_PLAN',schema_version=1,content_id=data['content_id'],created_at=data['created_at'],producer={'agent':'CODEX_PLAN_ADAPTER','model':None},canonical_sha256=digest(canonical(data)),creative_sha256=digest(canonical(creative)),preflight_sha256=digest(canonical(preflight)),capability_matrix_sha256=digest(canonical(CAPABILITIES)),inputs=deepcopy(creative['inputs']),input_authority='INTEGRATION_TEST_INPUT_UNLESS_SEPARATELY_BOUND',evidence_refs=deepcopy(creative['evidence_refs']),jobs=jobs,outputs=[],status='PLAN_ONLY_EXECUTION_BLOCKED',resolve_execution_proven=False,**GATES)


def verify(plan,data,creative,resolver,fps=(25,1)):
    require(canonical(plan)==canonical(build(data,creative,resolver,fps)),'RESOLVE_PLAN_DRIFT')
    return dict(status='PASS',scope='OFFLINE_PLAN_ONLY',resolve_execution_proven=False,zero_semantic_drift=True,**GATES)


def execute(*args,**kwargs):
    raise ValueError('RESOLVE_TRANSPORT_NOT_IMPLEMENTED_INSTALL_AND_CAPABILITY_GATE')


QC_CHECKS=('technical','look_match','full_motion','lipsync','audio','platform_safe_area','performance_rule')


def review_candidate(plan,output,observations,resolver):
    """Bind untrusted QC observations to actual candidate bytes; no approval.

    A PASS here only means the observations are complete. Authenticated fresh
    independent QC still needs the existing integration.validate_chain route.
    """
    require(plan['schema']=='RESOLVE_EXECUTION_PLAN' and plan['resolve_execution_proven'] is False,'plan scope')
    require(all(plan[k]==v for k,v in GATES.items()),'governance escalation')
    keys(output,'uri sha256');sha(output['sha256'])
    require(digest(resolver(output['uri']))==output['sha256'],'candidate bytes mismatch')
    keys(observations,'plan_sha256 output_sha256 checked_at reviewer checks evidence_refs')
    require(observations['plan_sha256']==digest(canonical(plan)),'QC plan binding')
    require(observations['output_sha256']==output['sha256'],'QC output binding')
    timestamp(observations['checked_at']);keys(observations['reviewer'],'agent model run_id')
    require(bool(observations['reviewer']['agent']) and bool(observations['reviewer']['run_id']),'QC identity required')
    require(observations['reviewer']['agent']!=plan['producer']['agent'],'independent reviewer required')
    keys(observations['checks'],' '.join(QC_CHECKS));verify_refs(observations['evidence_refs'],resolver)
    require(all(v in ('PASS','FAIL','UNKNOWN') for v in observations['checks'].values()),'QC verdict')
    failed=[k for k,v in observations['checks'].items() if v!='PASS']
    return dict(schema='RESOLVE_QC_RECEIPT',schema_version=1,plan_sha256=digest(canonical(plan)),output=deepcopy(output),observations_sha256=digest(canonical(observations)),observations=deepcopy(observations),status='REWORK_REQUIRED' if failed else 'OBSERVATIONS_COMPLETE_AUTHENTICATED_QC_PENDING',rework=dict(required_checks=failed,parent_plan_sha256=digest(canonical(plan)),candidate_sha256=output['sha256'],next_action='REVISE_RECOMMENDATION_REVALIDATE_80_PERCENT_REPLAN' if failed else 'FRESH_AUTHENTICATED_INDEPENDENT_QC'),authenticated_qc_proven=False,resolve_execution_proven=False,**GATES)
