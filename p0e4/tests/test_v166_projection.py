import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import project_v166 as p
from integration.contracts import file_resolver


class V166ProjectionTest(unittest.TestCase):
    def test_projection_is_deterministic_and_gated(self):
        ledger=p.EventLedger(str(p.OUT/'ENGINEERING_EVENT_LEDGER.jsonl'))
        a=p.project(p.PARENT.read_bytes(),ledger,file_resolver(p.ROOT))
        b=p.project(p.PARENT.read_bytes(),ledger,file_resolver(p.ROOT))
        self.assertEqual(a,b); self.assertEqual(a['state_version'],32)
        self.assertEqual(a['p0e4']['current_color_status'],p.STATUS)
        self.assertFalse(a['authorizations']['PRODUCTION_DEPLOYMENT_AUTHORIZED'])
        self.assertFalse(a['authorizations']['PUBLICATION_AUTHORIZED'])
        self.assertEqual(a['production_state']['first_real_poster'],'PAUSED_BY_NITIN')


if __name__=='__main__': unittest.main()
