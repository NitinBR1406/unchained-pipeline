import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import project_v16 as p
from canonical.factory_acceptance import verify
from integration.contracts import file_resolver
from control_plane.ledger import EventLedger
import handoff as h
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'p0e4/evidence/factory_v16'
class Projection(unittest.TestCase):
 def test_actual_external_chain_and_corruption(self):
  refs=json.loads((OUT/'INTEGRATION_REFS.json').read_bytes());resolve=file_resolver(ROOT)
  self.assertEqual(verify(refs,resolve),json.loads((OUT/'INTEGRATION_VALIDATION.json').read_bytes()))
  for key in refs:
   bad=copy.deepcopy(refs);bad[key]['sha256']='0'*64
   with self.subTest(key=key),self.assertRaises(ValueError):verify(bad,resolve)
 def test_replay_and_human_gate_preservation(self):
  a=json.loads((ROOT/'p0e4/evidence/wake_dispatch_v155/ACCEPTANCE.json').read_bytes())
  a.update(status='FACTORY_OFFLINE_INTEGRATION_ACCEPTED_LIVE_RENDER_BLOCKED',factory_refs=json.loads((OUT/'INTEGRATION_REFS.json').read_bytes()),factory_validation=json.loads((OUT/'INTEGRATION_VALIDATION.json').read_bytes()))
  for escalation in (False,True):
   a['publication_authorized']=escalation
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(path));payload=dict(tested_sha='a'*40,ingested_at='2026-09-19T11:40:00Z',acceptance=a,evidence_refs=list(a['factory_refs'].values()))
    ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
    if escalation:
     with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),file_resolver(ROOT))
    else:
     state=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),file_resolver(ROOT));self.assertEqual(state['state_version'],26)
     self.assertEqual(state,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),file_resolver(ROOT)))
     for key in ('authorizations','production_state','current_release'):self.assertEqual(state[key],json.loads(p.PARENT.read_bytes())[key])
if __name__=='__main__':unittest.main()
