import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import project_v164 as p
from integration.contracts import file_resolver, digest
from integration.project_v09 import bytes_json


class ProjectionTests(unittest.TestCase):
    def project(self, payload_change=None, resolver=None):
        records=p.EventLedger(str(p.OUT/'ENGINEERING_EVENT_LEDGER.jsonl')).read_all()
        event=records[-1]
        payload=event['inputs']
        if payload_change:
            payload_change(payload)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl'
            path.write_bytes(p.PREFIX.read_bytes())
            ledger=p.EventLedger(str(path))
            ledger.append(p.h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',event['timestamp'],'codex',inputs=payload))
            return p.project(p.PARENT.read_bytes(),ledger,resolver or file_resolver(p.ROOT))

    def test_replay_and_gates(self):
        state=self.project()
        self.assertEqual(bytes_json(state),(p.OUT/'UNCHAINED_MASTER_PROJECT_STATE_V16_4.json').read_bytes())
        self.assertEqual(state['state_version'],30)
        self.assertEqual(state['authorizations'],json.loads(p.PARENT.read_bytes())['authorizations'])
        self.assertFalse(state['current_release']['publish_ready'])

    def test_evidence_tamper_rejected(self):
        resolver=file_resolver(p.ROOT)
        with self.assertRaises(ValueError):
            self.project(resolver=lambda uri:resolver(uri)+b' ')

    def test_unexpected_authority_rejected(self):
        with self.assertRaises(ValueError):
            self.project(lambda payload:payload.update(publication_authorized=True))

    def test_rehashed_fake_execution_rejected(self):
        resolver=file_resolver(p.ROOT)
        uri=str((p.OUT/'STUDY_REQUEST.json').relative_to(p.ROOT))
        study=json.loads(resolver(uri));study['render_started']=True
        bad=bytes_json(study)
        def change(payload):
            for ref in payload['evidence_refs']:
                if ref['uri']==uri:ref['sha256']=digest(bad)
        with self.assertRaises(ValueError):
            self.project(change,lambda x:bad if x==uri else resolver(x))


if __name__=='__main__':unittest.main()
