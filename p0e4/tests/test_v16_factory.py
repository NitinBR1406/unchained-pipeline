import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.consumer import compile_preflight
from canonical.factory import prepare,verify_preparation,read_groups,shadow_bundle,execute_live,ROUTES
from canonical.intelligence_intake import integrate
from integration.contracts import canonical,digest
ROOT=Path(__file__).resolve().parents[2]
class Factory(unittest.TestCase):
 def setUp(self):
  self.d,self.c,self.b=fixture()
  self.m=json.loads((ROOT/'p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V01.json').read_bytes())
  self.s=json.loads((ROOT/'p0e4/evidence/canonical_v15/LIVE_SHEET_SNAPSHOT.json').read_bytes())
 def resolve(self,u):return self.b[u] if u in self.b else (ROOT/u).read_bytes()
 def claude(self):
  p=compile_preflight(self.d,self.c,self.resolve)
  return dict(schema='CLAUDE_FACTORY_INPUT',schema_version=1,canonical_sha256=p['canonical_sha256'],jobs=[dict(package_id=j['package_id'],groups=j['groups']) for j in p['jobs']],publication_authorized=False)
 def run_factory(self,r=None):return prepare(self.d,self.c,r or self.claude(),self.m,self.s,self.resolve)
 def test_existing_engines_are_reused(self):
  from unpipe.adapters import PackagingEngine,DerivativeEngine
  with patch.object(PackagingEngine,'build',autospec=True,side_effect=PackagingEngine.build) as packaging,patch.object(DerivativeEngine,'plan',autospec=True,side_effect=DerivativeEngine.plan) as derivative:
   result=self.run_factory();self.assertEqual(packaging.call_count,1);self.assertEqual(derivative.call_count,1)
  self.assertEqual(canonical(read_groups(result['jobs'][0])),canonical(self.claude()['jobs'][0]['groups']))
  self.assertEqual(set(ROUTES),set(self.claude()['jobs'][0]['groups']))
 def test_all_group_loss_or_type_drift_fails(self):
  for group in ROUTES:
   for mode in ('missing','changed'):
    r=self.claude()
    if mode=='missing':del r['jobs'][0]['groups'][group]
    else:r['jobs'][0]['groups'][group]=False
    with self.subTest(group=group,mode=mode),self.assertRaises(ValueError):self.run_factory(r)
  r=self.claude();r['jobs'][0]['groups']['timestamps']['start_ms']=0.0
  with self.assertRaises(ValueError):self.run_factory(r)
 def test_output_mutations_and_gates_fail(self):
  r=self.claude();result=self.run_factory(r)
  for k,v in [('publication_authorized',True),('production_deployment_authorized',True),('extra',1),('schema_version',2)]:
   bad=copy.deepcopy(result);bad[k]=v
   with self.assertRaises(ValueError):verify_preparation(bad,self.d,self.c,r,self.m,self.s,self.resolve)
  with self.assertRaises(ValueError):execute_live(result)
 def test_duplicate_wrong_platform_sha_and_80_percent_fail(self):
  for mode in ('duplicate','platform','sha','performance','unknown'):
   self.setUp()
   if mode=='duplicate':self.d['DERIVATIVES'].append(copy.deepcopy(self.d['DERIVATIVES'][0]))
   elif mode=='platform':self.d['PUBLICATION'][0]['platform']='tiktok'
   elif mode=='sha':self.d['source_package_sha256']='0'*64
   elif mode=='performance':self.c['payload']['edit_plan']['segments'][0]['performer_visible']=False
   else:self.d['extra']=1
   with self.subTest(mode=mode),self.assertRaises(ValueError):self.run_factory()
 def test_learning_lineage_and_deterministic_shadow(self):
  r=self.claude();a=self.run_factory(r);b=self.run_factory(r);self.assertEqual(canonical(a),canonical(b))
  graph=a['jobs'][0]['learning']['attribution'][0]
  self.assertEqual(graph,dict(publication_id='publication:test',package_id='package:test',derivative_id='derivative:test',content_id='TEST_ONLY_GOLDEN',campaign_id='campaign:test',experiment_id='experiment:test',hypothesis_id='hypothesis:test'))
  for table in ('ANALYTICS','MONETIZATION','BUSINESS_FUNNEL','AUDIENCE_GROWTH'):self.assertEqual(a['learning'][table],[])
  self.assertEqual(shadow_bundle(a,self.d,self.c,r,self.m,self.s,self.resolve),shadow_bundle(b,self.d,self.c,r,self.m,self.s,self.resolve))
 def test_actual_gemini_response_mapping_and_tampering(self):
  out=ROOT/'p0e4/evidence/factory_v16';r=json.loads((out/'GEMINI_RESULT.json').read_bytes());receipt=json.loads((out/'GEMINI_RECEIPT.json').read_bytes())
  d,c=integrate(self.d,self.c,r,receipt,self.resolve)
  self.assertEqual(d['PLATFORM_PACKAGES'][0]['cta'],r['editorial']['cta']);self.assertEqual(c['producer']['run_id'],r['request_id'])
  r['editorial']['cta']='silently changed'
  with self.assertRaises(ValueError):integrate(self.d,self.c,r,receipt,self.resolve)
if __name__=='__main__':unittest.main()
