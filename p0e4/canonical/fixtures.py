"""Synthetic transport fixtures, never actual Gemini/Claude execution or approval."""
from integration.fixtures import chain,AT
from integration.contracts import canonical,digest
from .validator import TABLES
from .bridge import assemble


def fixture():
    creative,_,_,blobs,_=chain()
    records={k:[] for k in TABLES}
    def row(**kw):return dict(kw,evidence_ids=['ev:test'])
    records['CAMPAIGNS']=[row(campaign_id='campaign:test',name='INTEGRATION_TEST_INPUT',objective='Test attribution, no actual growth values')]
    records['CONTENT_MASTER']=[row(content_id=creative['content_id'],campaign_id='campaign:test',song_id='song:test',title='INTEGRATION_TEST_INPUT',track_type='COVER',master_asset_id=None,isrc_code=None,status='INTEGRATION_TEST_INPUT')]
    for i,a in enumerate(creative['inputs']):
        records['ASSETS'].append(row(asset_id=f'asset:{i}',content_id=creative['content_id'],role='INTEGRATION_TEST_INPUT',uri=a['uri'],sha256=a['sha256'],authority='INTEGRATION_TEST_INPUT',binding_evidence_id=None))
    records['AGENT_EVIDENCE']=[row(agent_id='agent:test',agent_role='GEMINI_INTELLIGENCE',source_agent_name=creative['producer']['agent'],model_id=creative['producer']['model'],run_id=creative['producer']['run_id'],observed_at=AT,authenticated_receipt_id=None)]
    records['HYPOTHESES']=[row(hypothesis_id='hypothesis:test',content_id=creative['content_id'],statement='TEST_ONLY vocal-first hook improves retention',predicted_metric='retention',falsification_rule='No improvement versus control')]
    records['CREATIVE_INTELLIGENCE']=[row(intelligence_id='intelligence:test',content_id=creative['content_id'],source_package_id=creative['package_id'],hypothesis_id='hypothesis:test',recommendation='TEST_ONLY recommendation',source_package_sha256=digest(canonical(creative)),agent_id='agent:test',created_at=AT)]
    records['EXPERIMENTS']=[row(experiment_id='experiment:test',campaign_id='campaign:test',hypothesis_id='hypothesis:test',tested_variable='opening_hook',variant_id='variant:test',control_variant_id=None,primary_metric='retention',status='PLANNED')]
    records['DERIVATIVES']=[row(derivative_id='derivative:test',content_id=creative['content_id'],source_asset_id='asset:0',asset_id=None,hypothesis_id='hypothesis:test',experiment_id='experiment:test',kind='CLIP',start_ms=0,end_ms=10000,aspect_ratio='9:16',hook='TEST_ONLY vocal opening')]
    records['PLATFORM_PACKAGES']=[row(package_id='package:test',derivative_id='derivative:test',platform='youtube_shorts',title='TEST_ONLY title',caption='TEST_ONLY caption',hashtags=['#TestOnly'],keywords=['test'],cta='TEST_ONLY save',thumbnail_asset_id=None,poster_asset_id=None,scheduled_at=None,schedule_timezone='Europe/Amsterdam',schedule_version=1,status='DRAFT')]
    records['PRODUCTION']=[row(production_id='production:test',content_id=creative['content_id'],derivative_id='derivative:test',creative_package_sha256=digest(canonical(creative)),edit_plan_sha256=digest(canonical(creative['payload']['edit_plan'])),executor_agent_id='agent:test',status='NOT_DISPATCHED',output_asset_id=None)]
    records['PUBLICATION']=[row(publication_id='publication:test',package_id='package:test',platform='youtube_shorts',platform_post_id=None,published_at=None,status='NOT_PUBLISHED',receipt_evidence_id=None,attribution_code=None)]
    evidence=[dict(evidence_id='ev:test',**creative['evidence_refs'][0])]
    return assemble(creative,records,evidence,AT,blobs.__getitem__),creative,blobs
