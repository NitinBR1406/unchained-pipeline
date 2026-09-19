import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller import project_v154 as p
from canonical.consumer import compile_preflight
from canonical.dispatch_receipt import verify_external,ARCHIVE_SHA,REQUEST_ID
from integration.contracts import canonical,digest
from control_plane.ledger import EventLedger
ROOT=Path(__file__).resolve().parents[2]
class Projection(unittest.TestCase):
 def test_replay_and_scope_escalation_rejected(self):
  a=json.loads((ROOT/'p0e4/evidence/wake_v153/ACCEPTANCE.json').read_bytes())
  a['status']='CLAUDE_SYNTHETIC_PREFLIGHT_ACCEPTED_PRODUCTION_BLOCKED'
  s=json.loads((ROOT/'p0e4/evidence/canonical_v15/SHADOW_FIXTURE.json').read_bytes())
  blobs={}
  def resolve(u):return blobs[u] if u in blobs else (ROOT/u).read_bytes()
  pre=compile_preflight(s['sidecar'],s['creative_package'],resolve)
  result=dict(request_id=REQUEST_ID,input_archive_sha256=ARCHIVE_SHA,status='PASS',jobs=[dict(package_id=j['package_id'],groups=j['groups']) for j in pre['jobs']])
  decision=dict(archive_sha256=ARCHIVE_SHA,transfer_authorized=True,destination='Claude Desktop Dispatch',allowed_purpose='NON_PUBLISHING_SYNTHETIC_P0E4_PREFLIGHT',production_deployment_authorized=False,make_sheet_mutation_authorized=False,cutover_authorized=False,publication_authorized=False,rights_clearance_granted=False,final_audio_binding_granted=False)
  archive=(ROOT/'p0e4/evidence/canonical_v151/CANONICAL_SHADOW_CLOSURE.zip').read_bytes()
  blobs.update(result=canonical(result),decision=canonical(decision),archive=archive)
  a['dispatch_refs']={k:dict(uri=k,sha256=digest(blobs[k])) for k in blobs}
  a['external_validation']=verify_external(result,s['sidecar'],s['creative_package'],resolve,archive,decision)
  for escalation in (False,True):
   a['publication_authorized']=escalation
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(path))
    inputs=dict(tested_sha='a'*40,ingested_at='2026-09-19T09:30:00Z',acceptance=a,evidence_refs=list(a['dispatch_refs'].values()))
    ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',inputs['ingested_at'],'codex',inputs=inputs))
    if escalation:
     with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve)
    else:
     state=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve);self.assertEqual(state['state_version'],24)
     self.assertEqual(state,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve))
     for k in ('authorizations','production_state','current_release'):self.assertEqual(state[k],json.loads(p.PARENT.read_bytes())[k])
if __name__=='__main__':unittest.main()
