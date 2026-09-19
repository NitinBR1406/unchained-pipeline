import copy,io,json,sys,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.coverage import assess,require_execution,REQUIRED
from canonical.shadow_bundle import build,verify
from integration.contracts import digest,canonical
ROOT=Path(__file__).resolve().parents[2]
class Coverage(unittest.TestCase):
 def setUp(self):
  self.d,self.c,self.blobs=fixture()
  self.m=json.loads((ROOT/'p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V01.json').read_bytes())
  self.s=json.loads((ROOT/'p0e4/evidence/canonical_v15/LIVE_SHEET_SNAPSHOT.json').read_bytes())
 def resolve(self,u):return self.blobs[u] if u in self.blobs else (ROOT/u).read_bytes()
 def report(self):return assess(self.d,self.c,self.m,self.s,self.resolve)
 def test_full_required_set_cannot_be_relaxed(self):
  r=self.report();self.assertEqual(r['required_count'],14);self.assertEqual(r['projected_count'],3)
  self.assertEqual(r['missing_count'],11);self.assertFalse(r['dispatch_authorized'])
  with self.assertRaisesRegex(ValueError,'REQUIRED_UNMAPPED'):require_execution(self.d,self.c,self.m,self.s,self.resolve)
 def test_sidecar_is_not_execution(self):
  r=self.report();self.assertTrue(r['shadow_zero_drift']);self.assertFalse(r['execution_coverage_complete'])
  self.assertEqual({x['field'] for x in r['fields']},set(REQUIRED))
 def test_no_consumers_blocks_even_projected_field(self):
  for m in self.m['fields']:m['make_consumers']=[]
  self.assertEqual(self.report()['projected_count'],0)
 def test_forged_evidence_fails(self):
  self.m['fields'][0]['evidence_refs'][0]['sha256']='0'*64
  with self.assertRaises(ValueError):self.report()
 def test_wrong_lineage_fails(self):
  self.d['source_package_sha256']='0'*64
  with self.assertRaises(ValueError):self.report()
 def test_deterministic_and_inert_bundle(self):
  files={'fixture.json':canonical(self.d),'creative.json':canonical(self.c)}
  b=build(files);self.assertEqual(b,build(dict(reversed(list(files.items())))))
  self.assertEqual(verify(b,digest(b)),files)
  with self.assertRaises(ValueError):verify(b,'0'*64)
 def test_unsafe_name_and_binary_rejected(self):
  for name in ['../escape.json','/escape.json','a\\b.json','MANIFEST.json','run.py']:
   with self.assertRaises(ValueError):build({name:b'{}'})
  with self.assertRaises(ValueError):build({'x.json':b'not json'})
 def test_tampered_control_rejected_even_rehashed(self):
  b=build({'x.json':b'{}'});out=io.BytesIO()
  with zipfile.ZipFile(io.BytesIO(b)) as src,zipfile.ZipFile(out,'w') as dst:
   for n in src.namelist():
    data=src.read(n)
    if n=='MANIFEST.json':
     m=json.loads(data);m['publication_authorized']=True;data=canonical(m)
    dst.writestr(n,data)
  with self.assertRaises(ValueError):verify(out.getvalue(),digest(out.getvalue()))
if __name__=='__main__':unittest.main()
