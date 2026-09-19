import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from integration.contracts import canonical,digest
from resolve.plan import build,verify,execute,frame,review_candidate,QC_CHECKS

class ResolvePlan(unittest.TestCase):
 def setUp(self):self.d,self.c,self.blobs=fixture();self.r=self.blobs.__getitem__
 def plan(self):return build(self.d,self.c,self.r)
 def rebind(self):
  h=digest(canonical(self.c));self.d['source_package_sha256']=h
  self.d['CREATIVE_INTELLIGENCE'][0]['source_package_sha256']=h
  self.d['PRODUCTION'][0]['creative_package_sha256']=h
  self.d['PRODUCTION'][0]['edit_plan_sha256']=digest(canonical(self.c['payload']['edit_plan']))
 def test_deterministic_exact_routing(self):
  p=self.plan();self.assertEqual(canonical(p),canonical(self.plan()));verify(p,self.d,self.c,self.r)
  j=p['jobs'][0];self.assertEqual(j['render_profile']['width'],1080);self.assertEqual(j['render_profile']['height'],1920)
  self.assertEqual(j['cuts'][-1]['end_frame_exclusive'],250);self.assertEqual(j['canonical_groups']['edit_effects'],self.c['payload']['edit_plan'])
  self.assertFalse(p['resolve_execution_proven']);self.assertEqual(p['outputs'],[])
  self.assertFalse(j['render_profile']['quick_export_upload'])
 def test_drift_and_publication_escalation(self):
  for k,v in [('publication_authorized',True),('schema_version',2),('outputs',[{'sha256':'0'*64}])]:
   p=self.plan();p[k]=v
   with self.assertRaises(ValueError):verify(p,self.d,self.c,self.r)
 def test_unknown_field_and_source_hash(self):
  self.d['unknown']=True
  with self.assertRaises(ValueError):self.plan()
  self.setUp();self.blobs[self.c['inputs'][0]['uri']]=b'changed'
  with self.assertRaises(ValueError):self.plan()
 def test_exact_frames_no_rounding(self):
  self.assertEqual(frame(1000,(25,1)),25)
  with self.assertRaises(ValueError):frame(1,(25,1))
  with self.assertRaises(ValueError):build(self.d,self.c,self.r,(True,1))
  with self.assertRaises(ValueError):build(self.d,self.c,self.r,(120,1))
 def test_derivative_performance_not_only_master(self):
  # Full plan remains 80% performance; derivative selecting the other 20% fails.
  s=self.c['payload']['edit_plan']['segments'][0];s['end_ms']=8000;s['source_end_ms']=8000
  other=copy.deepcopy(s);other.update(start_ms=8000,end_ms=10000,source_start_ms=8000,source_end_ms=10000,performer_visible=False)
  self.c['payload']['edit_plan']['segments'].append(other);self.rebind()
  end=self.c['payload']['edit_plan']['duration_ms']
  self.d['DERIVATIVES'][0]['start_ms']=end-1000;self.d['DERIVATIVES'][0]['end_ms']=end
  with self.assertRaisesRegex(ValueError,'DERIVATIVE_80'):self.plan()
 def test_parameterless_effect_is_preserved_and_blocked(self):
  self.c['payload']['edit_plan']['effects']=[dict(kind=k,start_ms=0,end_ms=1000,intensity_milli=100,performer_obscured=False) for k in ('zoom','shake','caption','reframe','grade','cut')];self.rebind()
  p=self.plan()
  self.assertEqual(len(p['jobs'][0]['operations']),6)
  for op in p['jobs'][0]['operations']:self.assertEqual(op['execution_status'],'BLOCKED_MISSING_EXACT_OPERATION_PARAMETERS')
  with self.assertRaisesRegex(ValueError,'TRANSPORT_NOT_IMPLEMENTED'):execute(p)
 def test_unsupported_operations_and_obscuring_effects(self):
  for kind,obscured in [('invented_plugin',False),('transition',False),('zoom',True)]:
   self.setUp();self.c['payload']['edit_plan']['effects']=[dict(kind=kind,start_ms=0,end_ms=1000,intensity_milli=100,performer_obscured=obscured)];self.rebind()
   with self.assertRaises(ValueError):self.plan()
 def test_qc_binds_actual_bytes_rework_and_no_approval(self):
  p=self.plan();self.blobs['candidate']=b'synthetic candidate'
  out={'uri':'candidate','sha256':digest(self.blobs['candidate'])}
  obs=dict(plan_sha256=digest(canonical(p)),output_sha256=out['sha256'],checked_at=p['created_at'],reviewer={'agent':'SYNTHETIC_QC','model':None,'run_id':'TEST_ONLY'},checks={k:'PASS' for k in QC_CHECKS},evidence_refs=self.c['evidence_refs'])
  receipt=review_candidate(p,out,obs,self.r);self.assertFalse(receipt['authenticated_qc_proven']);self.assertFalse(receipt['publication_authorized'])
  obs['checks']['lipsync']='UNKNOWN';receipt=review_candidate(p,out,obs,self.r)
  self.assertEqual(receipt['status'],'REWORK_REQUIRED');self.assertEqual(receipt['rework']['required_checks'],['lipsync'])
  obs['output_sha256']='0'*64
  with self.assertRaises(ValueError):review_candidate(p,out,obs,self.r)
 def test_qc_missing_checks_and_same_reviewer(self):
  p=self.plan();self.blobs['candidate']=b'test'
  out={'uri':'candidate','sha256':digest(b'test')}
  obs=dict(plan_sha256=digest(canonical(p)),output_sha256=out['sha256'],checked_at=p['created_at'],reviewer={'agent':'CODEX_PLAN_ADAPTER','model':None,'run_id':'TEST_ONLY'},checks={k:'PASS' for k in QC_CHECKS},evidence_refs=self.c['evidence_refs'])
  with self.assertRaises(ValueError):review_candidate(p,out,obs,self.r)
  obs['reviewer']['agent']='INDEPENDENT_TEST';del obs['checks']['audio']
  with self.assertRaises(ValueError):review_candidate(p,out,obs,self.r)

if __name__=='__main__':unittest.main()
