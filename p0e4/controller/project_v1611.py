"""Project V05 soft-skin-lighting review to V16.11."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT;PARENT=ROOT/'p0e4/evidence/v04_natural_skin_v01_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_10.json';PARENT_SHA='42b6f4038fcc83382246e1cf14b2891619ebc21bc26523335c64c02a74cc0608';PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl';OUT=ROOT/'p0e4/evidence/v05_soft_skin_lighting_v01_execution';EVENT_ID='p0e4-v1611-v05-soft-skin-lighting-review-ready';STATUS='WAITING_FOR_NITIN_V05_SOFT_SKIN_LIGHTING_COLOR_REVIEW'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift');events=ledger.read_all();require(len(events)==27,'event count');e=events[-1];require(e['event_id']==EVENT_ID,'identity');payload=e['inputs'];verify_refs(payload['evidence_refs'],resolver);a=json.loads(resolver(payload['acceptance_ref']));require(a['technical_qc']=='GREEN_10BIT_HLG_3720_OF_3720_DECODED','decode');require(a['gemini_independent_review']=='PASS_FOR_NITIN_V05_COLOR_REVIEW_WITH_RESPONSE_FORMAT_ANOMALY','gemini');require(a['shared_drive_persistence']=='GREEN_EXACT_SHA_READBACK','persistence');require(a['full_master_rendered'] is False and a['beat_effects_started'] is False,'scope')
 reduced=derive(ledger,keyring={});require(reduced['state_version']==27,'reducer');s=json.loads(parent);before=copy.deepcopy(s['authorizations']);s.update(state_version=37,updated_at=e['timestamp'],updated_by='codex',milestone='P0-E4 V05 soft-skin-lighting HLG comparison ready for Nitin');s['p0e4']['v1611_v05_soft_skin_lighting_review']=copy.deepcopy(payload);s['p0e4']['current_color_status']=STATUS;s['current_release'].update(status='BLOCKED',publish_ready=False);s['state_lineage']=dict(parent_version=36,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=27);s['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])));require(s['authorizations']==before,'authority');require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False,'gates');return s
def main():
 excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_11.json','SHA256SUMS.txt'};files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT)),'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]};path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 l=EventLedger(str(path))
 if len(l.read_all())==26:l.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T16:45:00Z','codex',inputs=payload))
 else:require(l.read_all()[-1]['inputs']==payload,'conflict')
 raw=bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_11.json',raw);print(json.dumps({'state_version':37,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
