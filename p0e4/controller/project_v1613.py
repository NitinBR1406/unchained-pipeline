"""Project V06 caption/beat private preview evidence to V16.13."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/v06_softness_caption_prep_v01_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_12.json'
PARENT_SHA='1eb3e09bb4a4c1127a637f26fee435a0c991840573f20b9983ee30b56d8a3605'
PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
OUT=ROOT/'p0e4/evidence/v06_caption_beat_preview_v01_execution'
EVENT_ID='p0e4-v1613-v06-caption-beat-preview-ready'
STATUS='WAITING_FOR_NITIN_V06_CAPTION_BEAT_PREVIEW_REVIEW'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift')
 events=ledger.read_all();require(len(events)==29,'event count');e=events[-1];require(e['event_id']==EVENT_ID,'identity');payload=e['inputs'];verify_refs(payload['evidence_refs'],resolver)
 a=json.loads(resolver(payload['acceptance_ref']));require(a['technical_qc']=='GREEN_10BIT_HLG_FULL_DECODE','decode');require(a['gemini_independent_review']=='PASS_FOR_NITIN_PREVIEW_REVIEW','gemini');require(a['variants_rendered']==['A','B'],'variants');require(a['variant_c']=='HOLD_PENDING_AUTHORITATIVE_LYRIC_TEXT_AND_WORD_TIMING','C hold');require(a['full_master_rendered'] is False and a['full_song_color_approved'] is False,'scope')
 reduced=derive(ledger,keyring={});require(reduced['state_version']==29,'reducer');s=json.loads(parent);before=copy.deepcopy(s['authorizations']);s.update(state_version=39,updated_at=e['timestamp'],updated_by='codex',milestone='P0-E4 V06 private A/B caption and beat preview ready for Nitin')
 s['p0e4']['v1613_v06_caption_beat_preview']=copy.deepcopy(payload);s['p0e4']['current_color_status']=STATUS;s['current_release'].update(status='BLOCKED',publish_ready=False);s['state_lineage']=dict(parent_version=38,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=29);s['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])));require(s['authorizations']==before,'authority');require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False,'gates');return s
def main():
 excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_13.json','SHA256SUMS.txt'};files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT)),'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]};path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 l=EventLedger(str(path))
 if len(l.read_all())==28:l.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T19:25:00Z','codex',inputs=payload))
 else:require(l.read_all()[-1]['inputs']==payload,'conflict')
 raw=bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_13.json',raw);print(json.dumps({'state_version':39,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
