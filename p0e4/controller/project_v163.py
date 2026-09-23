"""Additive V16.3 evidence projection: bounded installed smoke, no human grant."""
import copy,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from integration.contracts import canonical,digest,require,keys,verify_refs,file_resolver,timestamp
from integration.project_v09 import bytes_json,persist
from control_plane.ledger import EventLedger
from control_loop.state_model import derive
ROOT=h.ROOT
PARENT=ROOT/'p0e4/evidence/resolve_max_v162_acceptance/UNCHAINED_MASTER_PROJECT_STATE_V16_2.json'
PARENT_SHA='a41764d6955f5153ba9cd3d4033c5521eb41037a9c801e53469135d1cfdde2eb'
PREFIX=PARENT.parent/'ENGINEERING_EVENT_LEDGER.jsonl'
EVENT_ID='p0e4-v163-installed-resolve-synthetic-acceptance'
STATUS='INSTALLED_SYNTHETIC_CAPABILITIES_ACCEPTED_PRODUCTION_BLOCKED'
CATEGORIES={'API_SCRIPTABLE','FUSION_SCRIPTABLE','EXTERNAL_INTELLIGENCE_REQUIRED','GUI_AUTOMATION_ONLY','UNSUPPORTED_FAIL_CLOSED'}

def validate(a,resolver):
    keys(a,'tested_sha status refs production_deployment_authorized publication_authorized first_real_poster')
    require(re.fullmatch('[a-f0-9]{40}',a['tested_sha']) is not None,'tested SHA')
    require(a['status']==STATUS,'acceptance status')
    require(a['production_deployment_authorized'] is False and a['publication_authorized'] is False,'authority escalation')
    require(a['first_real_poster']=='PAUSED_BY_NITIN','poster gate')
    keys(a['refs'],'local replay readback matrix regression captions')
    verify_refs(list(a['refs'].values()),resolver)
    def load(k):return json.loads(resolver(a['refs'][k]['uri']))
    for k in ('local','replay'):
        r=load(k)
        require(r['status']=='PASS_SYNTHETIC_BOUNDED_CAPABILITIES','local failure')
        require(r['installation']==dict(product='DaVinci Resolve Studio',version=[21,1,0,17,'']),'installed version')
        require(r['render']['status']['JobStatus']=='Complete' and r['render']['bytes']>0,'render incomplete')
        require(r['render_job_removed'] is True and r['closed'] is True and r['original_project_restored'] is True,'cleanup failure')
        require(r['nitin_audio_source_binding_inferred'] is False and r['production_deployment_authorized'] is False and r['publication_authorized'] is False,'runtime authority')
    b=load('readback')
    require(b['full_decode_pass'] is True and b['video_essence_equal'] is True and b['audio_essence_equal'] is True,'replay mismatch')
    require(b['video_frames']==100 and b['audio_samples_per_channel']==192000,'readback extent')
    require(b['outputs'][0]['sha256']==load('local')['render']['sha256'] and b['outputs'][1]['sha256']==load('replay')['render']['sha256'],'output binding')
    rows=load('matrix')['capabilities'];names=[x['capability'] for x in rows]
    require(len(names)==len(set(names)) and len(rows)>=30,'capability coverage')
    require(all(x['classification'] in CATEGORIES and x['proven_scope_or_limit'] and x['evidence'] for x in rows),'capability classification')
    require(load('captions')['captions']==[dict(text='UNCHAINED SYNTHETIC',start=0,end=50),dict(text='CAPTION ACCEPTANCE',start=50,end=100)],'caption timing')
    reg=load('regression')
    require(reg['tested_sha']==a['tested_sha'] and reg['passed']==reg['total'] and reg['total']>=73 and reg['tracked_worktree_clean'] is True,'regression invalid')
    require(bool(reg['prior_manifests']) and all(x['pass'] is True for x in reg['prior_manifests']),'manifest mismatch')

def project(parent,ledger,resolver):
    require(digest(parent)==PARENT_SHA,'V16.2 parent drift')
    require(Path(ledger.path).read_bytes().startswith(PREFIX.read_bytes()),'ledger prefix drift')
    events=ledger.read_all();require(len(events)==19 and all(e['event_type']=='EVIDENCE_REGISTERED' for e in events),'evidence events only')
    e=events[-1];require(e['event_id']==EVENT_ID and e['agent']=='codex','event identity')
    payload=e['inputs'];keys(payload,'ingested_at evidence_refs acceptance');timestamp(payload['ingested_at']);verify_refs(payload['evidence_refs'],resolver);validate(payload['acceptance'],resolver)
    reduced=derive(ledger,keyring={});require(reduced['state_version']==19,'reducer version')
    state=json.loads(parent);before=copy.deepcopy(state['authorizations'])
    state['state_version']=29;state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
    state['milestone']='P0-E4 installed Resolve synthetic capabilities accepted; real production finishing remains blocked'
    state['p0e4']['v163_installed_resolve']=copy.deepcopy(payload)
    state['state_lineage']=dict(parent_version=28,parent_sha256=PARENT_SHA,engineering_ledger_head_hash=reduced['ledger_head_hash'],engineering_transition_count=19)
    state['provenance'].append(dict(phase='P0-E4',status=STATUS,tested_sha=payload['acceptance']['tested_sha'],evidence_refs=copy.deepcopy(payload['evidence_refs'])))
    require(state['authorizations']==before and state['authorizations']['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and state['authorizations']['PUBLICATION_AUTHORIZED'] is False,'governance drift')
    return state

def main(out,at):
    timestamp(at);out=Path(out).resolve();require(out.is_relative_to(ROOT/'p0e4/evidence'),'output scope')
    a=json.loads((out/'ACCEPTANCE.json').read_bytes());validate(a,file_resolver(ROOT))
    exclude={'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_3.json','SHA256SUMS.txt'}
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name not in exclude and not p.name.endswith('.lock'))
    payload=dict(ingested_at=at,acceptance=a,evidence_refs=[dict(uri=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for p in files])
    path=out/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists():persist(path,PREFIX.read_bytes())
    ledger=EventLedger(str(path))
    if len(ledger.read_all())==18:ledger.append(h.make_event(EVENT_ID,'EVIDENCE_REGISTERED',at,'codex',inputs=payload))
    else:require(ledger.read_all()[-1]['inputs']==payload,'immutable acceptance conflict')
    raw=bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT)))
    require(raw==bytes_json(project(PARENT.read_bytes(),ledger,file_resolver(ROOT))),'replay differs')
    persist(out/'UNCHAINED_MASTER_PROJECT_STATE_V16_3.json',raw)
