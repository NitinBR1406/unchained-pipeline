"""Canonical -> Claude production preflight, not a legacy live write adapter.

Every required group is consumed into explicit typed production instructions.
The existing source validator remains authoritative. No default captions, ID
crosswalks, schedules, rights, approvals or effects are inferred.
"""
from copy import deepcopy
from integration.contracts import canonical,digest,require,keys
from .validator import validate
from .coverage import REQUIRED
from .legacy_codecs import encode_tokens,encode_schedule


def compile_preflight(data,creative,resolver):
    index=validate(data,creative,resolver)
    require(bool(data['PLATFORM_PACKAGES']),'no packages')
    jobs=[]
    for p in data['PLATFORM_PACKAGES']:
        d=index['DERIVATIVES'][p['derivative_id']]
        require(d['end_ms']<=creative['payload']['edit_plan']['duration_ms'],'derivative exceeds creative timeline')
        def asset(a):return deepcopy(index['ASSETS'][a]) if a is not None else None
        groups={
          'title':p['title'], 'caption':p['caption'], 'hashtags':deepcopy(p['hashtags']),
          'cta':p['cta'], 'hooks':d['hook'],
          'timestamps':{'start_ms':d['start_ms'],'end_ms':d['end_ms']},
          'derivatives':{'derivative_id':d['derivative_id'],'kind':d['kind'],'source_asset':asset(d['source_asset_id']),'output_asset':asset(d['asset_id'])},
          'aspect_ratios':d['aspect_ratio'],
          'edit_effects':deepcopy(creative['payload']['edit_plan']),
          'thumbnails_posters':{'thumbnail':asset(p['thumbnail_asset_id']),'poster':asset(p['poster_asset_id'])},
          'platform_targeting':p['platform'],
          'schedules':{k:deepcopy(p[k]) for k in ('scheduled_at','schedule_timezone','schedule_version')},
          'experiments':{'experiment':deepcopy(index['EXPERIMENTS'][d['experiment_id']]) if d['experiment_id'] else None,'hypothesis':deepcopy(index['HYPOTHESES'][d['hypothesis_id']])},
          'provenance':{'content_id':data['content_id'],'package_id':p['package_id'],'source_package_sha256':data['source_package_sha256'],'agents':deepcopy(data['AGENT_EVIDENCE']),'evidence_refs':deepcopy(data['evidence_refs'])},
        }
        # Wire conversions are independently reversible. No fields are concatenated
        # into captions to hide missing legacy consumers or absent approvals.
        wire={'hashtags':encode_tokens(p['hashtags'],'hashtags'),
              'keywords':encode_tokens(p['keywords'],'keywords'),
              'amsterdam_schedule':encode_schedule(p['scheduled_at']) if p['scheduled_at'] else None}
        jobs.append(dict(package_id=p['package_id'],groups=groups,wire=wire,
                         required_groups=list(REQUIRED),group_sha256={k:digest(canonical(v)) for k,v in groups.items()},
                         status='PREFLIGHT_ONLY_PRODUCTION_BLOCKED'))
    return dict(schema='CLAUDE_PRODUCTION_PREFLIGHT',schema_version=1,
                canonical_sha256=digest(canonical(data)),creative_sha256=digest(canonical(creative)),
                jobs=jobs,preflight_group_coverage=14,live_legacy_execution_proven=False,
                production_deployment_authorized=False,publication_authorized=False,
                first_real_poster='PAUSED_BY_NITIN')


def verify_readback(result,data,creative,resolver):
    expected=compile_preflight(data,creative,resolver)
    require(result==expected,'PREFLIGHT_SEMANTIC_DRIFT')
    # Explicit group-level checks, not a returned source sidecar.
    for job in result['jobs']:
        require(set(job['groups'])==set(REQUIRED),'required group coverage')
        require(job['group_sha256']=={k:digest(canonical(v)) for k,v in job['groups'].items()},'group drift')
    return {'status':'PASS','groups_per_package':14,'zero_semantic_drift':True,
            'scope':'LOCAL_CLAUDE_PREFLIGHT_CONTRACT','live_legacy_execution_proven':False}


def execute_production(*args,**kwargs):
    raise ValueError('PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED_AND_LIVE_CONSUMERS_NOT_PROVEN')
