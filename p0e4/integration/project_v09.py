"""Append-only V09 engineering evidence using the frozen ledger and reducer.

Only evidence is registered; no runtime approvals, campaign state or gates changed.
Replay verifies evidence bytes and returns the identical versioned projection.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import canonical, digest, require, timestamp, verify_refs, file_resolver

ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/human_binding/UNCHAINED_MASTER_PROJECT_STATE_V08.json'
PARENT_SHA='8feb7ce8a80d388aa6ba755bd83da54e2dc145cf53f99cc5e1edce52c1da0e37'
PREFIX=ROOT/'p0e4/evidence/human_binding/ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v09-integration-contracts-evidence'


def project(parent_bytes, ledger, prefix_bytes, resolver):
    require(digest(parent_bytes)==PARENT_SHA,'V08 parent mismatch')
    records=ledger.read_all()
    require(Path(ledger.path).read_bytes().startswith(prefix_bytes),'accepted ledger prefix changed')
    require(len(records)==4 and all(r['event_type']=='EVIDENCE_REGISTERED' for r in records), 'evidence-only V09 ledger required')
    require(records[-1]['event_id']==EVENT_ID and records[-1]['agent']=='codex','unexpected evidence author/event')
    derived=derive(ledger,keyring={})
    require(derived['state_version']==4,'reducer did not apply four evidence transitions')
    payload=records[-1]['inputs']
    require(set(payload)=={'tested_sha','ingested_at','evidence_refs','status','completed','remaining'},'unexpected authority field')
    require(type(payload['tested_sha']) is str and re.fullmatch('[0-9a-f]{40}',payload['tested_sha']), 'invalid tested commit')
    timestamp(payload['ingested_at']); verify_refs(payload['evidence_refs'],resolver)
    require(payload['status']=='OFFLINE_VERIFIED_LIVE_E2E_BLOCKED','unsafe milestone promotion')
    state=json.loads(parent_bytes)
    require(state['state_version']==13 and all(state['authorizations'][k] is False for k in
        ('PRODUCTION_DEPLOYMENT_AUTHORIZED','PUBLICATION_AUTHORIZED')),'parent governance differs')
    require(state['production_state']['first_real_poster']=='PAUSED_BY_NITIN','poster gate differs')
    state['state_version']=10+derived['state_version']
    state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
    state['milestone']='P0-E4 offline integration contracts verified; real E2E blocked'
    state['p0e4']['integration_followup']=copy.deepcopy(payload)
    state['p0e4']['verdict']='BLOCKED_NOT_GREEN'
    state['current_release'].update(status='BLOCKED',publish_ready=False)
    state['state_lineage']={'parent_version':13,'parent_sha256':PARENT_SHA,
        'engineering_ledger_head_hash':derived['ledger_head_hash'],
        'engineering_transition_count':derived['state_version']}
    state['provenance'].append(dict(phase='P0-E4',**copy.deepcopy(payload)))
    return state


def bytes_json(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()


def persist(path,raw):
    if path.exists():require(path.read_bytes()==raw,'immutable V09 evidence conflict: '+path.name)
    else:
        with path.open('xb') as f:f.write(raw)


def main(directory,at):
    out=Path(directory).resolve()
    regression=json.loads((out/'REGRESSION.json').read_text())
    require(regression['tracked_worktree_clean'] is True and regression['untracked_runtime_files']==[], 'exact committed source required')
    require(regression['passed']==regression['total'] and all(x['pass'] for x in regression['prior_manifests']), 'regression not passed')
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name not in
        ('ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V09.json','SHA256SUMS.txt','VERIFICATION.json','PERSISTENCE_RECEIPTS.json'))
    payload={'tested_sha':regression['tested_sha'],'ingested_at':at,
        'status':'OFFLINE_VERIFIED_LIVE_E2E_BLOCKED',
        'completed':['FAIL_CLOSED_RIGHTS_ROUTER_OFFLINE','EXISTING_PACKAGING_WRAPPER_OFFLINE',
                     'THREE_PACKAGE_CHAIN_VALIDATION','80_PERCENT_EDIT_CONSTRAINT',
                     'HASH_BOUND_INBOX','TEST_ONLY_GOLDEN_HARD_STOP'],
        'remaining':['AUTHENTICATED_GEMINI_CLAUDE_CAPABILITIES','AUTHORITATIVE_RAW_AUDIO_PAIR',
                     'REAL_RENDER_AND_INDEPENDENT_QC','RIGHTS_CLEARANCE','RELEASE_PACKAGE_REVIEW'],
        'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]}
    path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists():persist(path,PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all())==3:
        ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
    else:require(ledger.read_all()[-1]['inputs']==payload,'immutable V09 payload conflict')
    state=project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT))
    persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V09.json',bytes_json(state))
    replay=project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT))
    require(bytes_json(replay)==(out/'UNCHAINED_MASTER_PROJECT_STATE_V09.json').read_bytes(),'replay mismatch')
    print(json.dumps({'state_version':state['state_version'],'deterministic_replay':True,'publication_authorized':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--at',required=True);a=p.parse_args()
    main(a.directory,a.at)
