"""Register R1 refinement request and execution blocker; no approval transitions."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest, require, verify_refs, file_resolver
from integration.project_v09 import bytes_json, persist

ROOT = h.ROOT
PARENT = ROOT / 'p0e4/evidence/resolve_studio_v163/UNCHAINED_MASTER_PROJECT_STATE_V16_3.json'
PARENT_SHA = 'c8f9f5ffc29e430ac7b39142b609ad55949ed908b36c3332dcc83b53a9a73ced'
PREFIX = PARENT.parent / 'ENGINEERING_EVENT_LEDGER.jsonl'
OUT = ROOT / 'p0e4/evidence/r1_framed_study_v164'
EVENT_ID = 'p0e4-v164-r1-framed-study-prepared-host-blocked'
STATUS = 'R1_STUDY_PREPARED_MAC_EXECUTION_BLOCKED'
FEEDBACK = 'p0e4/evidence/aakhri_multitake_real_v01/r6/NITIN_R1_PROVISIONAL_REFINEMENT_REQUEST_V01.json'


def project(parent, ledger, resolver):
    require(digest(parent) == PARENT_SHA, 'parent changed')
    require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()), 'ledger prefix changed')
    events = ledger.read_all()
    require(len(events) == 20 and all(e['event_type'] == 'EVIDENCE_REGISTERED' for e in events), 'evidence-only ledger')
    event = events[-1]
    require(event['event_id'] == EVENT_ID and event['agent'] == 'codex', 'event identity')
    payload = event['inputs']
    require(set(payload) == {'status', 'evidence_refs', 'feedback_ref', 'study_ref'}, 'unexpected payload')
    require(payload['status'] == STATUS and payload['feedback_ref'] == FEEDBACK, 'scope changed')
    verify_refs(payload['evidence_refs'], resolver)
    paths = {r['uri'] for r in payload['evidence_refs']}
    require({FEEDBACK, payload['study_ref']} <= paths, 'unbound study or feedback')
    feedback = json.loads(resolver(FEEDBACK))
    require(feedback['selection_status'] == 'PROVISIONAL_BASE_SELECTED_REFINEMENT_REQUIRED', 'not provisional')
    require(feedback['provisional_base'] == 'R1_SUBTLE_RICHNESS', 'base mismatch')
    require(all(feedback['governance'][k] is False for k in ('final_color_approval', 'final_video_approval', 'publication_authorized', 'production_deployment_authorized')), 'feedback authority escalation')
    study = json.loads(resolver(payload['study_ref']))
    require(study['status'] == STATUS and study['render_started'] is False and study['gemini_dispatched'] is False, 'execution not proven')
    reduced = derive(ledger, keyring={})
    require(reduced['state_version'] == 20, 'unexpected reducer version')
    state = json.loads(parent)
    before = copy.deepcopy(state['authorizations'])
    state.update(state_version=30, updated_at=event['timestamp'], updated_by='codex',
                 milestone='P0-E4 R1 provisional choice recorded; framed HLG study prepared, Mac execution blocked')
    state['p0e4']['v164_r1_framed_study'] = copy.deepcopy(payload)
    state['p0e4']['current_color_status'] = STATUS
    state['current_release'].update(status='BLOCKED', publish_ready=False)
    state['state_lineage'] = dict(parent_version=29, parent_sha256=PARENT_SHA,
        engineering_ledger_head_hash=reduced['ledger_head_hash'], engineering_transition_count=20)
    state['provenance'].append(dict(phase='P0-E4', **copy.deepcopy(payload)))
    require(state['authorizations'] == before, 'authority mutated')
    require(all(before[k] is False for k in ('PRODUCTION_DEPLOYMENT_AUTHORIZED', 'PUBLICATION_AUTHORIZED')), 'unexpected authorization')
    require(state['production_state']['first_real_poster'] == 'PAUSED_BY_NITIN', 'poster gate')
    return state


def main():
    refs = [FEEDBACK, 'p0e4/evidence/aakhri_multitake_real_v01/r6/REGRESSION_V01.json',
            'p0e4/evidence/aakhri_multitake_real_v01/r6/HLG_COLOR_RICHNESS_CALIBRATION_V01.json',
            str((OUT / 'STUDY_REQUEST.json').relative_to(ROOT)),
            str((OUT / 'GEMINI_REVIEW_REQUEST.json').relative_to(ROOT))]
    payload = dict(status=STATUS, feedback_ref=FEEDBACK, study_ref=refs[3],
        evidence_refs=[dict(uri=p, sha256=digest((ROOT/p).read_bytes())) for p in refs])
    path = OUT / 'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists():
        persist(path, PREFIX.read_bytes())
    ledger = EventLedger(str(path))
    if len(ledger.read_all()) == 19:
        ledger.append(h.make_event(EVENT_ID, 'EVIDENCE_REGISTERED', '2026-09-25T07:06:22Z', 'codex', inputs=payload))
    else:
        require(ledger.read_all()[-1]['inputs'] == payload, 'immutable payload conflict')
    raw = bytes_json(project(PARENT.read_bytes(), ledger, file_resolver(ROOT)))
    persist(OUT / 'UNCHAINED_MASTER_PROJECT_STATE_V16_4.json', raw)
    require(raw == bytes_json(project(PARENT.read_bytes(), ledger, file_resolver(ROOT))), 'replay mismatch')
    print(json.dumps(dict(state_version=30, deterministic_replay=True, render_started=False)))


if __name__ == '__main__':
    main()
