import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller import project_v14 as p
from integration.contracts import digest, canonical
from control_plane.ledger import EventLedger
import test_historical_context


class V14ProjectionTests(unittest.TestCase):
    def fixture(self):
        package,excerpts=test_historical_context.fixture()
        blobs={'package':canonical(package),'excerpts':canonical(excerpts)}
        refs={k:{'uri':k,'sha256':digest(v)} for k,v in blobs.items()}
        a=dict(status='HISTORICAL_CONTEXT_ACCEPTED_PRODUCTION_BLOCKED',deterministic_replay=True,
            real_media_qc_proven=False,durable_gui_dispatcher_proven=False,first_real_poster='PAUSED_BY_NITIN',
            production_e2e_status='BLOCKED_NOT_GREEN',blocked_tasks=['TEST_ONLY_GATE'],
            production_deployment_authorized=False,publication_authorized=False,historical_context_refs=refs)
        return blobs,a

    def project(self,blobs,a,extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes())
            ledger=EventLedger(str(path))
            payload=dict(tested_sha='a'*40,ingested_at='2026-09-18T22:30:00Z',acceptance=a,
                evidence_refs=[{'uri':k,'sha256':digest(v)} for k,v in blobs.items()])
            ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',payload['ingested_at'],'codex',inputs=payload))
            if extra:ledger.append(h.make_event('forbidden',extra,payload['ingested_at'],'codex'))
            first=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),blobs.__getitem__)
            self.assertEqual(first,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),blobs.__getitem__))
            return first

    def test_replay_and_frozen_authority_preserved(self):
        blobs,a=self.fixture();state=self.project(blobs,a);parent=json.loads(p.PARENT.read_bytes())
        self.assertEqual(state['state_version'],19)
        for key in ('authorizations','production_state','current_release'):
            self.assertEqual(state[key],parent[key])
        self.assertEqual(state['p0e4']['verdict'],'BLOCKED_NOT_GREEN')

    def test_scope_escalation_and_approval_event_rejected(self):
        for key,value in [('real_media_qc_proven',True),('durable_gui_dispatcher_proven',True),
                          ('publication_authorized',True),('blocked_tasks',[])]:
            blobs,a=self.fixture();a[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.project(blobs,a)
        blobs,a=self.fixture()
        with self.assertRaises(ValueError):self.project(blobs,a,'HUMAN_GATE_GRANTED')

    def test_historical_authority_escalation_rejected(self):
        blobs,a=self.fixture()
        package=json.loads(blobs['package']);package['boundaries']['current_qc']=True
        blobs['package']=canonical(package)
        a['historical_context_refs']['package']['sha256']=digest(blobs['package'])
        with self.assertRaises(ValueError):self.project(blobs,a)


if __name__=='__main__':unittest.main()
