import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog.engine import compile_catalog,STATES,ROLES,FLAGS
from integration.contracts import digest,canonical
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'p0e4/evidence/catalog_bootstrap_v01'
class CatalogLive(unittest.TestCase):
 def test_actual_observations_replay_no_unproven_readiness(self):
  inv=json.loads((BASE/'CATALOG_INVENTORY_V01.json').read_bytes())
  result=compile_catalog(inv)
  self.assertEqual(result,json.loads((BASE/'CATALOG_OUTPUTS_V01.json').read_bytes()))
  self.assertEqual(len(inv['folders']),69)
  self.assertEqual(sum(len(f['entries']) for f in inv['folders']),446)
  for f in inv['folders']:
   for e in f['entries']:
    self.assertEqual(digest((ROOT/e['source_ref']['uri']).read_bytes()),e['source_ref']['sha256'])
    self.assertIsNone(e['sha256'])
  self.assertFalse(result['LIVE_READY_QUEUE']['records']);self.assertFalse(result['CATALOG_REACTIVATION_QUEUE']['records'])
  for row in result['MASTER_CATALOG_V01']['records']:
   self.assertEqual(row['production_status'],'UNKNOWN')
   self.assertFalse(row['live_performance_ready'])
 def test_controller_boundary_matches_engine(self):
  seed=json.loads((ROOT/'p0e4/controller/READY_WRITES_V01.json').read_bytes())
  task=next(t for t in seed['tasks'] if t['task_id']=='EC_V161_CATALOG_LIFECYCLE_CONTRACT')
  contract=next(iter(task['outputs'].values()))
  self.assertEqual(contract['lifecycle_states'],list(STATES));self.assertEqual(contract['verified_components'],list(ROLES))
  for k,v in FLAGS.items():self.assertEqual(contract[k],v)
  self.assertFalse(contract['filename_claims_authoritative']);self.assertFalse(contract['inventory_only_implies_ready'])
if __name__=='__main__':unittest.main()
