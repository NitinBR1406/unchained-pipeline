"""Evidence-only V16.1 projection; preserve frozen reducer and human gates."""
import argparse,copy,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from integration.contracts import canonical,digest,require,keys,timestamp,verify_refs,file_resolver
from integration.project_v09 import persist,bytes_json
from catalog.engine import compile_catalog
from resolve.plan import verify as verify_plan
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/factory_v16/UNCHAINED_MASTER_PROJECT_STATE_V16.json'
PARENT_SHA='a466c8837812f2a17a1f4e39cf5f2669ca9a0046d299570578d2b64e9dfef741'
PREFIX=ROOT/'p0e4/evidence/factory_v16/ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v161-resolve-catalog-bootstrap'
STATUS='RESOLVE_PREINSTALL_AND_CATALOG_METADATA_ACCEPTED'


def validate_acceptance(a,resolver):
 keys(a,'status tested_sha deterministic_replay production_e2e_status blocked_tasks resolve_execution_proven live_cutover_authorized always_on_dispatcher_proven production_deployment_authorized publication_authorized first_real_poster catalog_refs resolve_refs regression_ref')
 require(a['status']==STATUS and a['deterministic_replay'] is True,'scope acceptance')
 require(type(a['tested_sha']) is str and re.fullmatch('[0-9a-f]{40}',a['tested_sha']),'tested code SHA')
 for key in ('resolve_execution_proven','live_cutover_authorized','always_on_dispatcher_proven','production_deployment_authorized','publication_authorized'):require(a[key] is False,'unproven capability or authority escalation')
 require(a['first_real_poster']=='PAUSED_BY_NITIN' and a['production_e2e_status']=='BLOCKED_NOT_GREEN','production gate')
 require(type(a['blocked_tasks']) is list and bool(a['blocked_tasks']),'explicit remaining gates required')
 keys(a['catalog_refs'],'inventory outputs');keys(a['resolve_refs'],'input plan')
 refs=list(a['catalog_refs'].values())+list(a['resolve_refs'].values())+[a['regression_ref']]
 verify_refs(refs,resolver)
 def load(ref):return json.loads(resolver(ref['uri']))
 regression=load(a['regression_ref'])
 require(type(regression['passed']) is int and regression['passed']>0 and regression['passed']==regression['total'] and regression['tracked_worktree_clean'] is True,'regression/commit not clean')
 require(regression['tested_sha']==a['tested_sha'],'tested SHA differs')
 require(bool(regression['prior_manifests']) and all(x['pass'] is True for x in regression['prior_manifests']),'manifest verification missing/failed')
 expected=compile_catalog(load(a['catalog_refs']['inventory']))
 require(canonical(expected)==canonical(load(a['catalog_refs']['outputs'])),'catalog replay drift')
 source=load(a['resolve_refs']['input']);blobs={k:v.encode() for k,v in source['blobs_utf8'].items()}
 verify_plan(load(a['resolve_refs']['plan']),source['canonical'],source['creative'],blobs.__getitem__)
 return True


def project(parent,ledger,prefix,resolver):
 require(digest(parent)==PARENT_SHA,'V16 parent hash mismatch')
 require(prefix==PREFIX.read_bytes(),'unrecognized ledger prefix')
 require(Path(ledger.path).read_bytes().startswith(prefix),'accepted prefix changed')
 records=ledger.read_all()
 require(len(records)==17 and all(r['event_type']=='EVIDENCE_REGISTERED' for r in records),'17 evidence events required')
 require(records[-1]['event_id']==EVENT_ID and records[-1]['agent']=='codex','event identity')
 payload=records[-1]['inputs'];keys(payload,'tested_sha ingested_at evidence_refs acceptance')
 timestamp(payload['ingested_at']);verify_refs(payload['evidence_refs'],resolver)
 a=payload['acceptance'];require(payload['tested_sha']==a['tested_sha'],'payload code SHA drift');validate_acceptance(a,resolver)
 reducer=derive(ledger,keyring={});require(reducer['state_version']==17,'reducer transition count')
 state=json.loads(parent)
 state['state_version']=27;state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
 state['milestone']='P0-E4 Resolve pre-install contracts and read-only catalog metadata accepted; execution remains gated'
 state['p0e4']['v161_resolve_catalog']=copy.deepcopy(payload);state['p0e4']['verdict']='BLOCKED_NOT_GREEN'
 state['state_lineage']=dict(parent_version=26,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reducer['ledger_head_hash'],engineering_transition_count=17)
 state['provenance'].append(dict(phase='P0-E4',status=STATUS,tested_sha=payload['tested_sha'],evidence_refs=copy.deepcopy(payload['evidence_refs'])))
 for k in ('authorizations','production_state','current_release'):require(state[k]==json.loads(parent)[k],'parent authority changed')
 return state


def main(directory,at):
 timestamp(at) # Reject invalid event time before any append-only ledger mutation.
 out=Path(directory).resolve();require(out.is_relative_to(ROOT/'p0e4/evidence'),'evidence output scope')
 a=json.loads((out/'ACCEPTANCE.json').read_bytes());r=json.loads((out/'REGRESSION.json').read_bytes())
 require(a['regression_ref']=={'uri':str((out/'REGRESSION.json').relative_to(ROOT)),'sha256':digest((out/'REGRESSION.json').read_bytes())},'regression ref location')
 validate_acceptance(a,file_resolver(ROOT))
 files=sorted(p for p in out.rglob('*') if p.is_file() and p.name not in ('ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_1.json','SHA256SUMS.txt','PERSISTENCE_RECEIPTS.json') and not p.name.endswith('.lock'))
 payload=dict(tested_sha=a['tested_sha'],ingested_at=at,acceptance=a,evidence_refs=[dict(uri=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for p in files])
 path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
 if not path.exists():persist(path,PREFIX.read_bytes())
 ledger=EventLedger(str(path))
 if len(ledger.read_all())==16:ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
 else:require(ledger.read_all()[-1]['inputs']==payload,'immutable V16.1 conflict')
 state=project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT));data=bytes_json(state)
 require(data==bytes_json(project(PARENT.read_bytes(),ledger,PREFIX.read_bytes(),file_resolver(ROOT))),'projection replay drift')
 persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V16_1.json',data)
 print(json.dumps(dict(state_version=state['state_version'],replay=True,scope_status=STATUS)))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--at',required=True);args=parser.parse_args();main(args.directory,args.at)
