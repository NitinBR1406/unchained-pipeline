import json,tempfile,unittest
from pathlib import Path
from control_plane.ledger import EventLedger
from integration.project_v09 import persist
from integration.contracts import file_resolver
from controller import project_v1615 as p
class ProjectionTest(unittest.TestCase):
 def test_projection(self):
  with tempfile.TemporaryDirectory() as d:
   lp=Path(d)/'l';persist(lp,p.PREFIX.read_bytes());l=EventLedger(str(lp));files=sorted(x for x in p.OUT.iterdir() if x.is_file() and x.name not in {'ENGINEERING_EVENT_LEDGER.jsonl','UNCHAINED_MASTER_PROJECT_STATE_V16_15.json','SHA256SUMS.txt'});payload={'status':p.STATUS,'acceptance_ref':str((p.OUT/'ACCEPTANCE_V01.json').relative_to(p.ROOT)),'evidence_refs':[{'uri':str(x.relative_to(p.ROOT)),'sha256':p.digest(x.read_bytes())} for x in files]};l.append(p.h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED','2026-09-25T20:45:00Z','codex',inputs=payload));parent=p.PARENT.read_bytes();auth=json.loads(parent)['authorizations'];s=p.project(parent,l,file_resolver(p.ROOT));self.assertEqual(s['state_version'],41);self.assertEqual(s['authorizations'],auth)
if __name__=='__main__':unittest.main()
