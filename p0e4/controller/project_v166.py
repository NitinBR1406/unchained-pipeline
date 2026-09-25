"""Project the bounded R1 highlight/background refinement to V16.6."""
import copy, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest, require, verify_refs, file_resolver
from integration.project_v09 import bytes_json, persist

ROOT = h.ROOT
PARENT = ROOT/'p0e4/evidence/r1_framed_study_v164_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_5.json'
PARENT_SHA = '6edbedf6f4b4ba57669398258c9451439566f5c7c9c163b53cea2a07b01d7990'
PREFIX = PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
OUT = ROOT/'p0e4/evidence/r1_highlight_refinement_v01_execution'
EVENT_ID = 'p0e4-v166-r1-highlight-background-refinement-review-ready'
STATUS = 'WAITING_FOR_NITIN_HIGHLIGHT_BACKGROUND_COLOR_REVIEW'


def project(parent, ledger, resolver):
    require(digest(parent) == PARENT_SHA, 'parent drift')
    require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()), 'ledger prefix drift')
    events = ledger.read_all(); require(len(events) == 22, 'event count')
    event = events[-1]; require(event['event_id'] == EVENT_ID and event['agent'] == 'codex', 'event identity')
    payload = event['inputs']; require(payload['status'] == STATUS, 'status')
    verify_refs(payload['evidence_refs'], resolver)
    acceptance = json.loads(resolver(payload['acceptance_ref']))
    require(acceptance['status'] == STATUS and acceptance['full_master_rendered'] is False, 'scope')
    require(acceptance['technical_qc'] == 'GREEN_10BIT_HLG_1200_OF_1200_DECODED', 'qc')
    require(acceptance['gemini_independent_review'] == 'COMPLETED_NO_CREATIVE_WINNER', 'gemini')
    require(acceptance['shared_drive_persistence'] == 'GREEN_EXACT_SHA_READBACK', 'persistence')
    require(acceptance['measurements'] == 'COMPARATIVE_DISPLAY_DECODED_PROXY_NOT_CALIBRATED_HDR_SCOPES', 'measurement truth')
    require(all(acceptance['governance'][k] is False for k in ('final_color_approved','full_master_render_authorized','production_deployment_authorized','publication_authorized')), 'authority')
    reduced = derive(ledger, keyring={}); require(reduced['state_version'] == 22, 'reducer')
    state = json.loads(parent); before = copy.deepcopy(state['authorizations'])
    state.update(state_version=32, updated_at=event['timestamp'], updated_by='codex',
                 milestone='P0-E4 bounded R1 highlight/background refinement ready for Nitin color review')
    state['p0e4']['v166_r1_highlight_background_refinement'] = copy.deepcopy(payload)
    state['p0e4']['current_color_status'] = STATUS
    state['current_release'].update(status='BLOCKED', publish_ready=False)
    state['state_lineage'] = dict(parent_version=31, parent_sha256=PARENT_SHA,
        engineering_ledger_head_hash=reduced['ledger_head_hash'], engineering_transition_count=22)
    state['provenance'].append(dict(phase='P0-E4', status=STATUS, evidence_refs=copy.deepcopy(payload['evidence_refs'])))
    require(state['authorizations'] == before, 'authority mutated')
    require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False, 'gate')
    require(state['production_state']['first_real_poster'] == 'PAUSED_BY_NITIN', 'poster')
    return state


def main():
    acceptance_ref = str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT))
    excluded = {'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_6.json','SHA256SUMS.txt'}
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded)
    payload = {'status':STATUS, 'acceptance_ref':acceptance_ref,
               'evidence_refs':[{'uri':str(p.relative_to(ROOT)), 'sha256':digest(p.read_bytes())} for p in files]}
    path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists(): persist(path, PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all()) == 21:
        ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T11:19:15Z','codex',inputs=payload))
    else: require(ledger.read_all()[-1]['inputs'] == payload, 'immutable event conflict')
    raw=bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT)))
    require(raw == bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT))), 'replay')
    persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_6.json',raw)
    print(json.dumps({'state_version':32,'status':STATUS,'deterministic_replay':True}))


if __name__ == '__main__': main()
