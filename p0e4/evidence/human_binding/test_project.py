import copy,json,tempfile,unittest
from pathlib import Path
import project as p
from control_plane.ledger import EventLedger

class EvidenceBindingTests(unittest.TestCase):
 def setUp(self):
  self.parent=p.PARENT.read_bytes();self.source=(p.OUT/'NITIN_SOURCE_REQUEST.txt').read_bytes()
  packet=json.loads((p.ROOT/'p0e4/evidence/resume/RELEASE_REVIEW_PACKET.json').read_text())
  self.prior=packet['approval_binding_request']['existing_decision'];self.media=packet['approval_binding_request']['candidate_asset']
 def facts(self):return p.facts(self.source,self.parent,self.prior,self.media)
 def ledger(self,path,**overrides):
  path.write_bytes((p.ROOT/'p0e4/evidence/review/ENGINEERING_EVENT_LEDGER.jsonl').read_bytes())
  ledger=EventLedger(str(path))
  payload=dict(human_evidence=self.facts(),evidence_refs=[],tested_sha='test',ingested_at='2026-09-18T14:00:00Z',remaining=['RIGHTS_CLEARANCE','RELEASE_PACKAGE_REVIEW'])
  payload.update(overrides)
  ledger.append(p.h.make_event('test-source-registration','EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
  return ledger
 def test_binding_preserves_prior_and_authority(self):
  original=copy.deepcopy(self.prior)
  with tempfile.TemporaryDirectory() as d:
   ledger=self.ledger(Path(d)/'ledger.jsonl')
   state=p.project(self.parent,ledger,self.source,self.prior,self.media)
   self.assertEqual(state['state_version'],13)
   self.assertEqual(state['authorizations'],json.loads(self.parent)['authorizations'])
   self.assertEqual(state['production_state'],json.loads(self.parent)['production_state'])
   self.assertFalse(state['current_release']['publish_ready'])
   self.assertEqual(state,p.project(self.parent,ledger,self.source,self.prior,self.media))
  self.assertEqual(original,self.prior)
  self.assertFalse(self.facts()['runtime_signed_grant_created'])
 def test_tampered_source_fails(self):
  self.source=self.source.replace(b'EIGEN PRODUCTIE',b'THIRD PARTY')
  with self.assertRaises(ValueError):self.facts()
 def test_parent_change_fails(self):
  self.parent+=b' '
  with self.assertRaises(ValueError):self.facts()
 def test_different_media_sha_fails(self):
  self.media['sha256']='0'*64
  with self.assertRaises(ValueError):self.facts()
 def test_different_prior_decision_fails(self):
  self.prior['decision']='REJECT'
  with self.assertRaises(ValueError):self.facts()
 def test_own_backing_never_means_rights_pass(self):
  f=self.facts();self.assertEqual(f['rights_status'],'RIGHTS_HOLD')
  self.assertFalse(f['rights_facts']['explicit_composition_publication_licence_previously_obtained'])
  self.assertEqual(f['rights_facts']['content_id_outcome'],'UNKNOWN')
 def test_cannot_smuggle_publish_authority(self):
  with tempfile.TemporaryDirectory() as d:
   ledger=self.ledger(Path(d)/'ledger.jsonl',PUBLICATION_AUTHORIZED=True)
   with self.assertRaises(ValueError):p.project(self.parent,ledger,self.source,self.prior,self.media)
 def test_cannot_clear_rights_or_package_gate(self):
  with tempfile.TemporaryDirectory() as d:
   ledger=self.ledger(Path(d)/'ledger.jsonl',remaining=[])
   with self.assertRaises(ValueError):p.project(self.parent,ledger,self.source,self.prior,self.media)
 def test_no_forged_human_grant(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'ledger.jsonl';ledger=self.ledger(path)
   ledger.append(p.h.make_event('forged','HUMAN_GATE_GRANTED','2026-09-18T14:00:00Z','nitin',gate='NITIN_PUBLISH_APPROVAL',decision='APPROVE'))
   with self.assertRaises(ValueError):p.project(self.parent,ledger,self.source,self.prior,self.media)
if __name__=='__main__':unittest.main()
