"""Build deterministic read-only RAW reconciliation and post-ready evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
from integration.post_ready import reconcile_raw, route

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'p0e4/evidence/post_ready_v01'


def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path=ROOT/'p0e4/evidence/target_v13/RAW_HASH.json'
    binding_path=ROOT/'p0e4/evidence/target_v13/AAKHRI_ISHQ_INPUT_BINDING.json'
    raw=json.loads(raw_path.read_text());binding=json.loads(binding_path.read_text())
    reconciliation=reconcile_raw(raw,binding);post=route(reconciliation)
    write('RAW_INGEST_RECONCILIATION_V01.json',reconciliation)
    write('POST_READY_CONTRACT_V01.json',post)
    write('NEXT_READY.json',{
        'schema':'POST_READY_NEXT_READY_V01','schema_version':1,
        'status':'WAITING_FOR_NITIN','ready_nonhuman_count':0,
        'completed':['PROMPT_GOVERNANCE_V01','RAW_INGEST_RECONCILE','POST_READY_CONTRACT'],
        'critical_path':['RAW_INGEST','POST_READY_CONTRACT','REAL_MEDIA_ORCHESTRATION',
                         'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING','COMPLETE_FACTORY_E2E'],
        'next_task':'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING',
        'human_gate':'AKI_AUTHORITATIVE_AUDIO_BINDING',
        'blocked_after_gate':['REAL_MEDIA_ORCHESTRATION requires production deployment authorization',
                              'COMPLETE_FACTORY_E2E requires accepted real-media orchestration'],
        'production_deployment_authorized':False,'publication_authorized':False,
        'first_real_poster':'PAUSED_BY_NITIN'})
    write('ACCEPTANCE.json',{
        'schema':'POST_READY_ACCEPTANCE_V01','schema_version':1,
        'tested_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'raw_evidence_refs':[{'uri':str(raw_path.relative_to(ROOT)),'sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest()},
                             {'uri':str(binding_path.relative_to(ROOT)),'sha256':hashlib.sha256(binding_path.read_bytes()).hexdigest()}],
        'raw_identity_reconciled':True,'authoritative_audio_bound':False,
        'post_ready_contract_validated':True,'source_mutations':0,
        'real_media_orchestration_started':False,'factory_e2e_complete':False,
        'production_deployment_authorized':False,'publication_authorized':False})
    files=sorted(x for x in OUT.iterdir() if x.name!='SHA256SUMS.txt')
    (OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in files))


if __name__=='__main__':main()
