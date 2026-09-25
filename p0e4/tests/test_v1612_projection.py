import unittest
from controller import project_v1612 as p
from integration.contracts import file_resolver
class TestV1612(unittest.TestCase):
 def test_projection(self):
  l=p.EventLedger(str(p.OUT/'ENGINEERING_EVENT_LEDGER.jsonl'));a=p.project(p.PARENT.read_bytes(),l,file_resolver(p.ROOT));b=p.project(p.PARENT.read_bytes(),l,file_resolver(p.ROOT));self.assertEqual(a,b);self.assertEqual(a['state_version'],38);self.assertFalse(a['authorizations']['PUBLICATION_AUTHORIZED'])
if __name__=='__main__':unittest.main()
