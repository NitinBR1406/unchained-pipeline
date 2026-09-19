import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller.wake_chain import verify_chain
from controller import project_v155 as p
from integration.contracts import digest
from control_plane.ledger import EventLedger
import handoff as h
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'p0e4/evidence/wake_dispatch_v155'
def resolve(u):return (ROOT/u).read_bytes()
class WakeChain(unittest.TestCase):
 def setUp(self):self.receipt=json.loads((OUT/'WAKE_DISPATCH_RECEIPT.json').read_bytes())
 def test_real_chain(self):
  result=verify_chain(self.receipt,resolve)
  self.assertEqual(result,json.loads((OUT/'CHAIN_VALIDATION.json').read_bytes()))
 def test_reject_wake_scope_and_duplicate_claims(self):
  for key,val in [('trigger','CONFIGURATION_ONLY'),('idle_to_wake_observed',False),('always_on_dispatcher_proven',True),('publication_authorized',True),('restart_dispatches',1),('trigger_at','2099-01-01T00:00:00Z')]:
   bad=copy.deepcopy(self.receipt);bad[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):verify_chain(bad,resolve)
 def test_corrupted_execution_evidence(self):
  bad=copy.deepcopy(self.receipt);bad['refs']['completion']['sha256']='0'*64
  with self.assertRaises(ValueError):verify_chain(bad,resolve)
 def test_schema_rejects_semantic_escalation(self):
  from jsonschema import Draft202012Validator,ValidationError
  schema=json.loads(resolve(self.receipt['refs']['schema']['uri']));v=Draft202012Validator(schema)
  data=json.loads(resolve(self.receipt['refs']['validation']['uri']))
  for key,val in [('publication_authorized',True),('live_make_execution_proven',True),('semantic_drift',True),('groups_per_package',13),('packages','1'),('result_sha256','bad'),('unknown',1)]:
   bad=dict(data);bad[key]=val
   with self.subTest(key=key),self.assertRaises(ValidationError):v.validate(bad)
  for key in schema['required']:
   bad=dict(data);del bad[key]
   with self.assertRaises(ValidationError):v.validate(bad)
 def test_projection_replay_preserves_gates(self):
  a=json.loads(resolve('p0e4/evidence/claude_v154/ACCEPTANCE.json'))
  a.update(status='BOUNDED_WAKE_DISPATCH_ACCEPTED_PRODUCTION_BLOCKED',wake_chain_ref=dict(uri=str((OUT/'WAKE_DISPATCH_RECEIPT.json').relative_to(ROOT)),sha256=digest((OUT/'WAKE_DISPATCH_RECEIPT.json').read_bytes())),wake_chain_validation=verify_chain(self.receipt,resolve))
  for escalation in (False,True):
   a['publication_authorized']=escalation
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(path))
    payload=dict(tested_sha='a'*40,ingested_at='2026-09-19T10:10:00Z',evidence_refs=[a['wake_chain_ref']],acceptance=a)
    ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
    if escalation:
     with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve)
    else:
     state=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve)
     self.assertEqual(state['state_version'],25)
     self.assertEqual(state,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve))
     for k in ('authorizations','production_state','current_release'):self.assertEqual(state[k],json.loads(p.PARENT.read_bytes())[k])
if __name__=='__main__':unittest.main()
