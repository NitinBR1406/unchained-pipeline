import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import project_v163 as p
class ProjectionTests(unittest.TestCase):
    def test_frozen_parent(self):
        self.assertEqual(p.digest(p.PARENT.read_bytes()),p.PARENT_SHA)
    def test_human_gate_escalation_rejected(self):
        a=dict(tested_sha='a'*40,status=p.STATUS,refs={},production_deployment_authorized=True,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')
        with self.assertRaisesRegex(ValueError,'authority escalation'):p.validate(a,lambda _:b'')
    def test_evidence_replay_when_registered(self):
        out=p.ROOT/'p0e4/evidence/resolve_studio_v163'
        if not (out/'ENGINEERING_EVENT_LEDGER.jsonl').exists():return
        state=p.project(p.PARENT.read_bytes(),p.EventLedger(str(out/'ENGINEERING_EVENT_LEDGER.jsonl')),p.file_resolver(p.ROOT))
        self.assertEqual(p.bytes_json(state),(out/'UNCHAINED_MASTER_PROJECT_STATE_V16_3.json').read_bytes())
        self.assertFalse(state['authorizations']['PUBLICATION_AUTHORIZED'])
        self.assertEqual(state['state_version'],29)
if __name__=='__main__':unittest.main()
