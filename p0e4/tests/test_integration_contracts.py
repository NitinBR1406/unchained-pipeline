import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration import contracts as c
from integration.fixtures import chain
from integration.existing_system import prepare, inventory


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.creative,self.production,self.qc,self.blobs,self.receipts = chain()

    def check(self):
        return c.validate_chain(self.creative,self.production,self.qc,self.blobs.__getitem__,self.receipts)

    def test_full_chain_and_deterministic_existing_wrapper(self):
        self.assertTrue(self.check())
        a,b=prepare(self.production),prepare(self.production)
        self.assertEqual(c.canonical(a),c.canonical(b))
        self.assertEqual(a['external_side_effect_count'],0)
        self.assertEqual(a['existing_system_draft']['status'],'ADAPTER_READY')
        self.assertEqual(inventory()['reused_entrypoint'],'unpipe.adapters.PackagingEngine.build')

    def test_untrusted_identity_cannot_prove_qc(self):
        self.receipts={}
        with self.assertRaises(ValueError): self.check()

    def test_schema_version_and_unknown_fields(self):
        for key,value in [('schema','UNKNOWN'),('schema_version',True),('schema_version',2),('created_at','2026-09-18'),('publish_approved',True)]:
            p=copy.deepcopy(self.creative);p[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): c.validate(p)

    def test_chain_tamper_cross_content_partial_qc(self):
        mutations=[lambda: self.production.update(content_id='OTHER'),
                   lambda: self.qc['payload'].update(production_package_sha256='0'*64),
                   lambda: self.qc['payload'].update(checked_assets=['a'*64]),
                   lambda: self.qc['producer'].update(agent=self.production['producer']['agent']),
                   lambda: self.qc['payload']['checks'].update(lipsync='UNKNOWN'),
                   lambda: self.blobs.update({'fixture/raw':b'CHANGED'}),
                   lambda: self.blobs.update({'fixture/master':b'CHANGED'}),
                   lambda: self.production['payload'].update(edit_plan_sha256='0'*64),
                   lambda: self.qc.update(created_at='2025-01-01T00:00:00Z')]
        for mutation in mutations:
            self.setUp();mutation()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): self.check()

    def test_80_percent_exact_boundary_and_overlap(self):
        plan=self.creative['payload']['edit_plan'];segment=plan['segments'][0]
        segment.update(end_ms=8000,source_end_ms=8000)
        plan['segments'].append(dict(segment,start_ms=8000,end_ms=10000,source_start_ms=8000,source_end_ms=10000,performer_visible=False))
        c.validate(self.creative)
        segment.update(end_ms=7999,source_end_ms=7999)
        plan['segments'][1].update(start_ms=7999,source_start_ms=7999)
        with self.assertRaisesRegex(ValueError,'80_PERCENT'): c.validate(self.creative)
        segment.update(end_ms=8001,source_end_ms=8001)
        with self.assertRaisesRegex(ValueError,'gap/overlap'): c.validate(self.creative)

    def test_edit_bounds_visibility_obscuring_effects(self):
        for change in ({'duration_ms':True},{'duration_ms':10001},{'execution_mode':'EXECUTE'},
                       {'effects':[{'kind':'flash','start_ms':0,'end_ms':1,'intensity_milli':1000,'performer_obscured':True}]}):
            p=copy.deepcopy(self.creative);p['payload']['edit_plan'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):c.validate(p)

    def test_missing_audio_or_nonvideo_output_fails(self):
        self.creative['inputs'].pop()
        with self.assertRaisesRegex(ValueError, 'RAW/audio'): c.validate(self.creative)
        self.production['payload']['outputs'][0]['role'] = 'authoritative_audio'
        with self.assertRaisesRegex(ValueError, 'rendered video'): c.validate(self.production)

    def test_path_escape_denied(self):
        resolve=c.file_resolver(Path(__file__).parent)
        with self.assertRaises(ValueError):resolve('../integration/contracts.py')

if __name__=='__main__':unittest.main()
