import ast,copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.consumer import compile_preflight
from canonical.render_request import prepare_clip,readback_clip
ROOT=Path(__file__).resolve().parents[2]
class RenderRequest(unittest.TestCase):
 def setUp(self):
  d,c,b=fixture();self.g=compile_preflight(d,c,b.__getitem__)['jobs'][0]['groups']
  self.e=json.loads((ROOT/'p0e4/canonical/RENDER_INTERFACE_V16.json').read_bytes())['evidence_refs']
 def resolve(self,u):return (ROOT/u).read_bytes()
 def test_existing_request_keys_and_exact_ms_readback(self):
  r=prepare_clip(self.g,self.e,self.resolve)
  source=ast.parse(self.resolve(self.e[0]['uri']));keys={n.args[0].value for n in ast.walk(source) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='b' and n.func.attr=='get' and n.args and isinstance(n.args[0],ast.Constant)}
  self.assertLessEqual(set(r['request_fields']),keys)
  self.g['timestamps']={'start_ms':123,'end_ms':9876};r=prepare_clip(self.g,self.e,self.resolve)
  self.assertEqual(readback_clip(r)['timestamps'],self.g['timestamps']);self.assertFalse(r['render_called'])
  self.assertNotIn('expected_un_sha256',r['request_fields'])
 def test_unproven_aspect_effect_or_evidence_fails(self):
  for mode in ('aspect','effect','evidence'):
   g=copy.deepcopy(self.g);e=copy.deepcopy(self.e)
   if mode=='aspect':g['aspect_ratios']='16:9'
   elif mode=='effect':g['edit_effects']['effects']=[{'kind':'unknown'}]
   else:e[0]['sha256']='0'*64
   with self.subTest(mode=mode),self.assertRaises(ValueError):prepare_clip(g,e,self.resolve)
if __name__=='__main__':unittest.main()
