"""Verify actual Claude preflight readback against independently compiled groups.

Caller supplies observed transport evidence; package claims cannot authenticate
execution or create an approval. This verifier returns synthetic preflight only.
"""
import io
import json
import zipfile
from integration.contracts import require,canonical,digest
from .consumer import compile_preflight
ARCHIVE_SHA='e2edfbfa1b4840f1204e0ed9e9213e17798c0a8f7169a92dd53fba814cf4bbdd'
REQUEST_ID='P0E4_V154_PREFLIGHT_A'


def verify_external(result,data,creative,resolver,archive_bytes,decision):
    require(digest(archive_bytes)==ARCHIVE_SHA,'archive SHA mismatch')
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        fixture=json.loads(z.read('SHADOW_FIXTURE.json'))
    require(canonical(fixture['sidecar'])==canonical(data) and canonical(fixture['creative_package'])==canonical(creative),'archive fixture lineage mismatch')
    require(decision['archive_sha256']==ARCHIVE_SHA and decision['transfer_authorized'] is True,'transfer not authorized')
    require(decision['destination']=='Claude Desktop Dispatch','wrong transfer destination')
    require(decision['allowed_purpose']=='NON_PUBLISHING_SYNTHETIC_P0E4_PREFLIGHT','wrong transfer scope')
    for flag in ('production_deployment_authorized','make_sheet_mutation_authorized','cutover_authorized','publication_authorized','rights_clearance_granted','final_audio_binding_granted'):
        require(decision[flag] is False,'decision scope escalated')
    require(result['request_id']==REQUEST_ID,'wrong dispatch request')
    require(result['input_archive_sha256']==ARCHIVE_SHA,'returned archive mismatch')
    require(result['status'] in ('PASS','COMPLETE','COMPLETED'),'preflight did not succeed')
    expected=compile_preflight(data,creative,resolver)
    jobs=[{'package_id':j['package_id'],'groups':j['groups']} for j in expected['jobs']]
    # Serialized equality rejects bool/int, int/float, null/default and ordering drift.
    require(canonical(result['jobs'])==canonical(jobs),'CLAUDE_SEMANTIC_DRIFT')
    return dict(schema='CLAUDE_PREFLIGHT_VALIDATION',schema_version=1,status='PASS',
                request_id=REQUEST_ID,input_archive_sha256=ARCHIVE_SHA,
                result_sha256=digest(canonical(result)),expected_jobs_sha256=digest(canonical(jobs)),
                groups_per_package=14,packages=len(jobs),semantic_drift=False,
                scope='SYNTHETIC_PREFLIGHT_ONLY',live_make_execution_proven=False,
                fresh_gemini_execution_proven=False,publication_authorized=False)
