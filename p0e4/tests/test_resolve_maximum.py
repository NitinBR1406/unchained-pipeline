import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve.adapter import ResolveAdapter,MATRIX
from catalog.review import technical_review
from integration.contracts import canonical,digest,file_resolver
from controller import project_v162 as p
from control_plane.ledger import EventLedger
import handoff as h
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'p0e4/evidence/resolve_max_v162'
def fixture():
 f=json.loads((OUT/'SYNTHETIC_INPUT.json').read_bytes());b={k:v.encode() for k,v in f['blobs_utf8'].items()};return f,b

def compile(f,b):return ResolveAdapter().compile(f['canonical'],f['creative'],f['operations'],f['finishing'],b.__getitem__)
class Maximum(unittest.TestCase):
 def test_determinism_full_fields_and_capability_boundary(self):
  f,b=fixture();plan=compile(f,b);self.assertEqual(plan,json.loads((OUT/'MASTER_FINISHING_PLAN.json').read_bytes()));self.assertEqual(canonical(plan),canonical(compile(f,b)))
  self.assertEqual(len(plan['base']['jobs'][0]['canonical_groups']),14)
  self.assertEqual(plan['finishing'],f['finishing']);self.assertEqual(len(MATRIX['classes']),5)
  self.assertTrue(all(c['effective_route']=='UNSUPPORTED_FAIL_CLOSED' and c['exact_callable_method'] is None for c in plan['capability_routes']))
  with self.assertRaises(ValueError):ResolveAdapter().execute(plan)
 def test_no_silent_look_audio_or_unknown_field_changes(self):
  for mutate in (lambda f:f['finishing']['color_look'].update(mode='AUTO_GRADE'),lambda f:f['finishing']['audio_sync'].update(gain_millidb=1),lambda f:f['finishing']['audio_sync'].update(preserve_rate=False),lambda f:f['finishing'].update(approval=True),lambda f:f['finishing']['audio_sync'].update(source_sha256='0'*64),lambda f:f['finishing']['audio_sync'].update(offset_samples=float('nan'))):
   f,b=fixture();mutate(f)
   with self.assertRaises(ValueError):compile(f,b)
 def test_lyric_bounds_duplicate_and_evidence(self):
  for mutate in (lambda f:f['finishing']['lyric_cues'][0].update(end_frame_exclusive=99999),lambda f:f['finishing']['lyric_cues'][0]['emphasis_spans'][0].update(end_character_exclusive=99),lambda f:f['finishing']['lyric_cues'].append(copy.deepcopy(f['finishing']['lyric_cues'][0])),lambda f:f['operations']['operations'][0]['evidence_ref'].update(sha256='0'*64)):
   f,b=fixture();mutate(f)
   with self.assertRaises(ValueError):compile(f,b)
 def test_qc_binds_whole_finishing_plan_and_rework(self):
  f,b=fixture();plan=compile(f,b);b['candidate']=b'TEST_ONLY';out=dict(uri='candidate',sha256=digest(b['candidate']))
  from resolve.plan import QC_CHECKS
  obs=dict(plan_sha256=digest(canonical(plan['base'])),output_sha256=out['sha256'],checked_at='2026-09-19T16:00:00Z',reviewer=dict(agent='TEST_ONLY_QC',model=None,run_id='TEST_ONLY'),checks={k:'PASS' for k in QC_CHECKS},evidence_refs=f['creative']['evidence_refs'])
  review=dict(finishing_plan_sha256=digest(canonical(plan)),base_observations=obs,finishing_checks=dict(lyric_text_exactness='UNKNOWN',audio_source_and_sample_offset='PASS',color_baseline_preserved='PASS'))
  r=ResolveAdapter().qc_rework(plan,out,review,b.__getitem__);self.assertEqual(r['status'],'REWORK_REQUIRED');self.assertFalse(r['authenticated_qc_proven'])
  review['finishing_plan_sha256']='0'*64
  with self.assertRaises(ValueError):ResolveAdapter().qc_rework(plan,out,review,b.__getitem__)
 def test_catalog_is_independent_and_immutable(self):
  inv=json.loads((ROOT/'p0e4/evidence/catalog_bootstrap_v01/CATALOG_INVENTORY_V01.json').read_bytes());before=canonical(inv)
  review=technical_review(inv);self.assertEqual(canonical(inv),before);self.assertEqual(review,json.loads((OUT/'CATALOG_TECHNICAL_REVIEW_QUEUE.json').read_bytes()))
  self.assertEqual(len(review['tasks']),92);self.assertTrue(all(t['candidate_hints_only'] for t in review['tasks']))
 def test_projection_replay_and_escalation(self):
  def ref(path):return dict(uri=str(path.relative_to(ROOT)),sha256=digest(path.read_bytes()))
  refs=dict(fixture=ref(OUT/'SYNTHETIC_INPUT.json'),plan=ref(OUT/'MASTER_FINISHING_PLAN.json'),inventory=ref(ROOT/'p0e4/evidence/catalog_bootstrap_v01/CATALOG_INVENTORY_V01.json'),catalog_review=ref(OUT/'CATALOG_TECHNICAL_REVIEW_QUEUE.json'))
  raw=json.dumps(dict(tested_sha='a'*40,passed=1,total=1,tracked_worktree_clean=True,prior_manifests=[{'pass':True}])).encode();refs['regression']=dict(uri='synthetic-regression',sha256=digest(raw))
  resolve=lambda u:raw if u=='synthetic-regression' else file_resolver(ROOT)(u)
  a=dict(tested_sha='a'*40,status='MASTER_FINISHING_DESIGN_ACCEPTED_EXECUTION_BLOCKED',refs=refs,resolve_execution_proven=False,production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'ledger';path.write_bytes(p.PREFIX.read_bytes());ledger=EventLedger(str(path));ledger.append(h.make_event(p.EVENT_ID,'EVIDENCE_REGISTERED','2026-09-19T16:00:00Z','codex',inputs=dict(ingested_at='2026-09-19T16:00:00Z',evidence_refs=list(refs.values()),acceptance=a)))
   s=p.project(p.PARENT.read_bytes(),ledger,resolve);self.assertEqual(s['state_version'],28);self.assertEqual(s,p.project(p.PARENT.read_bytes(),ledger,resolve))
   for k in ('authorizations','production_state','current_release'):self.assertEqual(s[k],json.loads(p.PARENT.read_bytes())[k])
  a['publication_authorized']=True
  with self.assertRaises(ValueError):p.validate(a,resolve)
if __name__=='__main__':unittest.main()
