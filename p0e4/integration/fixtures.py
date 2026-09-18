"""Deterministic TEST_ONLY packages. No real Gemini/Claude result or human approval."""
from copy import deepcopy
from .contracts import canonical, digest, KINDS

AT = '2026-09-18T17:00:00Z'


def chain():
    blobs = {'fixture/raw': b'TEST_ONLY_RAW_NOT_MEDIA', 'fixture/audio': b'TEST_ONLY_AUDIO_NOT_MEDIA',
             'fixture/master': b'TEST_ONLY_OUTPUT_NOT_MEDIA', 'fixture/evidence': b'TEST_ONLY_EVIDENCE'}
    def asset(role, uri): return {'role': role, 'uri': uri, 'sha256': digest(blobs[uri])}
    raw, audio, output = asset('raw_video','fixture/raw'), asset('authoritative_audio','fixture/audio'), asset('master','fixture/master')
    evidence = [{'uri':'fixture/evidence','sha256':digest(blobs['fixture/evidence'])}]
    def envelope(kind, agent, inputs, payload):
        return {'schema':kind,'schema_version':1,'content_id':'TEST_ONLY_GOLDEN',
                'package_id':'TEST_ONLY_'+kind, 'created_at':AT,
                'producer':{'agent':agent,'model':None,'run_id':'TEST_ONLY_'+agent},
                'inputs':inputs,'evidence_refs':deepcopy(evidence),'payload':payload}
    creative = envelope(KINDS[0], 'TEST_ONLY_GEMINI', [raw,audio], {'edit_plan':{
        'duration_ms':10000, 'baseline_locked':True,'execution_mode':'RECOMMENDATION_ONLY',
        'segments':[{'start_ms':0,'end_ms':10000,'source_sha256':raw['sha256'],
                     'source_start_ms':0,'source_end_ms':10000,'performer_visible':True}],
        'effects':[]}})
    production = envelope(KINDS[1], 'TEST_ONLY_CLAUDE', deepcopy(creative['inputs']), {
        'creative_package_sha256':digest(canonical(creative)),
        'edit_plan_sha256':digest(canonical(creative['payload']['edit_plan'])),
        'outputs':[output], 'platforms':[{'platform':'youtube_hero','asset_sha256':output['sha256'],
                                        'title':'TEST_ONLY','caption':'TEST_ONLY'}]})
    qc = envelope(KINDS[2], 'TEST_ONLY_GEMINI_QC', [output], {
        'production_package_sha256':digest(canonical(production)), 'checked_assets':[output['sha256']],
        'verdict':'PASS', 'checks':{k:'PASS' for k in
            ('technical','look_match','full_motion','lipsync','audio','platform_safe_area','performance_rule')}})
    receipts = {digest(canonical(p)):deepcopy(p['producer']) for p in (creative,production,qc)}
    return creative, production, qc, blobs, receipts
