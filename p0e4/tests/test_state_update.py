import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import state_update as s
import handoff as h
from control_plane.ledger import EventLedger

class StateUpdateTests(unittest.TestCase):
    def test_replay_and_human_gates_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            summary={'verdict':'BLOCKED_NOT_GREEN','tested_sha':'TEST_ONLY','evidence_refs':[]}
            a=s.update(d,summary,'2026-09-18T00:00:00Z'); b=s.update(d,summary,'2026-09-18T00:00:00Z')
            self.assertEqual(a,b); self.assertEqual(a['state_version'],11)
            parent=json.loads((h.ROOT/h.STATE).read_text())
            self.assertEqual(a['authorizations'],parent['authorizations'])
            self.assertEqual(a['production_state'],parent['production_state'])
            self.assertFalse(a['current_release']['publish_ready'])
            summary['tested_sha']='changed'
            with self.assertRaises(ValueError): s.update(d,summary,'2026-09-18T00:00:00Z')

    def test_no_authority_or_green_through_engineering(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=EventLedger(str(Path(d)/'ledger'))
            ledger.append(h.make_event('bad','HUMAN_GATE_GRANTED','1000','codex'))
            with self.assertRaises(ValueError): s.project((h.ROOT/h.STATE).read_bytes(),ledger)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): s.update(d,{'verdict':'GREEN'},'1000')

if __name__=='__main__': unittest.main()
