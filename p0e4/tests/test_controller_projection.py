import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller import project_v10 as p
from integration.contracts import digest
from control_plane.ledger import EventLedger

class ControllerProjectionTests(unittest.TestCase):
    def test_evidence_only_v10_and_gates_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger';path.write_bytes(p.PREFIX.read_bytes())
            ledger=EventLedger(str(path))
            acceptance={'status':'GREEN_SINGLE_HOST_READONLY_SLICE','real_codex_tasks_completed':2,
                        'deterministic_replay':True,'production_deployment_authorized':False,'publication_authorized':False}
            payload={'tested_sha':'a'*40,'ingested_at':'2026-09-18T21:00:00Z','acceptance':acceptance,
                     'evidence_refs':[{'uri':'TEST_ONLY','sha256':digest(b'test')} ]}
            ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
            before=json.loads(p.PARENT.read_bytes())
            state=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),lambda uri:b'test')
            self.assertEqual(state['state_version'],15)
            for key in ('authorizations','production_state','current_release'):
                self.assertEqual(state[key],before[key])
            self.assertEqual(state,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),lambda uri:b'test'))
            with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),lambda uri:b'changed')
            ledger.append(h.make_event('forbidden','HUMAN_GATE_GRANTED',payload['ingested_at'],'codex'))
            with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),lambda uri:b'test')

if __name__=='__main__':unittest.main()
