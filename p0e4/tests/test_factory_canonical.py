from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.fixtures import fixture
from canonical.validator import validate,attribution
from canonical.adapter import shadow,readback,dispatch
from integration.contracts import canonical,digest
ROOT=Path(__file__).resolve().parents[2]

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.d,self.c,self.b=fixture()
        self.m=json.loads((ROOT/'p0e4/canonical/CLAUDE_SHEET_FIELD_MAP_V01.json').read_text())
        self.s=json.loads((ROOT/'p0e4/evidence/canonical_v15/LIVE_SHEET_SNAPSHOT.json').read_text())
    def resolve(self,uri):return self.b[uri] if uri in self.b else (ROOT/uri).read_bytes()
    def check(self):return validate(self.d,self.c,self.resolve)
    def test_expected_projection_and_roundtrip(self):
        r=shadow(self.d,self.c,self.m,self.s,self.resolve)
        self.assertEqual(r['rows'][0]['cells'],{'youtube_title':'TEST_ONLY title','caption_youtube':'TEST_ONLY caption','hashtags_youtube':'#TestOnly'})
        self.assertEqual(set(r['rows'][0]['controls'].values()),{'FALSE'})
        self.assertEqual(readback(r,self.m,self.s,self.resolve),self.d)
        self.assertEqual(r,shadow(self.d,self.c,self.m,self.s,self.resolve))
        r['rows'][0]['cells']['youtube_title']='drift'
        with self.assertRaises(ValueError):readback(r,self.m,self.s,self.resolve)
    def test_unknown_missing_types_versions_and_ids(self):
        for mutate in [lambda d:d.update(unrecognized=1),lambda d:d.pop('DERIVATIVES'),lambda d:d['PLATFORM_PACKAGES'][0].update(caption=3),lambda d:d.update(schema_version=2),lambda d:d['ASSETS'].append(deepcopy(d['ASSETS'][0])),lambda d:d['DERIVATIVES'][0].update(content_id='missing')]:
            self.d,self.c,self.b=fixture();mutate(self.d)
            with self.assertRaises(ValueError):self.check()
    def test_platform_sha_approval_and_performance(self):
        for mutate in [lambda d:d['PUBLICATION'][0].update(platform='tiktok'),lambda d:d.update(source_package_sha256='0'*64),lambda d:d['governance'].update(publication_authorized=True),lambda d:d['ASSETS'][0].update(sha256='0'*64),lambda d:d['ASSETS'][0].update(authority='NITIN_BOUND')]:
            self.d,self.c,self.b=fixture();mutate(self.d)
            with self.assertRaises(ValueError):self.check()
        self.d,self.c,self.b=fixture();self.c['payload']['edit_plan']['segments'][0]['performer_visible']=False
        self.d['source_package_sha256']=digest(canonical(self.c))
        with self.assertRaisesRegex(ValueError,'80_PERCENT'):self.check()
    def test_unmapped_header_drift_and_live_execution_block(self):
        with self.assertRaisesRegex(ValueError,'UNMAPPED'):shadow(self.d,self.c,self.m,self.s,self.resolve,required_fields=['cta'])
        self.s['sheets'][0]['headers'][6]='renamed'
        with self.assertRaises(ValueError):shadow(self.d,self.c,self.m,self.s,self.resolve)
        with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):dispatch()
    def test_attribution_and_no_invented_values(self):
        self.check();trace=attribution(self.d,'publication:test')
        self.assertEqual(trace['campaign_id'],'campaign:test');self.assertEqual(trace['hypothesis_id'],'hypothesis:test');self.assertEqual(trace['experiment_id'],'experiment:test')
        for t in ['ANALYTICS','MONETIZATION','AUDIENCE_GROWTH','BUSINESS_FUNNEL']:self.assertEqual(self.d[t],[])
    def test_missing_editorial_not_silently_generated(self):
        self.d['PLATFORM_PACKAGES'][0].pop('cta')
        with self.assertRaises(ValueError):self.check()
    def test_exact_performance_boundary(self):
        for duration,ok in [(8000,True),(7900,False)]:
            self.d,self.c,self.b=fixture();plan=self.c['payload']['edit_plan']
            first=plan['segments'][0];first['end_ms']=duration;first['source_end_ms']=duration
            plan['segments'].append(dict(first,start_ms=duration,end_ms=10000,source_start_ms=duration,source_end_ms=10000,performer_visible=False))
            self.d['source_package_sha256']=digest(canonical(self.c))
            self.d['CREATIVE_INTELLIGENCE'][0]['source_package_sha256']=self.d['source_package_sha256']
            self.d['PRODUCTION'][0]['creative_package_sha256']=self.d['source_package_sha256']
            self.d['PRODUCTION'][0]['edit_plan_sha256']=digest(canonical(plan))
            if ok:self.check()
            else:
                with self.assertRaisesRegex(ValueError,'80_PERCENT'):self.check()
    def test_business_attribution_and_unknown_measurement(self):
        self.d['BUSINESS_FUNNEL']=[dict(funnel_id='funnel:test',publication_id='publication:test',campaign_id='campaign:test',lead_id='lead:test',booking_id=None,partnership_id=None,stage='UNKNOWN',attribution_method='UNATTRIBUTED',attribution_code=None,occurred_at=self.d['created_at'],source='TEST_ONLY',evidence_ids=['ev:test'])]
        self.d['MONETIZATION']=[dict(revenue_id='revenue:test',publication_id='publication:test',funnel_id='funnel:test',campaign_id='campaign:test',kind='STREAM',amount_minor=None,currency='EUR',quantity=None,gross_or_net='UNKNOWN',cost_minor=None,recognized_at=None,attribution_status='UNATTRIBUTED',source='TEST_ONLY',external_reference=None,evidence_ids=['ev:test'])]
        self.check()
        self.d['MONETIZATION'][0]['publication_id']='unknown'
        with self.assertRaises(ValueError):self.check()
    def test_stale_map_and_evidence_drift(self):
        self.m['schema_version']=2
        with self.assertRaises(ValueError):shadow(self.d,self.c,self.m,self.s,self.resolve)
        self.m['schema_version']=1;self.m['fields'][0]['evidence_refs'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):shadow(self.d,self.c,self.m,self.s,self.resolve)

    def test_live_column_conflict_blocks_tiktok(self):
        self.d['PLATFORM_PACKAGES'][0]['platform']='tiktok'
        self.d['PUBLICATION'][0]['platform']='tiktok'
        with self.assertRaisesRegex(ValueError,'UNMAPPED'):
            shadow(self.d,self.c,self.m,self.s,self.resolve,required_fields=['caption','hashtags'])

    def test_formula_like_text_is_never_executed(self):
        self.d['PLATFORM_PACKAGES'][0]['title']='=HYPERLINK("test")'
        r=shadow(self.d,self.c,self.m,self.s,self.resolve)
        self.assertEqual(r['rows'][0]['cells']['youtube_title'],'=HYPERLINK("test")')
        self.assertEqual(r['external_writes'],0)

if __name__=='__main__':unittest.main()
