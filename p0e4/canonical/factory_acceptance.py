"""Recompute V16 acceptance from hash-bound evidence, not agent prose."""
import json
from .fixtures import fixture
from .intelligence_intake import integrate
from .factory import verify_preparation,shadow_bundle
from integration.contracts import verify_refs,require,canonical,digest


def verify(refs,resolver):
    require(set(refs)=={'canonical','creative','claude','factory','gemini','gemini_receipt','claude_receipt','claude_hash','handoff','bundle','drive','field_map','snapshot','decision','decision_text'},'V16 evidence refs')
    verify_refs(list(refs.values()),resolver)
    get=lambda k:json.loads(resolver(refs[k]['uri']))
    d,c,b=fixture()
    resolve=lambda u:b[u] if u in b else resolver(u)
    gd,gc=integrate(d,c,get('gemini'),get('gemini_receipt'),resolve)
    require(canonical(gd)==canonical(get('canonical')) and canonical(gc)==canonical(get('creative')),'Gemini canonical mapping drift')
    cr=get('claude_receipt');verify_refs(list(cr['refs'].values()),resolver)
    require(cr['status']=='COMPLETED' and cr['request_id']=='P0E4_V16_FACTORY_INTEGRATION_A' and cr['publication_authorized'] is False,'Claude receipt scope')
    require(cr['refs']['result']==refs['claude'] and cr['refs']['attachment']==refs['handoff'],'Claude artifact binding')
    ch=get('claude_hash');require(ch['canonical_match'] is True and ch['attachment_match'] is True,'Claude hash not verified')
    require(ch['computed_canonical_sha256']==digest(canonical(gd)) and ch['input_attachment_sha256']==refs['handoff']['sha256'] and ch['jobs_sha256']==digest(canonical(get('claude')['jobs'])),'hash domain mismatch')
    v=verify_preparation(get('factory'),gd,gc,get('claude'),get('field_map'),get('snapshot'),resolve)
    blob=shadow_bundle(get('factory'),gd,gc,get('claude'),get('field_map'),get('snapshot'),resolve)
    require(blob==resolver(refs['bundle']['uri']),'shadow bytes drift')
    drive=get('drive');require(drive['remote_bytes_equal'] is True and drive['remote_sha256']==digest(blob),'Drive readback mismatch')
    require(drive['metadata']['drive_id']=='0AG0CqqUZ6YuXUk9PVA','wrong authoritative drive')
    decision=get('decision');require(decision['engineering_authorized'] is True and decision['source_sha256']==refs['decision_text']['sha256'],'engineering decision')
    require(all(decision[k] is False for k in ('production_deployment_authorized','publication_authorized','live_cutover_authorized')),'human gate changed')
    return dict(**v,fresh_gemini_recommendations_proven=True,actual_claude_transform_proven=True,shared_drive_exact_readback=True,canonical_sha256=digest(canonical(gd)),bundle_sha256=digest(blob),real_media_qc_proven=False)
