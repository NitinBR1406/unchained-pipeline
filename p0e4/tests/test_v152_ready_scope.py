import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.contracts import digest
from canonical.coverage import REQUIRED
ROOT=Path(__file__).resolve().parents[2]
class ReadyScope(unittest.TestCase):
 def test_authority_and_bounded_outputs(self):
  seed=json.loads((ROOT/'p0e4/controller/READY_WRITES_V01.json').read_bytes())
  self.assertEqual(digest((ROOT/seed['master_state_path']).read_bytes()),seed['master_state_sha256'])
  self.assertEqual(len({x['task_id'] for x in seed['tasks']}),len(seed['tasks']))
  for task in seed['tasks']:
   self.assertIsNone(task['human_gate_required']);self.assertEqual(task['scope'],'p0e4_nonproduction_contract_fixture')
   self.assertLessEqual(len(task['outputs']),3)
   for p in task['outputs']:self.assertTrue(p.startswith('p0e4/generated/'));self.assertNotIn('..',Path(p).parts)
  task=next(x for x in seed['tasks'] if x['task_id']=='EC_V152_PREFLIGHT_GROUPS')
  self.assertEqual(set(next(iter(task['outputs'].values()))['required_groups']),set(REQUIRED))
if __name__=='__main__':unittest.main()
