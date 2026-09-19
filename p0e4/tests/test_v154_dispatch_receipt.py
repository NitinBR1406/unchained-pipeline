import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.consumer import compile_preflight
from canonical.dispatch_receipt import verify_external,ARCHIVE_SHA,REQUEST_ID
ROOT=Path(__file__).resolve().parents[2]
class Receipt(unittest.TestCase):
 def setUp(self):
  source=json.loads((ROOT/'p0e4/evidence/canonical_v15/SHADOW_FIXTURE.json').read_bytes());self.d,self.c=source['sidecar'],source['creative_package'];self.resolve=lambda u:(ROOT/u).read_bytes();self.archive=(ROOT/'p0e4/evidence/canonical_v151/CANONICAL_SHADOW_CLOSURE.zip').read_bytes()
  p=compile_preflight(self.d,self.c,self.resolve)
  self.result=dict(request_id=REQUEST_ID,input_archive_sha256=ARCHIVE_SHA,status='PASS',jobs=[dict(package_id=j['package_id'],groups=j['groups']) for j in p['jobs']])
  self.decision=dict(archive_sha256=ARCHIVE_SHA,transfer_authorized=True,destination='Claude Desktop Dispatch',allowed_purpose='NON_PUBLISHING_SYNTHETIC_P0E4_PREFLIGHT',production_deployment_authorized=False,make_sheet_mutation_authorized=False,cutover_authorized=False,publication_authorized=False,rights_clearance_granted=False,final_audio_binding_granted=False)
 def verify(self):return verify_external(self.result,self.d,self.c,self.resolve,self.archive,self.decision)
 def test_exact_readback_is_only_synthetic(self):
  r=self.verify();self.assertEqual(r['groups_per_package'],14);self.assertFalse(r['live_make_execution_proven'])
 def test_committed_ready_schema_accepts_exact_receipt(self):
  from jsonschema import Draft202012Validator
  seed=json.loads((ROOT/'p0e4/controller/READY_WRITES_V01.json').read_bytes())
  task=next(t for t in seed['tasks'] if t['task_id']=='EC_V154_PREFLIGHT_VALIDATION_SCHEMA')
  schema=next(iter(task['outputs'].values()));Draft202012Validator.check_schema(schema)
  Draft202012Validator(schema).validate(self.verify())
 def test_observed_status_and_reported_gates(self):
  self.result['status']='PREFLIGHT_OK';self.result['NON_PUBLISHING']=True
  self.result['gates']=dict(PRODUCTION_DEPLOYMENT_AUTHORIZED=False,PUBLICATION_AUTHORIZED=False,FIRST_REAL_POSTER='PAUSED_BY_NITIN')
  self.verify();self.result['gates']['PUBLICATION_AUTHORIZED']=True
  with self.assertRaises(ValueError):self.verify()
 def test_wrong_archive_and_request(self):
  for field in ('input_archive_sha256','request_id','status'):
   self.setUp();self.result[field]='WRONG'
   with self.assertRaises(ValueError):self.verify()
  self.setUp();self.archive+=b'corrupt'
  with self.assertRaises(ValueError):self.verify()
 def test_every_group_missing_or_changed_fails(self):
  original=copy.deepcopy(self.result)
  for key in original['jobs'][0]['groups']:
   self.result=copy.deepcopy(original);del self.result['jobs'][0]['groups'][key]
   with self.assertRaises(ValueError):self.verify()
 def test_numeric_type_and_extra_fields_fail(self):
  self.result['jobs'][0]['groups']['timestamps']['start_ms']=False
  with self.assertRaises(ValueError):self.verify()
  self.setUp();self.result['jobs'][0]['ignored_extra']=True
  with self.assertRaises(ValueError):self.verify()
 def test_transfer_cannot_escalate_other_gates(self):
  for k in ('publication_authorized','production_deployment_authorized','final_audio_binding_granted','rights_clearance_granted','make_sheet_mutation_authorized','cutover_authorized'):
   self.setUp();self.decision[k]=True
   with self.assertRaises(ValueError):self.verify()
if __name__=='__main__':unittest.main()
