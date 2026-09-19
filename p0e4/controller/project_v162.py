"""Additive evidence transition for master-finishing design; no human grant."""
import copy,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from integration.contracts import canonical,digest,require,keys,verify_refs,file_resolver,timestamp
from integration.project_v09 import bytes_json,persist
from resolve.adapter import ResolveAdapter
from catalog.review import technical_review
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/resolve_catalog_v161_accepted/UNCHAINED_MASTER_PROJECT_STATE_V16_1.json'
PARENT_SHA='ffaa9110369773cb8e50d751f236a49b7abf4448eb9bdf33515d04daf517967e'
PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v162-master-finishing-capabilities'

def validate(a,resolver):
 keys(a,'tested_sha status refs resolve_execution_proven production_deployment_authorized publication_authorized first_real_poster')
 require(re.fullmatch('[a-f0-9]{40}',a['tested_sha']) is not None,'tested SHA')
 require(a['status']=='MASTER_FINISHING_DESIGN_ACCEPTED_EXECUTION_BLOCKED','acceptance status')
 for k in ('resolve_execution_proven','production_deployment_authorized','publication_authorized'):require(a[k] is False,'authority escalation')
 require(a['first_real_poster']=='PAUSED_BY_NITIN','poster gate')
 keys(a['refs'],'fixture plan inventory catalog_review regression')
 verify_refs(list(a['refs'].values()),resolver)
 def load(k):return json.loads(resolver(a['refs'][k]['uri']))
 f=load('fixture');blobs={k:v.encode() for k,v in f['blobs_utf8'].items()}
 expected=ResolveAdapter().compile(f['canonical'],f['creative'],f['operations'],f['finishing'],blobs.__getitem__)
 require(canonical(expected)==canonical(load('plan')),'finishing replay drift')
 require(technical_review(load('inventory'))==load('catalog_review'),'catalog review drift')
 r=load('regression');require(r['tested_sha']==a['tested_sha'] and r['passed']==r['total'] and r['total']>0 and r['tracked_worktree_clean'] is True,'regression invalid')
 require(bool(r['prior_manifests']) and all(x['pass'] is True for x in r['prior_manifests']),'manifest mismatch')

def project(parent,ledger,resolver):
 require(digest(parent)==PARENT_SHA,'V16.1 parent drift')
 require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift')
 events=ledger.read_all();require(len(events)==18 and all(e['event_type']=='EVIDENCE_REGISTERED' for e in events),'evidence events only')
 e=events[-1];require(e['event_id']==EVENT_ID and e['agent']=='codex','event identity')
 payload=e['inputs'];keys(payload,'ingested_at evidence_refs acceptance');timestamp(payload['ingested_at']);verify_refs(payload['evidence_refs'],resolver);validate(payload['acceptance'],resolver)
 reduced=derive(ledger,keyring={});require(reduced['state_version']==18,'reducer version')
 state=json.loads(parent);state['state_version']=10+reduced['state_version'];state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
 state['milestone']='P0-E4 master-finishing capability design accepted; installed execution remains unproven'
 state['p0e4']['v162_master_finishing']=copy.deepcopy(payload)
 state['state_lineage']=dict(parent_version=27,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=18)
 state['provenance'].append(dict(phase='P0-E4',status=payload['acceptance']['status'],tested_sha=payload['acceptance']['tested_sha'],evidence_refs=copy.deepcopy(payload['evidence_refs'])))
 return state

def main(out,at):
 timestamp(at);out=Path(out).resolve();require(out.is_relative_to(ROOT/'p0e4/evidence'),'output scope')
 a=json.loads((out/'ACCEPTANCE.json').read_bytes());validate(a,file_resolver(ROOT))
 exclude={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_2.json','SHA256SUMS.txt'}
 files=sorted(p for p in out.rglob('*') if p.is_file() and p.name not in exclude and not p.name.endswith('.lock'))
 payload=dict(ingested_at=at,acceptance=a,evidence_refs=[dict(uri=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for p in files])
 path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 ledger=EventLedger(str(path))
 if len(ledger.read_all())==17:ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
 else:require(ledger.read_all()[-1]['inputs']==payload,'immutable acceptance conflict')
 raw=bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT)))
 require(raw==bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT))),'replay differs')
 persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V16_2.json',raw)
