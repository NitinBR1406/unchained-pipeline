import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog.engine import compile_catalog,STATES
from integration.contracts import canonical,digest

def fixture():
 return dict(schema='CATALOG_INVENTORY_V01',schema_version=1,observed_at='2026-09-19T12:00:00Z',source_root='TEST_ONLY',scope_status='PARTIAL_READ_ONLY',folders=[dict(relative_path='Song',source_ref='evidence/finder.json',complete=False,entries=[dict(relative_path='Song/final master vocals 120 bpm.wav',kind='file',bytes=None,sha256=None,availability='UNKNOWN',source_ref='evidence/finder.json')])])

class Catalog(unittest.TestCase):
 def test_filename_does_not_prove_semantics(self):
  result=compile_catalog(fixture());row=result['MASTER_CATALOG_V01']['records'][0]
  self.assertEqual(row['song_title'],'UNKNOWN');self.assertEqual(row['classification'],'UNKNOWN');self.assertEqual(row['verified_components']['master'],'UNKNOWN');self.assertFalse(row['live_performance_ready'])
  self.assertIn('master',row['assets'][0]['candidate_role_hints']);self.assertEqual(result['LIVE_READY_QUEUE']['records'],[]);self.assertEqual(result['VATSAL_ACTION_QUEUE']['records'],[])
 def test_replay_and_identity_stability(self):
  inv=fixture();a=compile_catalog(inv);self.assertEqual(canonical(a),canonical(compile_catalog(inv)))
  inv['observed_at']='2026-09-20T12:00:00Z';b=compile_catalog(inv)
  self.assertEqual(a['MASTER_CATALOG_V01']['records'][0]['song_id'],b['MASTER_CATALOG_V01']['records'][0]['song_id'])
 def test_duplicate_and_hash_conflict(self):
  for h in (None,'0'*64):
   inv=fixture();e=copy.deepcopy(inv['folders'][0]['entries'][0]);e['sha256']=h;inv['folders'][0]['entries'].append(e)
   with self.assertRaises(ValueError):compile_catalog(inv)
 def test_missing_refs_and_unsafe_paths(self):
  inv=fixture();inv['folders'][0]['source_ref']=''
  with self.assertRaises(ValueError):compile_catalog(inv)
  inv=fixture();inv['folders'][0]['entries'][0]['relative_path']='../private'
  with self.assertRaises(ValueError):compile_catalog(inv)
 def observations(self,fields):
  return [dict(relative_path='Song',field=k,value=v,evidence_refs=[dict(uri='attestation',sha256=digest(b'verified attestation'))]) for k,v in fields.items()]
 def test_explicit_prerequisites_route_vatsal_not_publication(self):
  fields={'classification':'ORIGINAL','vocals':'READY_VERIFIED','production_status':'VOCALS_READY_VATSAL_PENDING','action_owner':'VATSAL'}
  result=compile_catalog(fixture(),self.observations(fields),lambda u:b'verified attestation')
  self.assertEqual(len(result['VATSAL_ACTION_QUEUE']['records']),1);self.assertFalse(result['MASTER_CATALOG_V01']['publication_authorized'])
 def test_live_requires_separate_explicit_status(self):
  fields={'classification':'ORIGINAL','instrumental_backing':'READY_VERIFIED','lyrics':'READY_VERIFIED'}
  self.assertEqual(compile_catalog(fixture(),self.observations(fields),lambda u:b'verified attestation')['LIVE_READY_QUEUE']['records'],[])
  fields['production_status']='LIVE_READY'
  self.assertEqual(len(compile_catalog(fixture(),self.observations(fields),lambda u:b'verified attestation')['LIVE_READY_QUEUE']['records']),1)
 def test_missing_prerequisites_approval_and_bad_evidence_fail(self):
  for f in ({'production_status':'LIVE_READY'},{'publication_authorized':True},{'classification':'COVER','production_status':'RECREATION_2008_LYRICS_REVIEW'}):
   with self.assertRaises(ValueError):compile_catalog(fixture(),self.observations(f),lambda u:b'verified attestation')
  with self.assertRaises(ValueError):compile_catalog(fixture(),self.observations({'classification':'COVER'}),lambda u:b'changed')
 def test_lifecycle_backlog_and_unknown_finance(self):
  out=compile_catalog(fixture());self.assertEqual(len(out['FACTORY_EXPANSION_BACKLOG_V01']['engines']),9);self.assertEqual(len(STATES),8)
  row=out['PRODUCTION_SHEET_VIEW_V01']['rows'][0];self.assertEqual(set(row['FINANCIAL_STAGES'].values()),{'UNKNOWN'});self.assertEqual(row['ATTRIBUTION']['song_id'],row['SONG_ID']);self.assertTrue(all(v is None for k,v in row['ATTRIBUTION'].items() if k!='song_id'))

if __name__=='__main__':unittest.main()
