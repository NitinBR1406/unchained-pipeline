"""Project kick/snare detector audit and fail-closed analysis to V16.14."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
from integration.contracts import digest,require,verify_refs,file_resolver
from integration.project_v09 import bytes_json,persist
ROOT=h.ROOT;PARENT=ROOT/'p0e4/evidence/v06_caption_beat_preview_v01_execution/UNCHAINED_MASTER_PROJECT_STATE_V16_13.json';PARENT_SHA='8bc86de33554e0a80f7e16c077b8d456fbba26c803589447909b987fd8618027';PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl';OUT=ROOT/'p0e4/evidence/kick_snare_discovery_v01_execution';EVENT_ID='p0e4-v1614-kick-snare-analysis';STATUS='WAITING_FOR_NITIN_MAC_UNLOCK_FOR_GEMINI_KICK_SNARE_VALIDATION'
def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'parent drift');require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift');events=ledger.read_all();require(len(events)==30,'event count');e=events[-1];require(e['event_id']==EVENT_ID,'identity');payload=e['inputs'];verify_refs(payload['evidence_refs'],resolver);a=json.loads(resolver(payload['acceptance_ref']));require(a['master_sha_verified'] is True and a['analysis_reproducible'] is True,'analysis');require(a['instrument_labels_accepted_for_automation'] is False,'classification gate');require(a['gemini_independent_review']=='BLOCKED_MAC_LOCKED','gemini');require(a['effect_policy_selected'] is False and a['effect_rendered'] is False and a['full_master_rendered'] is False,'scope');reduced=derive(ledger,keyring={});require(reduced['state_version']==30,'reducer');s=json.loads(parent);before=copy.deepcopy(s['authorizations']);s.update(state_version=40,updated_at=e['timestamp'],updated_by='codex',milestone='P0-E4 kick/snare detector audit and mixed-master analysis ready; Gemini audio validation blocked by Mac lock');s['p0e4']['v1614_kick_snare_discovery']=copy.deepcopy(payload);s['p0e4']['current_color_status']=STATUS;s['current_release'].update(status='BLOCKED',publish_ready=False);s['state_lineage']=dict(parent_version=39,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=30);s['provenance'].append(dict(phase='P0-E4',status=STATUS,evidence_refs=copy.deepcopy(payload['evidence_refs'])));require(s['authorizations']==before,'authority');require(before['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and before['PUBLICATION_AUTHORIZED'] is False,'gates');return s
def main():
 excluded={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_14.json','SHA256SUMS.txt'};files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded);payload={'status':STATUS,'acceptance_ref':str((OUT/'ACCEPTANCE_V01.json').relative_to(ROOT)),'evidence_refs':[{'uri':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())} for p in files]};path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 l=EventLedger(str(path))
 if len(l.read_all())==29:l.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T20:15:00Z','codex',inputs=payload))
 else:require(l.read_all()[-1]['inputs']==payload,'conflict')
 raw=bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT)));require(raw==bytes_json(project(PARENT.read_bytes(),l,file_resolver(ROOT))),'replay');persist(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_14.json',raw);print(json.dumps({'state_version':40,'status':STATUS,'deterministic_replay':True}))
if __name__=='__main__':main()
