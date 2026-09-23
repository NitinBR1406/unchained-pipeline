"""Master-finishing compiler. Product documentation never enables transport."""
from copy import deepcopy
from pathlib import Path
import json
from integration.contracts import canonical,digest,require,keys,verify_refs
from resolve.plan import build,review_candidate
from resolve.operations import compile_operations,integer

MATRIX=json.loads((Path(__file__).parent/'MAXIMUM_CAPABILITY_MATRIX_V02.json').read_bytes())

class ResolveAdapter:
    def compile(self,data,creative,operations,finishing,resolver):
        base=build(data,creative,resolver)
        supplement=compile_operations(base,operations)
        # Resolve exact referenced bytes without executing style/template content.
        for op in operations['operations']:
            verify_refs([op['evidence_ref']],resolver)
            for name in ('style_ref','template_ref'):
                if name in op['parameters']:verify_refs([op['parameters'][name]],resolver)
        keys(finishing,'schema schema_version base_plan_sha256 color_look audio_sync lyric_cues')
        require(finishing['schema']=='MASTER_FINISHING_DETAILS' and type(finishing['schema_version']) is int and finishing['schema_version']==1,'finishing schema')
        require(finishing['base_plan_sha256']==digest(canonical(base)),'finishing SHA lineage')
        color=finishing['color_look'];keys(color,'mode baseline_ref')
        require(color['mode']=='PRESERVE_LOCKED_BASELINE','NITIN_CHANGE_APPROVAL_REQUIRED_FOR_LOOK_CHANGE')
        verify_refs([color['baseline_ref']],resolver)
        # A hash identifies proposed baseline bytes; it cannot manufacture approval.
        audio=finishing['audio_sync'];keys(audio,'source_sha256 sample_rate offset_samples gain_millidb preserve_pitch preserve_rate evidence_refs')
        require(audio['source_sha256']==next(x['sha256'] for x in creative['inputs'] if x['role']=='authoritative_audio'),'audio source mismatch')
        integer(audio['sample_rate'],8000,384000);integer(audio['offset_samples'],-2147483648,2147483647)
        require(type(audio['gain_millidb']) is int and audio['gain_millidb']==0 and audio['preserve_pitch'] is True and audio['preserve_rate'] is True,'LOCKED_AUDIO_BASELINE')
        verify_refs(audio['evidence_refs'],resolver)
        jobs={j['package_id']:j for j in base['jobs']};seen=set()
        require(type(finishing['lyric_cues']) is list,'lyric cues list')
        for cue in finishing['lyric_cues']:
            keys(cue,'cue_id package_id start_frame end_frame_exclusive text emphasis_spans style_ref evidence_ref')
            require(type(cue['cue_id']) is str and bool(cue['cue_id']) and cue['cue_id'] not in seen,'duplicate/empty cue ID');seen.add(cue['cue_id'])
            require(cue['package_id'] in jobs,'unknown lyric package')
            end=jobs[cue['package_id']]['cuts'][-1]['end_frame_exclusive']
            integer(cue['start_frame'],0,end-1);integer(cue['end_frame_exclusive'],cue['start_frame']+1,end)
            require(type(cue['text']) is str and 0<len(cue['text'])<=4096,'invalid lyric text')
            require(type(cue['emphasis_spans']) is list,'emphasis spans list')
            previous=0
            for span in cue['emphasis_spans']:
                keys(span,'start_character end_character_exclusive')
                integer(span['start_character'],previous,len(cue['text'])-1)
                integer(span['end_character_exclusive'],span['start_character']+1,len(cue['text']))
                previous=span['end_character_exclusive']
            verify_refs([cue['style_ref']],resolver);verify_refs([cue['evidence_ref']],resolver)
        return dict(schema='MASTER_FINISHING_EXECUTION_PLAN',schema_version=1,content_id=data['content_id'],
                    created_at=data['created_at'],producer={'agent':'CODEX_RESOLVE_ADAPTER','model':None},
                    base=base,operations=supplement,finishing=deepcopy(finishing),
                    matrix_sha256=digest(canonical(MATRIX)),canonical_sha256=digest(canonical(data)),
                    capability_routes=deepcopy(MATRIX['capabilities']),
                    attribution_policy='CANONICAL_SYSTEM_OF_RECORD_ALL_14_GROUPS_PRESERVED',
                    qc_checks=['look_match','audio_source_and_sample_offset','lip_sync','full_motion','safe_areas','lyric_text_exactness','80_percent_visible_per_derivative','output_sha256'],
                    status='PLAN_ONLY_INSTALLATION_CAPABILITY_AND_HUMAN_BINDINGS_REQUIRED',
                    resolve_execution_proven=False,production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')

    def synthetic_local_acceptance(self, staging_root, project_name):
        """Version/fixture-bound local smoke; never the production execute route."""
        from resolve.local_acceptance import run
        return run(staging_root, project_name)

    def execute(self,*args,**kwargs):
        raise ValueError('NO_VERIFIED_LOCAL_RESOLVE_TRANSPORT')

    def qc_rework(self,plan,output,review,resolver):
        keys(review,'finishing_plan_sha256 base_observations finishing_checks')
        require(review['finishing_plan_sha256']==digest(canonical(plan)),'full finishing QC lineage')
        checks=review['finishing_checks'];keys(checks,'lyric_text_exactness audio_source_and_sample_offset color_baseline_preserved')
        require(all(v in ('PASS','FAIL','UNKNOWN') for v in checks.values()),'finishing QC verdict')
        result=review_candidate(plan['base'],output,review['base_observations'],resolver)
        failed=[k for k,v in checks.items() if v!='PASS']
        if failed:
            result['status']='REWORK_REQUIRED'
            result['rework']['required_checks']+=failed
            result['rework']['next_action']='REVISE_RECOMMENDATION_REVALIDATE_80_PERCENT_REPLAN'
        result['finishing_plan_sha256']=review['finishing_plan_sha256']
        result['finishing_review_sha256']=digest(canonical(review))
        return result
