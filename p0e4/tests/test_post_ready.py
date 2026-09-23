import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration.post_ready import reconcile_raw, route, bind_authoritative_audio

ROOT = Path(__file__).resolve().parents[2]
RAW = json.loads((ROOT/'p0e4/evidence/target_v13/RAW_HASH.json').read_text())
BINDING = json.loads((ROOT/'p0e4/evidence/target_v13/AAKHRI_ISHQ_INPUT_BINDING.json').read_text())
EVENT={'event_id':'AKI_AUTHORITATIVE_AUDIO_BINDING_V01','event_type':'NITIN_AUTHORITATIVE_AUDIO_BINDING',
       'selected_basename':'AAKHRI ISHQ MASTER 2.wav','excluded_substitutes':['AAKHRI ISHQ MASTER 1.wav'],
       'source_statement':'explicit'}
OBS={'path':'/x/Aakhri Ishq/AAKHRI ISHQ MASTER 2.wav','basename':'AAKHRI ISHQ MASTER 2.wav',
     'size_bytes':61749398,'mtime_ns':1776231984000000000,
     'sha256':'670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2',
     'unchanged_during_read':True,'technical':{'format':'PCM_WAVE','channels':2,'sample_rate_hz':48000,
     'sample_width_bytes':3,'frames':10291202,'duration_seconds':214.40004166666668,
     'validation':'full bytes SHA256 read; WAV header and frame count parsed'}}


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

    def test_exact_audio_binding_and_route(self):
        bound=bind_authoritative_audio(reconcile_raw(RAW,BINDING),EVENT,OBS)
        self.assertEqual(bound['authoritative_audio']['sha256'],OBS['sha256'])
        self.assertEqual(route(bound)['status'],'AUDIO_BOUND_WAITING_FOR_PRODUCTION_DEPLOYMENT_AUTHORIZATION')
        self.assertFalse(route(bound)['production_deployment_authorized'])

    def test_audio_substitutions_fail_closed(self):
        for field,value in [('basename','AAKHRI ISHQ MASTER 1.wav'),('path','/x/Aakhri Ishq/AAKHRI ISHQ VOCALS.wav'),
                            ('sha256','bad'),('unchanged_during_read',False)]:
            obs=copy.deepcopy(OBS);obs[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                bind_authoritative_audio(reconcile_raw(RAW,BINDING),EVENT,obs)

if __name__ == '__main__': unittest.main()
