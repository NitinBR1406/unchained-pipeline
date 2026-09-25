"""Project completed local R1 framed HLG study to V16.5 without human approval."""
import copy, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest, require, verify_refs, file_resolver
from integration.project_v09 import bytes_json, persist

ROOT = h.ROOT
PARENT = ROOT/'p0e4/evidence/r1_framed_study_v164/UNCHAINED_MASTER_PROJECT_STATE_V16_4.json'
PARENT_SHA = 'ca0f7350d1ea8706f210611e541db6c038ea80f25a19383ff37ddeafd53480ac'
PREFIX = PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
OUT = ROOT/'p0e4/evidence/r1_framed_study_v164_execution'
EVENT_ID = 'p0e4-v165-r1-framed-hlg-study-local-review-ready'
STATUS = 'WAITING_FOR_NITIN_R1_REFINED_COLOR_REVIEW'


def project(parent, ledger, resolver):
    require(digest(parent) == PARENT_SHA, 'parent drift')
    require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()), 'ledger prefix drift')
    events = ledger.read_all(); require(len(events) == 21, 'event count')
    event = events[-1]; require(event['event_id'] == EVENT_ID and event['agent'] == 'codex', 'event identity')
    payload = event['inputs']; require(payload['status'] == STATUS, 'status')
    verify_refs(payload['evidence_refs'], resolver)
    acceptance = json.loads(resolver(payload['acceptance_ref']))
    require(acceptance['status'] == STATUS and acceptance['full_master_rendered'] is False, 'scope')
    require(acceptance['technical_qc'] == 'GREEN_WITH_GEMINI_VISUAL_UNCERTAINTY', 'qc')
    require(acceptance['gemini_independent_review'] == 'COMPLETED_WITH_RENDITION_LIMITATIONS', 'gemini')
    require(acceptance['shared_drive_persistence'] == 'BLOCKED_BY_AUTOMATIC_APPROVAL_REVIEW_NO_COPY_PERFORMED', 'persistence truth')
    require(all(acceptance['governance'][k] is False for k in ('production_deployment_authorized','publication_authorized','full_master_render_authorized')), 'authority')
    reduced = derive(ledger, keyring={}); require(reduced['state_version'] == 21, 'reducer')
    state = json.loads(parent); before = copy.deepcopy(state['authorizations'])
    state.update(state_version=31, updated_at=event['timestamp'], updated_by='codex',
                 milestone='P0-E4 R1 framed HLG color study complete locally; waiting for Nitin color review')
    state['p0e4']['v165_r1_framed_hlg_execution'] = copy.deepcopy(payload)
    state['p0e4']['current_color_status'] = STATUS
    state['current_release'].update(status='BLOCKED', publish_ready=False)
    state['state_lineage'] = dict(parent_version=30, parent_sha256=PARENT_SHA,
        engineering_ledger_head_hash=reduced['ledger_head_hash'], engineering_transition_count=21)
    state['provenance'].append(dict(phase='P0-E4', status=STATUS, evidence_refs=copy.deepcopy(payload['evidence_refs'])))
    require(state['authorizations'] == before, 'authority mutated')
    require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False, 'gate')
    require(state['production_state']['first_real_poster'] == 'PAUSED_BY_NITIN', 'poster')
    return state


def main():
    acceptance_ref = str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT))
    excluded = {'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_5.json','SHA256SUMS.txt'}
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded)
    payload = {'status':STATUS, 'acceptance_ref':acceptance_ref,
               'evidence_refs':[{'uri':str(p.relative_to(ROOT)), 'sha256':digest(p.read_bytes())} for p in files]}
    path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists(): persist(path, PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all()) == 20:
        ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T07:50:00Z','codex',inputs=payload))
    else: require(ledger.read_all()[-1]['inputs'] == payload, 'immutable event conflict')
    raw=bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT)))
    require(raw == bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT))), 'replay')
    persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_5.json',raw)
    print(json.dumps({'state_version':31,'status':STATUS,'deterministic_replay':True}))


if __name__ == '__main__': main()
