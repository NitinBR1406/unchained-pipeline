import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_plane.ledger import EventLedger
from integration import project_v09 as p
from integration.contracts import digest

class ProjectionTests(unittest.TestCase):
    def test_additive_replay_preserves_all_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger';path.write_bytes(p.PREFIX.read_bytes())
            ledger=EventLedger(str(path))
            payload={'tested_sha':'a'*40,'ingested_at':'2026-09-18T17:00:00Z',
                     'evidence_refs':[{'uri':'TEST_ONLY','sha256':digest(b'TEST_ONLY')}],
                     'status':'OFFLINE_VERIFIED_LIVE_E2E_BLOCKED','completed':[],'remaining':[]}
            ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
            parent=p.PARENT.read_bytes();before=json.loads(parent)
            state=p.project(parent,ledger,p.PREFIX.read_bytes(),lambda uri:b'TEST_ONLY')
            self.assertEqual(state['state_version'],14)
            self.assertEqual(state['authorizations'],before['authorizations'])
            self.assertEqual(state['production_state'],before['production_state'])
            self.assertEqual(state['p0e4']['final_video_binding'],before['p0e4']['final_video_binding'])
            self.assertFalse(state['current_release']['publish_ready'])
            self.assertEqual(state,p.project(parent,ledger,p.PREFIX.read_bytes(),lambda uri:b'TEST_ONLY'))
            with self.assertRaises(ValueError):p.project(parent,ledger,p.PREFIX.read_bytes(),lambda uri:b'TAMPER')
            with self.assertRaises(ValueError):p.project(parent+b' ',ledger,p.PREFIX.read_bytes(),lambda uri:b'TEST_ONLY')
            ledger.append(h.make_event('forbidden','HUMAN_GATE_GRANTED',payload['ingested_at'],'codex'))
            with self.assertRaises(ValueError):p.project(parent,ledger,p.PREFIX.read_bytes(),lambda uri:b'TEST_ONLY')

if __name__=='__main__':unittest.main()
