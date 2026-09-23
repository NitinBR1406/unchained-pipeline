import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from p0e4.catalog.batch_semantics import apply_batch
EVENT_PATH=ROOT/'p0e4/evidence/catalog_semantic_events/NITIN_BATCH_1_5_MASHUPS_SEMANTIC_CONFIRMATION_V01.json'
BASE=json.loads(subprocess.check_output(['git','show','f1f9eff:p0e4/evidence/catalog_minimal_review_v01/NITIN_MINIMAL_SEMANTIC_REVIEW_V01.json'],cwd=ROOT,text=True))
EVENT=json.loads(EVENT_PATH.read_text())
class BatchTests(unittest.TestCase):
 def test_exact_semantics_and_protected_fields(self):
  projected,receipt,queues=apply_batch(BASE,EVENT);old={r['candidate_id']:r for r in BASE['rows']};items={i['candidate_id']:i for i in EVENT['items']}
  self.assertEqual(len(items),67)
  for row in projected['rows']:
   if row['candidate_id'] not in items:self.assertEqual(row,old[row['candidate_id']]);continue
   for k,v in row.items():
    if k in ('question','semantic_evidence_event_id'):continue
    self.assertEqual(v,items[row['candidate_id']]['set_fields'].get(k,old[row['candidate_id']][k]))
  self.assertEqual(queues['NITIN_VOCAL_QUEUE_V01']['count'],31)
  self.assertEqual(queues['MUSIC_AND_VOCALS_READY_V01']['count'],36)
  bypath={r['path'].strip():r for r in projected['rows']}
  self.assertEqual(bypath['Aye Khuda']['TYPE'],'ORIGINAL');self.assertEqual(bypath['Dooriyan']['TYPE'],'ORIGINAL');self.assertEqual(bypath['DHUN']['TYPE'],'UNKNOWN')
  self.assertNotEqual(bypath['Songs voor 2022/Chunar']['candidate_id'],bypath['Chunar 2025']['candidate_id'])
 def test_expected_totals_disagreement_visible(self):
  _,r,_=apply_batch(BASE,EVENT)
  self.assertFalse(r['all_checks_passed']);self.assertEqual(r['observed_control_totals']['regular_vocals_yes'],36)
  self.assertEqual(r['observed_control_totals']['regular_vocals_no'],27)
  self.assertEqual(set(r['control_total_mismatches']),{'regular_vocals_yes','regular_vocals_no','vocal_pending'})
 def test_duplicate_id_rejected(self):
  e=copy.deepcopy(EVENT);e['items'].append(e['items'][0])
  with self.assertRaises(ValueError):apply_batch(BASE,e)
 def test_wrong_name_rejected(self):
  e=copy.deepcopy(EVENT);e['items'][0]['input_name']='Other'
  with self.assertRaises(ValueError):apply_batch(BASE,e)
 def test_unspecified_field_rejected(self):
  e=copy.deepcopy(EVENT);e['items'][0]['set_fields']['LYRICS_READY']='YES'
  with self.assertRaises(ValueError):apply_batch(BASE,e)
 def test_type_conflict_preserved(self):
  b=copy.deepcopy(BASE);r=next(r for r in b['rows'] if r['path']=='Arijit Dance Mashup');r['TYPE']='MEDLEY'
  p,v,_=apply_batch(b,EVENT)
  self.assertEqual(next(r for r in p['rows'] if r['path']=='Arijit Dance Mashup')['TYPE'],'MEDLEY');self.assertEqual(len(v['type_conflicts']),1)
 def test_deterministic_and_no_input_mutation(self):
  b=copy.deepcopy(BASE);e=copy.deepcopy(EVENT);first=apply_batch(b,e)
  self.assertEqual(first,apply_batch(b,e));self.assertEqual(b,BASE);self.assertEqual(e,EVENT)
if __name__=='__main__':unittest.main()
