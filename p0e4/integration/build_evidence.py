"""Generate reproducible additive integration evidence, no network/media mutations."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration import contracts as c
from integration import existing_system as existing
from integration import fixtures, rights
from integration.ingest import inspect_inbox
from integration.pipeline import prepare_release
from integration.project_v09 import persist, bytes_json, ROOT


def build(out, at):
    out=Path(out)
    def write(name,value):persist(out/name,bytes_json(value))
    write('EXISTING_SYSTEM_INVENTORY.json',existing.inventory())
    write('RIGHTS_GRANTS.json',[])
    att=ROOT/'p0e4/evidence/human_binding/HUMAN_ATTESTATION.json'
    source=ROOT/'p0e4/evidence/human_binding/RIGHTS_MATRIX.json'
    media=json.loads((ROOT/'p0e4/evidence/human_binding/media/MEDIA_QC.json').read_text())['assets']
    assets=[{'name':a['name'],'sha256':a['sha256'],'file_id':a['file_id']} for a in media]
    refs=[{'uri':str(p.relative_to(ROOT)),'sha256':c.digest(p.read_bytes())} for p in (att,source)]
    rows=[]
    for platform in c.PLATFORMS:
        # Nulls preserve unknown scope. Never synthesize an account, territory or use.
        request={'content_id':'aakhri-ishq','asset_sha256':assets[0]['sha256'], 'platform':platform,
                 'territories':[], 'account_id':None,'use':None,'monetized':None,'at':at}
        decision=rights.evaluate(request,out/'RIGHTS_GRANTS.json',{},c.file_resolver(ROOT))
        rows.append({'platform':platform,'existing_campaign_target':platform!='x',
            'status':decision['status'],'pass':decision['pass'],
            'source_evidence_refs':refs,'scope':{'territories':None,'account_id':None,'use':None,'monetized':None},
            'recording_origin':'OWN_PRODUCTION_OWNER_ATTESTATION_ONLY',
            'composition':'NOT_ESTABLISHED','lyrics':'NOT_ESTABLISHED',
            'licence_evidence':'NOT_AVAILABLE','content_id_outcome':'UNKNOWN',
            'blockers':['NO_VERIFIED_CAMPAIGN_CLEARANCE','RELEASE_SCOPE_NOT_ESTABLISHED'],
            'router_result':decision})
    write('RIGHTS_MATRIX.json',{'schema_version':1,'content_id':'aakhri-ishq','status':'RIGHTS_HOLD',
        'evaluated_at':at,'assets_in_review':assets,'rows':rows,'rights_reviewer_keys_provisioned':False,
        'no_new_approval':True,'no_contact_purchase_or_upload':True})
    creative,production,qc,blobs,receipts=fixtures.chain()
    for package in (creative,production,qc):write('TEST_ONLY_'+package['schema']+'.json',package)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for uri,raw in blobs.items():
            target=root/uri;target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
        ingestion=inspect_inbox({'schema_version':1,'content_id':creative['content_id'],
            'received_at':fixtures.AT,'assets':creative['inputs']},root)
        chain_ok=c.validate_chain(creative,production,qc,c.file_resolver(root),receipts)
        blocked=prepare_release(creative,production,qc,resolver=c.file_resolver(root),
            authenticated_receipts=receipts,rights_store=out/'RIGHTS_GRANTS.json',reviewer_keys={},
            scope={'territories':['NL'],'account_id':'TEST_ONLY','use':'organic','monetized':False},at=fixtures.AT)
        write('TEST_ONLY_SAFE_SMOKE.json',{'fixture':'TEST_ONLY_NOT_REAL_AKHRI_ISHQ',
            'ingestion':ingestion,'package_chain_verified':chain_ok,'result':blocked,
            'positive_human_wait_boundary':'Exercised separately in test_rights_router.py with ephemeral TEST_ONLY reviewer and verifier double',
            'real_media_decode':False,'external_agent_executed':False,'external_side_effect_count':0,
            'cleanup':'Temporary fixture directory automatically removed'})
    write('GOLDEN_E2E_READINESS.json',{'content_id':'aakhri-ishq','status':'BLOCKED_NOT_GREEN',
        'raw_source_file_id':'1Uk6Ru7wtU1Y3aCeOdYQwPhuTojHzDgN6','raw_source_name':'AKI_SOURCE_0902_V01.mov',
        'raw_source_sha256':None,'authoritative_audio_file_id':None,'authoritative_audio_sha256':None,
        'available_proofs':['RAW metadata discovered in authoritative Drive folder',
            'V08 exact master/derivative SHA and historic decode evidence',
            'New offline contract/rights/ingest/wrapper tests'],
        'missing':['Verified RAW/audio SHA pair','Authenticated Gemini intelligence response',
            'Authenticated Claude execution receipt and rendered assets','Independent full Gemini QC',
            'Campaign-specific rights coverage','Exact package final review'],
        'target_terminal':'WAITING_FOR_NITIN_PUBLISH_APPROVAL','publish_ready':False,
        'publication_authorized':False,'production_deployment_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'})
    print('Rights matrix, existing wrapper inventory, package examples and safe smoke persisted')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--at',required=True);a=p.parse_args();c.timestamp(a.at);build(a.output,a.at)
