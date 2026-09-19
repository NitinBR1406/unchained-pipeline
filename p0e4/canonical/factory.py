"""Additive, offline consumers around the existing Factory, never live Make dispatch.

Four layers consume explicit fields. Unknown groups and any semantic loss fail
closed. The output is a preparation artifact, not a render or approval receipt.
"""
from copy import deepcopy
import json
from pathlib import Path
from .render_request import prepare_clip,readback_clip
from integration.contracts import canonical,digest,require,verify_refs
from integration.existing_system import PackagingEngine
from unpipe.adapters import DerivativeEngine
from .consumer import compile_preflight
from .validator import validate,attribution
from .adapter import shadow
from .coverage import REQUIRED
from .shadow_bundle import build,verify

ROUTES={
 'title':'release.existing_package.title','caption':'release.existing_package.caption',
 'hashtags':'release.existing_package.hashtags','cta':'release.existing_package.cta',
 'hooks':'production.opening_hook','timestamps':'production.cut',
 'derivatives':'production.assets','aspect_ratios':'production.aspect_ratio',
 'edit_effects':'production.edit_plan','thumbnails_posters':'release.artwork',
 'platform_targeting':'release.existing_package.platform','schedules':'release.schedule',
 'experiments':'learning.experiment_context','provenance':'learning.provenance',
}


def read_groups(job):
    def get(path):
        x=job
        for key in path.split('.'):x=x[key]
        return deepcopy(x)
    return {g:get(path) for g,path in ROUTES.items()}


def prepare(data,creative,claude_result,field_map,snapshot,resolver):
    index=validate(data,creative,resolver)
    expected=compile_preflight(data,creative,resolver)
    require(set(claude_result)=={'schema','schema_version','canonical_sha256','jobs','publication_authorized'},'Claude result fields')
    require(claude_result['schema']=='CLAUDE_FACTORY_INPUT' and type(claude_result['schema_version']) is int and claude_result['schema_version']==1,'Claude schema')
    require(claude_result['publication_authorized'] is False,'Claude cannot authorize publication')
    require(claude_result['canonical_sha256']==expected['canonical_sha256'],'Claude lineage')
    projected=[dict(package_id=j['package_id'],groups=j['groups']) for j in expected['jobs']]
    require(canonical(claude_result['jobs'])==canonical(projected),'CLAUDE_SEMANTIC_DRIFT')
    legacy=shadow(data,creative,field_map,snapshot,resolver)
    jobs=[]
    for j in claude_result['jobs']:
        g=j['groups'];require(set(g)==set(REQUIRED)==set(ROUTES),'REQUIRED_UNMAPPED_EXECUTION_FIELD')
        package=index['PLATFORM_PACKAGES'][j['package_id']]
        d=index['DERIVATIVES'][package['derivative_id']]
        campaign=index['CONTENT_MASTER'][d['content_id']]['campaign_id']
        draft=PackagingEngine().build(campaign,[g['platform_targeting']],{'title':g['title'],'rights_status':'RIGHTS_HOLD'})
        draft['generated_at']=data['created_at'];existing=draft['packages'][0]
        existing.update(title=g['title'],caption=g['caption'],hashtags=deepcopy(g['hashtags']),cta=g['cta'],publish_datetime=g['schedules']['scheduled_at'])
        existing['thumbnail']=g['thumbnails_posters']['thumbnail']['uri'] if g['thumbnails_posters']['thumbnail'] else None
        plan=DerivativeEngine().plan(campaign,g['derivatives']['source_asset']['uri'],[g['platform_targeting']])
        plan['generated_at']=data['created_at']
        job=dict(package_id=j['package_id'],production=dict(existing_derivative_plan=plan,opening_hook=g['hooks'],cut=deepcopy(g['timestamps']),assets=deepcopy(g['derivatives']),aspect_ratio=g['aspect_ratios'],edit_plan=deepcopy(g['edit_effects']),status='PREPARED_NOT_RENDERED'),release=dict(existing_package=existing,existing_packaging_metadata={k:v for k,v in draft.items() if k!='packages'},artwork=deepcopy(g['thumbnails_posters']),schedule=deepcopy(g['schedules']),status='DRAFT_NOT_SCHEDULED'),learning=dict(experiment_context=deepcopy(g['experiments']),provenance=deepcopy(g['provenance']),attribution=[attribution(data,p['publication_id']) for p in data['PUBLICATION'] if p['package_id']==j['package_id']]))
        require(canonical(read_groups(job))==canonical(g),'FACTORY_SEMANTIC_DRIFT')
        interface=json.loads((Path(__file__).parent/'RENDER_INTERFACE_V16.json').read_bytes())
        try:
            native=prepare_clip(g,interface['evidence_refs'],resolver)
            require(canonical(readback_clip(native))==canonical({k:g[k] for k in ('timestamps','hooks','cta')}),'native request drift')
            job['production']['existing_endpoint_request']=native
        except ValueError as exc:
            if str(exc) not in ('UNMAPPED_RENDER_ASPECT_RATIO','UNMAPPED_RENDER_EFFECT_SEMANTICS'):raise
            job['production']['existing_endpoint_request']={'status':'BLOCKED_UNMAPPED_RENDER_SEMANTICS','reason':str(exc),'render_called':False}
        jobs.append(job)
    # Preserve all growth/commercial observation records, including absence of values.
    learning={t:deepcopy(data[t]) for t in ('CAMPAIGNS','HYPOTHESES','EXPERIMENTS','CREATIVE_INTELLIGENCE','PUBLICATION','ANALYTICS','AUDIENCE_GROWTH','BUSINESS_FUNNEL','MONETIZATION','AGENT_EVIDENCE')}
    return dict(schema='EXISTING_FACTORY_PREPARATION',schema_version=1,canonical_sha256=expected['canonical_sha256'],creative_sha256=expected['creative_sha256'],claude_input_sha256=digest(canonical(claude_result)),routes=deepcopy(ROUTES),jobs=jobs,legacy_shadow=legacy,learning=learning,status='NON_PUBLISHING_PREPARATION_ONLY',prepared_group_count=14,live_execution_proven=False,production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')


def verify_preparation(result,data,creative,claude_result,field_map,snapshot,resolver):
    require(canonical(result)==canonical(prepare(data,creative,claude_result,field_map,snapshot,resolver)),'FACTORY_OUTPUT_DRIFT')
    return dict(status='PASS',groups_per_package=14,semantic_drift=False,scope='EXISTING_FACTORY_OFFLINE_CONSUMERS',live_make_execution_proven=False,render_execution_proven=False,publication_authorized=False)


def shadow_bundle(result,data,creative,claude_result,field_map,snapshot,resolver):
    verify_preparation(result,data,creative,claude_result,field_map,snapshot,resolver)
    files={'FACTORY_PREPARATION.json':canonical(result),'CANONICAL.json':canonical(data),'CREATIVE_INTELLIGENCE_PACKAGE.json':canonical(creative),'CLAUDE_FACTORY_INPUT.json':canonical(claude_result)}
    blob=build(files);require(verify(blob,digest(blob))==files,'shadow replay drift');return blob


def execute_live(*args,**kwargs):
    raise ValueError('NITIN_CHANGE_APPROVAL_AND_PRODUCTION_DEPLOYMENT_REQUIRED')
