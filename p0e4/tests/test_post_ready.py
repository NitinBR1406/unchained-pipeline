import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration.post_ready import reconcile_raw, route

ROOT = Path(__file__).resolve().parents[2]
RAW = json.loads((ROOT/'p0e4/evidence/target_v13/RAW_HASH.json').read_text())
BINDING = json.loads((ROOT/'p0e4/evidence/target_v13/AAKHRI_ISHQ_INPUT_BINDING.json').read_text())


class PostReady(unittest.TestCase):
    def test_current_real_raw_reconciles_but_audio_gate_remains(self):
        r = reconcile_raw(RAW, BINDING); p = route(r)
        self.assertEqual(r['raw_contract_status'], 'RAW_IDENTITY_HASH_RECONCILED')
        self.assertEqual(r['full_ingest_status'], 'BLOCKED_MISSING_AUTHORITATIVE_AUDIO')
        self.assertEqual(p['status'], 'WAITING_FOR_NITIN_AUDIO_SOURCE_BINDING')
        self.assertFalse(p['production_deployment_authorized']); self.assertFalse(p['publication_authorized'])

    def test_raw_hash_file_id_size_and_gate_drift_rejected(self):
        cases = [('raw_sha256', 'a'*64), ('raw_file_id', 'wrong'), ('raw_bytes', 1),
                 ('authoritative_audio', {'sha256':'a'*64}), ('real_e2e_allowed', True)]
        for key,value in cases:
            b=copy.deepcopy(BINDING);b[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):reconcile_raw(RAW,b)

    def test_source_mutation_rejected(self):
        raw=copy.deepcopy(RAW);raw['source_mutations']=1
        with self.assertRaises(ValueError):reconcile_raw(raw,BINDING)

    def test_authority_escalation_rejected(self):
        r=reconcile_raw(RAW,BINDING)
        with self.assertRaises(ValueError):route(r,production_deployment_authorized=True)
        with self.assertRaises(ValueError):route(r,publication_authorized=True)

    def test_deterministic(self):
        self.assertEqual(reconcile_raw(RAW,BINDING),reconcile_raw(RAW,BINDING))
        self.assertEqual(route(reconcile_raw(RAW,BINDING)),route(reconcile_raw(RAW,BINDING)))

if __name__ == '__main__': unittest.main()
