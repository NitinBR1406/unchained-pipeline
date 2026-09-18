"""Append-only E4 engineering evidence -> deterministic V06, preserving V05 human gates.

Versioned project snapshot composition (not replacement of the frozen runtime reducer).
Frozen reducer verifies/replays the new engineering ledger. The V05 parent is hash-bound.
"""
import json
from pathlib import Path
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

V05_SHA256 = '5d0c90cfd9b544304bb2dac762046c8ff66eb17e5bd3033188204f847d7b7bcf'


def project(parent, ledger):
    if h.digest(parent) != V05_SHA256:
        raise ValueError('authoritative parent differs from frozen V05')
    state = json.loads(parent)
    derived = derive(ledger, keyring={})  # verifies append-only hash chain and event contracts
    records = ledger.read_all()
    if len(records) != 1 or records[0]['event_type'] != 'EVIDENCE_REGISTERED':
        raise ValueError('V06 accepts exactly one E4 evidence registration, no authority events')
    evidence = records[0]['inputs']
    if evidence['verdict'] != 'BLOCKED_NOT_GREEN':
        raise ValueError('this update cannot grant GREEN or publication')
    state.update(state_version=state['state_version']+derived['state_version'],
                 phase='P0-E4', milestone='PRODUCTION INTEGRATION — ENGINEERING VERIFIED, HUMAN GATES PENDING',
                 updated_at=records[0]['timestamp'], updated_by='codex')
    state['current_content'] = 'aakhri-ishq'
    state['current_release'] = {'status':'BLOCKED','publish_ready':False,
        'next_gate_after_resolution':'NITIN_PUBLISH_APPROVAL'}
    state['p0e4'] = evidence
    state['state_lineage'] = {'parent_version':10,'parent_sha256':V05_SHA256,
        'engineering_ledger_head_hash':derived['ledger_head_hash'],
        'engineering_transition_count':derived['state_version']}
    state['provenance'].append({'phase':'P0-E4','status':'BLOCKED_NOT_GREEN',
        'tested_sha':evidence['tested_sha'],'evidence_refs':evidence['evidence_refs']})
    # No human authority can enter through engineering evidence.
    assert state['authorizations']['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False
    assert state['authorizations']['PUBLICATION_AUTHORIZED'] is False
    assert state['production_state']['first_real_poster']=='PAUSED_BY_NITIN'
    return state


def update(directory, summary, timestamp):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    ledger=EventLedger(str(directory/'ENGINEERING_EVENT_LEDGER.jsonl'))
    event=h.make_event('p0e4-v06-engineering-result','EVIDENCE_REGISTERED',timestamp,'codex',inputs=summary)
    existing=ledger.read_all()
    if not existing: ledger.append(event)
    elif existing[0]['inputs']!=summary or existing[0]['timestamp']!=timestamp:
        raise ValueError('V06 already recorded: use a subsequent version for changed evidence')
    state=project((h.ROOT/h.STATE).read_bytes(),ledger)
    path=directory/'UNCHAINED_MASTER_PROJECT_STATE_V06.json'
    data=json.dumps(state,sort_keys=True,indent=2).encode()
    if path.exists() and path.read_bytes()!=data: raise ValueError('immutable V06 conflict')
    path.write_bytes(data)
    return state
