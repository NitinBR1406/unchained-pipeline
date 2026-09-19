"""Explicit Gemini UI recommendation mapping onto an already validated fixture.

The source response is never an approval. The transport receipt is supplied by
Orchestrator, and the exact envelope transformation remains auditable.
"""
from copy import deepcopy
from integration.contracts import canonical,digest,require,keys,verify_refs
from .validator import validate


def integrate(data,creative,response,receipt,resolver):
    validate(data,creative,resolver)
    keys(response,'request_id edit_plan editorial publication_authorized real_media_review')
    require(response['publication_authorized'] is False and response['real_media_review'] is False,'recommendations scope')
    require(receipt['status']=='COMPLETED' and receipt['request_id']==response['request_id'] and receipt['scope']=='SYNTHETIC_RECOMMENDATIONS_ONLY','receipt scope')
    verify_refs(list(receipt['refs'].values()),resolver)
    import json
    require(canonical(json.loads(resolver(receipt['refs']['result']['uri'])))==canonical(response),'response receipt mismatch')
    e=response['editorial'];keys(e,'title caption hashtags cta hook hypothesis')
    require(len(data['PLATFORM_PACKAGES'])==len(data['DERIVATIVES'])==len(data['HYPOTHESES'])==len(data['AGENT_EVIDENCE'])==1,'bounded single-fixture mapping only')
    d=deepcopy(data);c=deepcopy(creative)
    c['package_id']=response['request_id'];c['created_at']=receipt['observed_at']
    c['producer']={'agent':'GEMINI_UI','model':receipt['exact_model_id'],'run_id':response['request_id']}
    c['payload']['edit_plan']=deepcopy(response['edit_plan'])
    c['evidence_refs'].append(deepcopy(receipt['refs']['result']))
    d['created_at']=receipt['observed_at'];d['source_package_sha256']=digest(canonical(c))
    eid='ev:gemini-v16-response';d['evidence_refs'].append(dict(evidence_id=eid,**receipt['refs']['result']))
    for k in ('title','caption','hashtags','cta'):d['PLATFORM_PACKAGES'][0][k]=deepcopy(e[k])
    d['DERIVATIVES'][0]['hook']=e['hook'];d['HYPOTHESES'][0]['statement']=e['hypothesis']
    agent=d['AGENT_EVIDENCE'][0];agent.update(source_agent_name='GEMINI_UI',model_id=c['producer']['model'],run_id=response['request_id'],observed_at=receipt['observed_at'])
    # A source response is not a signed receipt; do not manufacture authenticated_receipt_id.
    for row in d['CREATIVE_INTELLIGENCE']:row.update(source_package_id=c['package_id'],source_package_sha256=d['source_package_sha256'],created_at=c['created_at'],recommendation=e['hypothesis'])
    for row in d['PRODUCTION']:row.update(creative_package_sha256=d['source_package_sha256'],edit_plan_sha256=digest(canonical(c['payload']['edit_plan'])))
    for table in ('PLATFORM_PACKAGES','DERIVATIVES','HYPOTHESES','AGENT_EVIDENCE','CREATIVE_INTELLIGENCE','PRODUCTION'):
        for row in d[table]:row['evidence_ids'].append(eid)
    validate(d,c,resolver)
    return d,c
