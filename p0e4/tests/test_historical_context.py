from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.historical_context import validate, context_for
from integration.contracts import canonical, digest


def fixture():
    excerpts=[dict(id='E1',page=1,text='TEST_ONLY creative hypothesis',
                   sha256=digest(b'TEST_ONLY creative hypothesis'))]
    package=dict(schema='GEMINI_HISTORICAL_CONTEXT_PACKAGE',schema_version=1,
        classification='HISTORICAL_UNVERIFIED_CONTEXT',scope='UNCHAINED_NITIN',
        provenance=dict(conversation_url='https://gemini.google.com/app/7c9afdcb27030bcb',
            conversation_title='YouTube-groeistrategie unchainednitin',account_match_observed=True,
            account_sha256='a'*64,source_snapshot_sha256='b'*64,
            observed_at='2026-09-19T00:00:00Z',snapshot_pages=192),
        excerpts_sha256=digest(canonical(excerpts)),
        boundaries=dict(nitin_approval=False,rights_clearance=False,current_facts=False,
            current_qc=False,publication_authorized=False,production_deployment_authorized=False,
            fresh_qc_must_review_actual_asset=True,first_real_poster='PAUSED_BY_NITIN'),
        insights=[dict(id='I1',category='hooks',summary='TEST_ONLY performance-first opening',
            status='HISTORICAL_HYPOTHESIS',fresh_validation_required=True,evidence_ids=['E1'])])
    return package,excerpts


class HistoricalContextTests(unittest.TestCase):
    def test_creative_context_cannot_inherit_approval(self):
        p,e=fixture();r=context_for(p,e,'CREATIVE_INTELLIGENCE')
        self.assertFalse(r['approval_authority']);self.assertFalse(r['instructions_from_source_executable'])
        self.assertTrue(r['fresh_validation_required'])

    def test_independent_qc_never_receives_history_or_verdict(self):
        p,e=fixture();r=context_for(p,e,'INDEPENDENT_QC')
        self.assertEqual(r['historical_context'],[])
        self.assertFalse(r['historical_verdicts_allowed']);self.assertTrue(r['actual_asset_sha256_required'])

    def test_authority_freshness_and_source_tampering_rejected(self):
        for key in ('nitin_approval','rights_clearance','current_facts','current_qc',
                    'publication_authorized','production_deployment_authorized'):
            p,e=fixture();p['boundaries'][key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):validate(p,e)
        p,e=fixture();e[0]['text']='changed'
        with self.assertRaises(ValueError):validate(p,e)
        p,e=fixture();p['insights'][0]['evidence_ids']=['missing']
        with self.assertRaises(ValueError):validate(p,e)
        p,e=fixture();p['insights'][0]['fresh_validation_required']=False
        with self.assertRaises(ValueError):validate(p,e)


if __name__=='__main__':unittest.main()
