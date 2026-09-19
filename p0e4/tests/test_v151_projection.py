import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller import project_v151 as p
from canonical.fixtures import fixture
from canonical.adapter import shadow
from canonical.coverage import assess
from integration.contracts import canonical,digest
from control_plane.ledger import EventLedger
ROOT=Path(__file__).resolve().parents[2]
class Projection(unittest.TestCase):
 def test_replay_frozen_and_fail_closed(self):
  data,creative,blobs=fixture()
  field_map=json.loads((ROOT/'p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V01.json').read_text());snapshot=json.loads((ROOT/'p0e4/evidence/canonical_v15/LIVE_SHEET_SNAPSHOT.json').read_text())
  def resolve(uri):return blobs[uri] if uri in blobs else (ROOT/uri).read_bytes()
  result=shadow(data,creative,field_map,snapshot,resolve)
  for k,v in [('shadow',result),('field_map',field_map),('snapshot',snapshot)]:blobs[k]=canonical(v)
  refs={k:dict(uri=k,sha256=digest(blobs[k])) for k in ['shadow','field_map','snapshot']}
  a=dict(always_on_dispatcher_proven=False,coverage=assess(data,creative,field_map,snapshot,resolve),status='MAPPING_COVERAGE_SHADOW_ACCEPTED_EXECUTION_BLOCKED',deterministic_replay=True,real_media_qc_proven=False,durable_gui_dispatcher_proven=False,first_real_poster='PAUSED_BY_NITIN',production_e2e_status='BLOCKED_NOT_GREEN',blocked_tasks=['TEST_GATE'],shadow_refs=refs,live_cutover_authorized=False,live_adapter_proven=False,production_deployment_authorized=False,publication_authorized=False)
  for escalation in [False,True]:
   a['live_cutover_authorized']=escalation
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(path))
    inputs=dict(tested_sha='a'*40,ingested_at='2026-09-19T00:00:00Z',acceptance=a,evidence_refs=list(refs.values()))
    ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED',inputs['ingested_at'],'codex',inputs=inputs))
    if escalation:
     with self.assertRaises(ValueError):p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve)
    else:
     s=p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve)
     self.assertEqual(s,p.project(p.PARENT.read_bytes(),ledger,p.PREFIX.read_bytes(),resolve));self.assertEqual(s['state_version'],21)
     parent=json.loads(p.PARENT.read_bytes())
     for k in ['authorizations','production_state','current_release']:self.assertEqual(s[k],parent[k])
if __name__=='__main__':unittest.main()
