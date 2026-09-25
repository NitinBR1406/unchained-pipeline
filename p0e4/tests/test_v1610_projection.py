import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import project_v1610 as p
from integration.contracts import file_resolver
class TestV1610(unittest.TestCase):
 def test_projection(self):
  l=p.EventLedger(str(p.OUT/'ENGINEERING_EVENT_LEDGER.jsonl'));a=p.project(p.PARENT.read_bytes(),l,file_resolver(p.ROOT));b=p.project(p.PARENT.read_bytes(),l,file_resolver(p.ROOT));self.assertEqual(a,b);self.assertEqual(a['state_version'],36);self.assertFalse(a['authorizations']['PUBLICATION_AUTHORIZED'])
if __name__=='__main__':unittest.main()
