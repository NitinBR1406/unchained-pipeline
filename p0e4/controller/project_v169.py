"""Project the V03 longer real-EDL color consistency review to V16.9."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/r1_highlight_refinement_v03_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_8.json'
PARENT_SHA='86342dbd4063af9aa4843a7ff66021f53a28e3064940ca1c46beefbb1b2c7e42'
PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
OUT=ROOT/'p0e4/evidence/v03_color_consistency_v01_execution'
EVENT_ID='p0e4-v169-v03-color-consistency-review-ready'
STATUS='WAITING_FOR_NITIN_V03_COLOR_CONSISTENCY_REVIEW'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift')
 events=ledger.read_all();require(len(events)==25,'event count');event=events[-1];require(event['event_id']==EVENT_ID and event['agent']=='codex','event identity')
 payload=event['inputs'];require(payload['status']==STATUS,'status');verify_refs(payload['evidence_refs'],resolver);a=json.loads(resolver(payload['acceptance_ref']))
 require(a['status']==STATUS and a['full_master_rendered'] is False,'scope');require(a['authoritative_review_sha256']=='6abcf3378ecce5df960c3d88df6bf0a1429e185996f321ecb37a0c7c381ca69b','review')
 require(a['gemini_independent_review'].startswith('PASS_FOR_NITIN'),'gemini');require(a['shared_drive_persistence']=='GREEN_EXACT_SHA_READBACK','persistence')
 require(all(a['governance'][k] is False for k in ('final_color_approved','full_master_render_authorized','production_deployment_authorized','publication_authorized')),'authority')
 reduced=derive(ledger,keyring={});require(reduced['state_version']==25,'reducer');state=json.loads(parent);before=copy.deepcopy(state['authorizations'])
 state.update(state_version=35,updated_at=event['timestamp'],updated_by='codex',milestone='P0-E4 V03 longer real-EDL color consistency review ready for Nitin')
 state['p0e4']['v169_v03_color_consistency_review']=copy.deepcopy(payload);state['p0e4']['current_color_status']=STATUS;state['current_release'].update(status='BLOCKED',publish_ready=False)
 state['state_lineage']=dict(parent_version=34,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=25)
 state['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])))
 require(state['authorizations']==before,'authority mutated');require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False,'gate');require(state['production_state']['first_real_poster']=='PAUSED_BY_NITIN','poster');return state
def main():
 acceptance_ref=str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT));excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_9.json','SHA256SUMS.txt'}
 files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':acceptance_ref,'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]}
 path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 ledger=EventLedger(str(path))
 if len(ledger.read_all())==24:ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T14:21:01Z','codex',inputs=payload))
 else:require(ledger.read_all()[-1]['inputs']==payload,'immutable event conflict')
 raw=bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_9.json',raw);print(json.dumps({'state_version':35,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
