"""Build deterministic read-only RAW reconciliation and post-ready evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
from integration.post_ready import reconcile_raw, route, bind_authoritative_audio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'p0e4/evidence/post_ready_v01'


def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path=ROOT/'p0e4/evidence/target_v13/RAW_HASH.json'
    binding_path=ROOT/'p0e4/evidence/target_v13/AAKHRI_ISHQ_INPUT_BINDING.json'
    raw=json.loads(raw_path.read_text());binding=json.loads(binding_path.read_text())
    reconciliation=reconcile_raw(raw,binding)
    event_path=ROOT/'p0e4/evidence/audio_binding_v01/NITIN_AUTHORIZATION.json'
    observation_path=ROOT/'p0e4/evidence/audio_binding_v01/AUDIO_BYTE_OBSERVATION.json'
    event=json.loads(event_path.read_text());observation=json.loads(observation_path.read_text())
    audio_path=Path(observation['path']);before=audio_path.stat();audio_hash=hashlib.sha256()
    with audio_path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):audio_hash.update(chunk)
    after=audio_path.stat()
    if audio_hash.hexdigest()!=observation['sha256'] or after.st_size!=observation['size_bytes']:
        raise ValueError('authoritative audio byte observation drift')
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('authoritative audio changed during validation')
    reconciliation=bind_authoritative_audio(reconciliation,event,observation)
    post=route(reconciliation)
    write('RAW_INGEST_RECONCILIATION_V01.json',reconciliation)
    write('POST_READY_CONTRACT_V01.json',post)
    write('NEXT_READY.json',{
        'schema':'POST_READY_NEXT_READY_V01','schema_version':1,
        'status':'WAITING_FOR_NITIN_PRODUCTION_DEPLOYMENT_AUTHORIZATION','ready_nonhuman_count':0,
        'completed':['PROMPT_GOVERNANCE_V01','RAW_INGEST_RECONCILE','POST_READY_CONTRACT',
                     'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING','REAL_MEDIA_ORCHESTRATION_PLAN'],
        'critical_path':['RAW_INGEST','POST_READY_CONTRACT','REAL_MEDIA_ORCHESTRATION',
                         'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING','COMPLETE_FACTORY_E2E'],
        'next_task':'REAL_MEDIA_ORCHESTRATION',
        'human_gate':'PRODUCTION_DEPLOYMENT_AUTHORIZED',
        'blocked_after_gate':['REAL_MEDIA_ORCHESTRATION requires explicit production deployment authorization',
                              'COMPLETE_FACTORY_E2E requires accepted real-media orchestration'],
        'production_deployment_authorized':False,'publication_authorized':False,
        'first_real_poster':'PAUSED_BY_NITIN'})
    write('ACCEPTANCE.json',{
        'schema':'POST_READY_ACCEPTANCE_V01','schema_version':1,
        'tested_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'raw_evidence_refs':[{'uri':str(raw_path.relative_to(ROOT)),'sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest()},
                             {'uri':str(binding_path.relative_to(ROOT)),'sha256':hashlib.sha256(binding_path.read_bytes()).hexdigest()},
                             {'uri':str(event_path.relative_to(ROOT)),'sha256':hashlib.sha256(event_path.read_bytes()).hexdigest()},
                             {'uri':str(observation_path.relative_to(ROOT)),'sha256':hashlib.sha256(observation_path.read_bytes()).hexdigest()}],
        'raw_identity_reconciled':True,'authoritative_audio_bound':True,
        'post_ready_contract_validated':True,'source_mutations':0,
        'real_media_orchestration_started':False,'real_media_orchestration_plan_ready':True,
        'factory_e2e_complete':False,
        'production_deployment_authorized':False,'publication_authorized':False})
    write('REAL_MEDIA_ORCHESTRATION_PLAN_V01.json',{
        'schema':'REAL_MEDIA_ORCHESTRATION_PLAN_V01','schema_version':1,
        'content_id':'aakhri-ishq','mode':'PLAN_ONLY_NO_EXECUTION',
        'inputs':[{'role':'raw_video','uri':raw['path'],'sha256':raw['sha256'],'bytes':raw['bytes']},
                  reconciliation['authoritative_audio']],
        'ordered_stages':['HASH_REVERIFY','TECHNICAL_DECODE','EDIT_PLAN_BINDING','RESOLVE_RENDER',
                          'TECHNICAL_QC','INDEPENDENT_REAL_MEDIA_QC','PACKAGE_EVIDENCE'],
        'execution_status':'BLOCKED_PENDING_PRODUCTION_DEPLOYMENT_AUTHORIZATION',
        'rights_clearance':'NOT_INFERRED','publication_authorized':False,
        'production_deployment_authorized':False,'source_mutations':0})
    files=sorted(x for x in OUT.iterdir() if x.name!='SHA256SUMS.txt')
    (OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in files))


if __name__=='__main__':main()
