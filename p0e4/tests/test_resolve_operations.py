import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from integration.contracts import canonical,digest
from resolve.plan import build
from resolve.operations import compile_operations

def fixture_operations():
 d,c,b=fixture();base=build(d,c,b.__getitem__);ref=dict(uri='TEST_ONLY/style',sha256='0'*64)
 trajectory={'keyframes':[{'frame':0,'scale_millionths':1000000,'center':{'x_millionths':500000,'y_millionths':500000}},{'frame':24,'scale_millionths':1100000,'center':{'x_millionths':510000,'y_millionths':500000}}],'interpolation':'LINEAR'}
 params={'cut':{'cut_frames':[10]},'reframe':{'left_millionths':100000,'top_millionths':100000,'right_millionths':900000,'bottom_millionths':900000},'zoom':trajectory,'push_in':trajectory,'shake':trajectory,'caption':{'text':'TEST_ONLY','style_ref':ref,'position':{'x_millionths':500000,'y_millionths':800000}},'text':{'text':'TEST_ONLY TITLE','style_ref':ref,'position':{'x_millionths':500000,'y_millionths':100000}},'transition':{'type':'DISSOLVE','duration_frames':25,'outgoing_handle_frames':25,'incoming_handle_frames':25},'effect':{'plugin_id':'TEST_ONLY','template_ref':ref,'license_status':'UNKNOWN','intent':'VISUAL_OVERLAY_NO_BASELINE_CHANGE'}}
 spec=dict(schema='RESOLVE_OPERATION_DETAILS',schema_version=1,base_plan_sha256=digest(canonical(base)),operations=[dict(operation_id='test:'+k,package_id=base['jobs'][0]['package_id'],kind=k,start_frame=0,end_frame_exclusive=25,performer_obscured=False,parameters=copy.deepcopy(v),evidence_ref=copy.deepcopy(ref)) for k,v in params.items()])
 return base,spec

class Operations(unittest.TestCase):
 def test_all_exact_parameter_routes_remain_blocked(self):
  b,s=fixture_operations();r=compile_operations(b,s);self.assertEqual(len(r['operations']),9);self.assertEqual(canonical(r),canonical(compile_operations(b,s)));self.assertTrue(all(not x['execution_enabled'] for x in r['operations']))
 def test_sha_unknown_duplicate_escalation(self):
  for mutate in (lambda s:s.update(base_plan_sha256='0'*64),lambda s:s['operations'][0].update(kind='audio_gain'),lambda s:s['operations'][0].update(performer_obscured=True),lambda s:s['operations'][0]['parameters'].update(extra=1),lambda s:s['operations'].append(copy.deepcopy(s['operations'][0]))):
   b,s=fixture_operations();mutate(s)
   with self.assertRaises(ValueError):compile_operations(b,s)
 def test_frame_crop_scale_nonfinite(self):
  for mutate in (lambda s:s['operations'][0].update(end_frame_exclusive=99999),lambda s:s['operations'][0].update(start_frame=True),lambda s:s['operations'][1]['parameters'].update(left_millionths=999999),lambda s:s['operations'][2]['parameters']['keyframes'][0].update(scale_millionths=float('nan')),lambda s:s['operations'][2]['parameters']['keyframes'][1].update(frame=0)):
   b,s=fixture_operations();mutate(s)
   with self.assertRaises(ValueError):compile_operations(b,s)
 def test_transitions_handles_and_baseline_lock(self):
  b,s=fixture_operations();s['operations'][-2]['parameters']['incoming_handle_frames']=1
  with self.assertRaises(ValueError):compile_operations(b,s)
  b,s=fixture_operations();s['operations'][-1]['parameters']['intent']='GRADE'
  with self.assertRaises(ValueError):compile_operations(b,s)
 def test_no_base_performance_or_publication_bypass(self):
  for key,value in [('publication_authorized',True),('resolve_execution_proven',True)]:
   b,s=fixture_operations();b[key]=value;s['base_plan_sha256']=digest(canonical(b))
   with self.assertRaises(ValueError):compile_operations(b,s)
  b,s=fixture_operations();b['jobs'][0]['performance']['visible_ms']=1;s['base_plan_sha256']=digest(canonical(b))
  with self.assertRaises(ValueError):compile_operations(b,s)

if __name__=='__main__':unittest.main()
