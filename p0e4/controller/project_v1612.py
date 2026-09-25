"""Project V06 softness and caption preparation to V16.12."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT;PARENT=ROOT/'p0e4/evidence/v05_soft_skin_lighting_v01_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_11.json';PARENT_SHA='30b322858eed29f874489ed3e882882e7c6f921234270e0d173e01b9be47bcc2';PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl';OUT=ROOT/'p0e4/evidence/v06_softness_caption_prep_v01_execution';EVENT_ID='p0e4-v1612-v06-softness-caption-prep-ready';STATUS='WAITING_FOR_NITIN_V06_COLOR_REVIEW'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift');events=ledger.read_all();require(len(events)==28,'event count');e=events[-1];require(e['event_id']==EVENT_ID,'identity');payload=e['inputs'];verify_refs(payload['evidence_refs'],resolver);a=json.loads(resolver(payload['acceptance_ref']));require(a['technical_qc']=='GREEN_10BIT_HLG_3720_OF_3720_DECODED','decode');require(a['gemini_independent_review']=='PASS_FOR_NITIN_V06_COLOR_REVIEW','gemini');require(a['caption_variants']=='PREPARED_NOT_RENDERED','captions');require(a['caption_preview_rendered'] is False and a['beat_preview_rendered'] is False and a['full_master_rendered'] is False,'scope')
 reduced=derive(ledger,keyring={});require(reduced['state_version']==28,'reducer');s=json.loads(parent);before=copy.deepcopy(s['authorizations']);s.update(state_version=38,updated_at=e['timestamp'],updated_by='codex',milestone='P0-E4 V06 softer HLG comparison and caption drafts ready for Nitin');s['p0e4']['v1612_v06_softness_caption_prep']=copy.deepcopy(payload);s['p0e4']['current_color_status']=STATUS;s['current_release'].update(status='BLOCKED',publish_ready=False);s['state_lineage']=dict(parent_version=37,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=28);s['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])));require(s['authorizations']==before,'authority');require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False,'gates');return s
def main():
 excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_12.json','SHA256SUMS.txt'};files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT)),'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]};path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 l=EventLedger(str(path))
 if len(l.read_all())==27:l.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T18:15:00Z','codex',inputs=payload))
 else:require(l.read_all()[-1]['inputs']==payload,'conflict')
 raw=bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_12.json',raw);print(json.dumps({'state_version':38,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
