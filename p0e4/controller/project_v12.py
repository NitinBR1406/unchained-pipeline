"""Add one controller acceptance evidence event; derive V12 via frozen reducer.

Runtime execution ledger remains a separately hash-bound evidence chain. Neither
chain creates a human grant or changes production/publication authorization.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from integration.contracts import digest,require,file_resolver,verify_refs
from integration.project_v09 import persist,bytes_json
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/executor_v11/UNCHAINED_MASTER_PROJECT_STATE_V11.json'
PARENT_SHA='fa152db2f2b68abbc7963e3815a337759c4d8343f2dacff60df3c5b7065e49f1'
PREFIX=ROOT/'p0e4/evidence/executor_v11/ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v12-external-capability-discovery'


def project(parent,ledger,prefix,resolver):
    require(digest(parent)==PARENT_SHA,'V11 hash mismatch')
    require(Path(ledger.path).read_bytes().startswith(prefix),'accepted ledger prefix changed')
    records=ledger.read_all()
    require(len(records)==7 and all(r['event_type']=='EVIDENCE_REGISTERED' for r in records),'evidence-only engineering ledger required')
    require(records[-1]['event_id']==EVENT_ID and records[-1]['agent']=='codex','event identity')
    state=json.loads(parent);payload=records[-1]['inputs']
    require(set(payload)=={'tested_sha','ingested_at','evidence_refs','acceptance'},'unexpected authority field')
    verify_refs(payload['evidence_refs'],resolver)
    acceptance=payload['acceptance']
    require(acceptance['status']=='BLOCKED_EXTERNAL_SETUP','unaccepted controller')
    require(acceptance['authenticated_external_capabilities']==0 and acceptance['provider_execution_receipts']==[] and acceptance['deterministic_replay'] is True,'incomplete execution evidence')
    require(acceptance['production_deployment_authorized'] is False and acceptance['publication_authorized'] is False,'human gate changed')
    result=derive(ledger,keyring={});require(result['state_version']==7,'reducer count mismatch')
    state['state_version']=10+result['state_version'];state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
    state['milestone']='P0-E4 external capability discovery verified; external setup and RAW/audio binding blocked'
    state['p0e4']['external_integration']=copy.deepcopy(payload)
    state['p0e4']['verdict']='BLOCKED_NOT_GREEN'
    state['state_lineage']={'parent_version':16,'parent_sha256':PARENT_SHA,
        'engineering_ledger_head_hash':result['ledger_head_hash'],'engineering_transition_count':result['state_version']}
    state['provenance'].append({'phase':'P0-E4','status':acceptance['status'],'tested_sha':payload['tested_sha'],
                                'evidence_refs':copy.deepcopy(payload['evidence_refs'])})
    return state


def main(directory,at):
    out=Path(directory).resolve()
    acceptance=json.loads((out/'ACCEPTANCE.json').read_text())
    regression=json.loads((out/'REGRESSION.json').read_text())
    require(regression['passed']==regression['total'] and regression['tracked_worktree_clean'] is True,'regression/commit not clean')
    require(all(x['pass'] for x in regression['prior_manifests']),'historical manifest mismatch')
    require(acceptance['tested_sha']==regression['tested_sha'],'tested SHA differs')
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name not in
        ('ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V12.json','SHA256SUMS.txt',
         'PERSISTENCE_RECEIPTS.json') and not p.name.endswith('.lock'))
    payload={'tested_sha':acceptance['tested_sha'],'ingested_at':at,'acceptance':acceptance,
             'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]}
    path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists():persist(path,PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all())==6:
        ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
    else:require(ledger.read_all()[-1]['inputs']==payload,'immutable V12 conflict')
    state=project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT))
    persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V12.json',bytes_json(state))
    require(bytes_json(project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT)))==
            (out/'UNCHAINED_MASTER_PROJECT_STATE_V12.json').read_bytes(),'V12 replay mismatch')
    print(json.dumps({'state_version':state['state_version'],'replay':True,'controller_acceptance':acceptance['status']}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--at',required=True)
    args=parser.parse_args();main(args.directory,args.at)
