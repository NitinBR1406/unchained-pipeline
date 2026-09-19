"""Validate schema, attribution graph and source bytes. No approval or execution."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from integration.contracts import canonical,digest,require,validate as validate_creative,verify_refs,timestamp

SCHEMA=json.loads((Path(__file__).parent/'FACTORY_SCHEMA_V01.json').read_text())
TABLES={k:v for k,v in SCHEMA['properties'].items() if v.get('type')=='array' and k!='evidence_refs'}
PRIMARY={k:next(iter(v['items']['properties'])) for k,v in TABLES.items()}
TARGETS={PRIMARY[k]:k for k in TABLES}
TARGETS.update(source_asset_id='ASSETS',master_asset_id='ASSETS',thumbnail_asset_id='ASSETS',poster_asset_id='ASSETS',output_asset_id='ASSETS',executor_agent_id='AGENT_EVIDENCE',reviewer_agent_id='AGENT_EVIDENCE')


def validate(data,creative,resolver):
    errors=list(Draft202012Validator(SCHEMA).iter_errors(data))
    require(not errors,'schema: '+('; '.join(e.json_path+': '+e.message for e in errors[:3])))
    # JSON Schema numbers permit 1.0 for integer; wire format here requires integers.
    require(type(data['schema_version']) is int,'schema version type')
    timestamp(data['created_at'])
    require(bool(data['CREATIVE_INTELLIGENCE']),'missing creative intelligence')
    validate_creative(creative)
    require(creative['schema']=='CREATIVE_INTELLIGENCE_PACKAGE','creative input required')
    require(data['source_package_sha256']==digest(canonical(creative)),'creative SHA lineage')
    require(data['content_id']==creative['content_id'],'cross-content creative')
    require(creative['payload']['edit_plan']['baseline_locked'] is True,'locked baseline required')
    verify_refs(creative['evidence_refs'],resolver)
    for a in creative['inputs']:require(digest(resolver(a['uri']))==a['sha256'],'source bytes mismatch')
    evidence={r['evidence_id']:r for r in data['evidence_refs']}
    require(len(evidence)==len(data['evidence_refs']),'duplicate evidence IDs')
    verify_refs([{'uri':r['uri'],'sha256':r['sha256']} for r in evidence.values()],resolver)
    index={};all_ids=set()
    for table,key in PRIMARY.items():
        index[table]={}
        for row in data[table]:
            rid=row[key];require(rid not in all_ids,'duplicate ID');all_ids.add(rid)
            index[table][rid]=row
            require(bool(row['evidence_ids']) and set(row['evidence_ids'])<=set(evidence),'record evidence missing')
    require(data['content_id'] in index['CONTENT_MASTER'],'missing root content')
    source_assets={(a['uri'],a['sha256']) for a in data['ASSETS']}
    require(all((a['uri'],a['sha256']) in source_assets for a in creative['inputs']),'missing source asset registration')
    for table in TABLES:
        for row in data[table]:
            for field,value in row.items():
                if field==PRIMARY[table] or value is None:continue
                if field in TARGETS:require(value in index[TARGETS[field]],'dangling '+field)
                if field in ('receipt_evidence_id','binding_evidence_id','authenticated_receipt_id'):
                    require(value in evidence,'missing receipt evidence')
                if field.endswith('_at') and isinstance(value,str):timestamp(value)
            if table in ('ANALYTICS','AUDIENCE_GROWTH'):
                require(timestamp(row['window_start'])<=timestamp(row['window_end']),'inverted observation window')
                require((row['availability']=='OBSERVED')==(row['metric_value'] is not None),'unobserved metric invented')
            if table=='ASSETS':
                require(digest(resolver(row['uri']))==row['sha256'],'asset byte lineage')
                require(row['authority']!='NITIN_BOUND','shadow cannot establish Nitin binding')
                require(row['binding_evidence_id'] is None,'shadow binding forbidden')
            if table=='DERIVATIVES':
                require(row['end_ms']>row['start_ms'],'derivative range')
                require(index['ASSETS'][row['source_asset_id']]['content_id']==row['content_id'],'cross-content asset')
                require(index['HYPOTHESES'][row['hypothesis_id']]['content_id']==row['content_id'],'hypothesis content')
                if row['experiment_id']:
                    e=index['EXPERIMENTS'][row['experiment_id']]
                    require(e['hypothesis_id']==row['hypothesis_id'],'experiment hypothesis mismatch')
                    require(e['campaign_id']==index['CONTENT_MASTER'][row['content_id']]['campaign_id'],'experiment campaign mismatch')
            if table=='PRODUCTION':
                require(row['creative_package_sha256']==data['source_package_sha256'],'production creative mismatch')
                require(row['edit_plan_sha256']==digest(canonical(creative['payload']['edit_plan'])),'edit plan mismatch')
            if table=='PUBLICATION':
                require(row['platform']==index['PLATFORM_PACKAGES'][row['package_id']]['platform'],'conflicting platform')
                require(row['status']!='NOT_PUBLISHED' or (row['platform_post_id'] is None and row['published_at'] is None),'fake publication')
                require(row['status']!='OBSERVED_HISTORICAL' or row['receipt_evidence_id'] is not None,'publication receipt missing')
            if table=='QC_APPROVALS':require(row['actual_asset_sha256']==index['ASSETS'][row['asset_id']]['sha256'],'QC wrong asset')
            if 'content_id' in row:require(row['content_id']==data['content_id'],'cross-content record')
            if table=='CREATIVE_INTELLIGENCE':
                require(row['source_package_id']==creative['package_id'] and row['source_package_sha256']==data['source_package_sha256'],'intelligence lineage')
                agent=index['AGENT_EVIDENCE'][row['agent_id']]
                require(agent['agent_role']=='GEMINI_INTELLIGENCE','intelligence owner')
                require((agent['source_agent_name'],agent['model_id'],agent['run_id'])==(creative['producer']['agent'],creative['producer']['model'],creative['producer']['run_id']),'producer identity drift')
            if table=='PLATFORM_PACKAGES':
                from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
                try:ZoneInfo(row['schedule_timezone'])
                except (ZoneInfoNotFoundError,ValueError):raise ValueError('unknown timezone')
            if table in ('MONETIZATION','BUSINESS_FUNNEL') and row['publication_id']:
                require(attribution(data,row['publication_id'])['campaign_id']==row['campaign_id'],'commercial campaign mismatch')
            if table=='MONETIZATION' and row['funnel_id']:
                funnel=index['BUSINESS_FUNNEL'][row['funnel_id']]
                require(funnel['campaign_id']==row['campaign_id'],'revenue funnel campaign')
                require(row['publication_id']==funnel['publication_id'],'revenue funnel attribution conflict')
    canonical(data)
    return index


def attribution(data,publication_id):
    """Read-only trace; attribution is linkage, never proof of causal revenue lift."""
    def get(t,k,v):return next(r for r in data[t] if r[k]==v)
    pub=get('PUBLICATION','publication_id',publication_id)
    package=get('PLATFORM_PACKAGES','package_id',pub['package_id'])
    d=get('DERIVATIVES','derivative_id',package['derivative_id'])
    c=get('CONTENT_MASTER','content_id',d['content_id'])
    return dict(publication_id=publication_id,package_id=package['package_id'],derivative_id=d['derivative_id'],content_id=c['content_id'],campaign_id=c['campaign_id'],experiment_id=d['experiment_id'],hypothesis_id=d['hypothesis_id'])
