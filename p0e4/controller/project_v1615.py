"""Project prepared native Resolve rhythm study blocker to V16.15."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT;PARENT=ROOT/'p0e4/evidence/kick_snare_discovery_v01_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_14.json';PARENT_SHA='39c93122ced4e4592d6ea2068796fdae7709138cf2f01155a94a4ec30e5b2d3c';PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl';OUT=ROOT/'p0e4/evidence/resolve_native_rhythm_study_v01_execution';EVENT_ID='p0e4-v1615-resolve-native-rhythm-prepared';STATUS='WAITING_FOR_NITIN_MAC_UNLOCK_FOR_RESOLVE_NATIVE_RHYTHM_STUDY'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift');events=ledger.read_all();require(len(events)==31,'event count');e=events[-1];require(e['event_id']==EVENT_ID,'identity');payload=e['inputs'];verify_refs(payload['evidence_refs'],resolver);a=json.loads(resolver(payload['acceptance_ref']));require(a['exact_audio_bound'] and a['native_feature_present'],'prep');require(not a['native_analysis_completed'] and not a['gemini_review_completed'],'blocked');require(not a['effect_rendered'] and not a['full_master_rendered'],'scope');reduced=derive(ledger,keyring={});require(reduced['state_version']==31,'reducer');s=json.loads(parent);before=copy.deepcopy(s['authorizations']);s.update(state_version=41,updated_at=e['timestamp'],updated_by='codex',milestone='P0-E4 native Resolve rhythm study prepared; UI execution blocked by Mac lock');s['p0e4']['v1615_resolve_native_rhythm_study']=copy.deepcopy(payload);s['p0e4']['current_color_status']=STATUS;s['current_release'].update(status='BLOCKED',publish_ready=False);s['state_lineage']=dict(parent_version=40,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=31);s['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])));require(s['authorizations']==before,'authority');return s
def main():
 excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_15.json','SHA256SUMS.txt'};files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT)),'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]};path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 l=EventLedger(str(path))
 if len(l.read_all())==30:l.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T20:45:00Z','codex',inputs=payload))
 else:require(l.read_all()[-1]['inputs']==payload,'conflict')
 raw=bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_15.json',raw);print(json.dumps({'state_version':41,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
