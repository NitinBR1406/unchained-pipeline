"""Add one controller acceptance evidence event; derive V15 via frozen reducer.

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
from canonical.validator import validate
from canonical.adapter import readback
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/history_v14/UNCHAINED_MASTER_PROJECT_STATE_V14.json'
PARENT_SHA='7c4aee9d56518bbf2aad7116e389156a7e25b219b115240d82a0702815d5d680'
PREFIX=ROOT/'p0e4/evidence/history_v14/ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v15-canonical-shadow'


def project(parent,ledger,prefix,resolver):
    require(digest(parent)==PARENT_SHA,'V14 hash mismatch')
    require(Path(ledger.path).read_bytes().startswith(prefix),'accepted ledger prefix changed')
    records=ledger.read_all()
    require(len(records)==10 and all(r['event_type']=='EVIDENCE_REGISTERED' for r in records),'evidence-only engineering ledger required')
    require(records[-1]['event_id']==EVENT_ID and records[-1]['agent']=='codex','event identity')
    state=json.loads(parent);payload=records[-1]['inputs']
    require(set(payload)=={'tested_sha','ingested_at','evidence_refs','acceptance'},'unexpected authority field')
    verify_refs(payload['evidence_refs'],resolver)
    acceptance=payload['acceptance']
    require(acceptance['status']=='CANONICAL_SHADOW_ACCEPTED_CUTOVER_BLOCKED','unaccepted controller')
    require(acceptance['deterministic_replay'] is True and acceptance['real_media_qc_proven'] is False and acceptance['durable_gui_dispatcher_proven'] is False,'UI scope exceeded')
    require(acceptance['first_real_poster']=='PAUSED_BY_NITIN','poster gate changed')
    require(acceptance['production_e2e_status']=='BLOCKED_NOT_GREEN' and bool(acceptance['blocked_tasks']),'production must remain blocked')
    refs=acceptance['shadow_refs']
    require(set(refs)=={'shadow','field_map','snapshot'},'shadow evidence refs')
    verify_refs(list(refs.values()),resolver)
    shadow=json.loads(resolver(refs['shadow']['uri']))
    field_map=json.loads(resolver(refs['field_map']['uri']))
    snapshot=json.loads(resolver(refs['snapshot']['uri']))
    require(acceptance['live_cutover_authorized'] is False and acceptance['live_adapter_proven'] is False,'cutover authority escalation')
    readback(shadow,field_map,snapshot,resolver)
    require(acceptance['production_deployment_authorized'] is False and acceptance['publication_authorized'] is False,'human gate changed')
    result=derive(ledger,keyring={});require(result['state_version']==10,'reducer count mismatch')
    state['state_version']=10+result['state_version'];state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
    state['milestone']='P0-E4 canonical factory shadow contract accepted; legacy cutover remains blocked'
    state['p0e4']['v15_canonical_contract']=copy.deepcopy(payload)
    state['p0e4']['verdict']='BLOCKED_NOT_GREEN'
    state['state_lineage']={'parent_version':19,'parent_sha256':PARENT_SHA,
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
        ('ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V15.json','SHA256SUMS.txt',
         'PERSISTENCE_RECEIPTS.json') and not p.name.endswith('.lock'))
    payload={'tested_sha':acceptance['tested_sha'],'ingested_at':at,'acceptance':acceptance,
             'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]}
    path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists():persist(path,PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all())==9:
        ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
    else:require(ledger.read_all()[-1]['inputs']==payload,'immutable V15 conflict')
    state=project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT))
    persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V15.json',bytes_json(state))
    require(bytes_json(project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT)))==
            (out/'UNCHAINED_MASTER_PROJECT_STATE_V15.json').read_bytes(),'V15 replay mismatch')
    print(json.dumps({'state_version':state['state_version'],'replay':True,'controller_acceptance':acceptance['status']}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--at',required=True)
    args=parser.parse_args();main(args.directory,args.at)
