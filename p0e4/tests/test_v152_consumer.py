import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.consumer import compile_preflight,verify_readback,execute_production
from canonical.coverage import REQUIRED
class Consumer(unittest.TestCase):
 def setUp(self):self.d,self.c,self.b=fixture()
 def compile(self):return compile_preflight(self.d,self.c,self.b.__getitem__)
 def test_all_fourteen_consumed_and_readback(self):
  r=self.compile();self.assertEqual(set(r['jobs'][0]['groups']),set(REQUIRED))
  self.assertEqual(verify_readback(r,self.d,self.c,self.b.__getitem__)['groups_per_package'],14)
  self.assertFalse(r['live_legacy_execution_proven'])
 def test_each_missing_or_changed_group_fails(self):
  for key in REQUIRED:
   for mutation in ('drop','change'):
    r=self.compile()
    if mutation=='drop':del r['jobs'][0]['groups'][key]
    else:r['jobs'][0]['groups'][key]='silently reinterpreted'
    with self.assertRaises(ValueError):verify_readback(r,self.d,self.c,self.b.__getitem__)
 def test_unknown_or_approval_escalation_fails(self):
  for k,v in [('publication_authorized',True),('schema_version',2),('extra','invented')]:
   r=self.compile();r[k]=v
   with self.assertRaises(ValueError):verify_readback(r,self.d,self.c,self.b.__getitem__)
 def test_timeline_and_lineage_fail_before_consumer(self):
  self.d['DERIVATIVES'][0]['end_ms']=1000000
  with self.assertRaises(ValueError):self.compile()
  self.setUp();self.d['source_package_sha256']='0'*64
  with self.assertRaises(ValueError):self.compile()
 def test_no_production_or_fake_fields(self):
  with self.assertRaises(ValueError):execute_production(self.compile())
  self.assertIsNone(self.compile()['jobs'][0]['groups']['schedules']['scheduled_at'])
  self.assertIsNone(self.compile()['jobs'][0]['groups']['thumbnails_posters']['poster'])
 def test_eighty_percent_gate_retained(self):
  self.c['payload']['edit_plan']['segments'][0]['performer_visible']=False
  with self.assertRaises(ValueError):self.compile()
if __name__=='__main__':unittest.main()
