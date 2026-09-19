import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import project_v161 as p
from integration.contracts import canonical,digest
from catalog.engine import compile_catalog
from control_plane.ledger import EventLedger
import handoff as h
ROOT=Path(__file__).resolve().parents[2]

class Projection(unittest.TestCase):
 def setUp(self):
  inv=dict(schema='CATALOG_INVENTORY_V01',schema_version=1,observed_at='2026-09-19T16:00:00Z',source_root='TEST_ONLY',scope_status='EMPTY_SYNTHETIC',folders=[])
  self.blobs={'inv':canonical(inv),'out':canonical(compile_catalog(inv)),'reg':canonical(dict(tested_sha='a'*40,passed=1,total=1,tracked_worktree_clean=True,prior_manifests=[{'pass':True}]))}
  for name,filename in [('source','SYNTHETIC_INPUT.json'),('plan','RESOLVE_EXECUTION_PLAN_SYNTHETIC.json')]:self.blobs[name]=(ROOT/'p0e4/evidence/resolve_preinstall_v01'/filename).read_bytes()
  def ref(k):return dict(uri=k,sha256=digest(self.blobs[k]))
  self.a=dict(status=p.STATUS,tested_sha='a'*40,deterministic_replay=True,production_e2e_status='BLOCKED_NOT_GREEN',blocked_tasks=['RESOLVE_INSTALL','NITIN_AUDIO_SOURCE_BINDING','CATALOG_BYTE_READ_SETUP'],resolve_execution_proven=False,live_cutover_authorized=False,always_on_dispatcher_proven=False,production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN',catalog_refs={'inventory':ref('inv'),'outputs':ref('out')},resolve_refs={'input':ref('source'),'plan':ref('plan')},regression_ref=ref('reg'))
 def project(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'ledger';f.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(f))
   payload=dict(tested_sha=self.a['tested_sha'],ingested_at='2026-09-19T16:00:00Z',acceptance=self.a,evidence_refs=[self.a['regression_ref']])
   ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
   a=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),self.blobs.__getitem__)
   self.assertEqual(canonical(a),canonical(p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),self.blobs.__getitem__)))
   return a
 def test_replay_preserves_authority(self):
  state=self.project();self.assertEqual(state['state_version'],27)
  for k in ('authorizations','production_state','current_release'):self.assertEqual(state[k],json.loads(p.PARENT.read_bytes())[k])
 def test_all_claim_escalations_rejected(self):
  for k in ('publication_authorized','production_deployment_authorized','resolve_execution_proven','live_cutover_authorized','always_on_dispatcher_proven'):
   self.setUp();self.a[k]=True
   with self.subTest(k=k),self.assertRaises(ValueError):self.project()
 def test_byte_corruption_rejected(self):
  for key in self.blobs:
   self.setUp();self.blobs[key]+=b' '
   with self.subTest(key=key),self.assertRaises(ValueError):self.project()
 def test_bad_catalog_replay_even_with_updated_hash(self):
  result=json.loads(self.blobs['out']);result['MASTER_CATALOG_V01']['publication_authorized']=True
  self.blobs['out']=canonical(result);self.a['catalog_refs']['outputs']['sha256']=digest(self.blobs['out'])
  with self.assertRaisesRegex(ValueError,'catalog replay'):self.project()
 def test_failed_regression_even_with_updated_hash(self):
  reg=json.loads(self.blobs['reg']);reg['passed']=0;self.blobs['reg']=canonical(reg);self.a['regression_ref']['sha256']=digest(self.blobs['reg'])
  with self.assertRaisesRegex(ValueError,'regression'):self.project()

class InputTime(unittest.TestCase):
 def test_invalid_timestamp_rejected_before_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'must_not_exist'
   with self.assertRaises(ValueError):p.main(output,'2026-09-19T15:00:00+00:00')
   self.assertFalse(output.exists())

if __name__=='__main__':unittest.main()
