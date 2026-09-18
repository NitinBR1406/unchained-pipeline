"""Historical strategy is untrusted context, never an approval or QC receipt."""
from .contracts import require, digest, canonical, sha, text, timestamp

SCHEMA = 'GEMINI_HISTORICAL_CONTEXT_PACKAGE'
CATEGORIES = {'growth', 'audience', 'hooks', 'formats', 'editing_effects',
              'visual_treatment', 'platform', 'posting', 'experiments', 'provenance'}


def validate(package, excerpts):
    require(package['schema'] == SCHEMA and type(package['schema_version']) is int
            and package['schema_version'] == 1, 'historical schema')
    require(package['classification'] == 'HISTORICAL_UNVERIFIED_CONTEXT', 'history is not current evidence')
    require(package['scope'] == 'UNCHAINED_NITIN', 'unrelated context')
    p = package['provenance']
    require(p['conversation_url'] == 'https://gemini.google.com/app/7c9afdcb27030bcb'
            and p['conversation_title'] == 'YouTube-groeistrategie unchainednitin', 'wrong source')
    require(p['account_match_observed'] is True, 'account not verified')
    sha(p['account_sha256']); sha(p['source_snapshot_sha256']); timestamp(p['observed_at'])
    require(package['excerpts_sha256'] == digest(canonical(excerpts)), 'excerpt content drift')
    boundaries = package['boundaries']
    for key in ('nitin_approval', 'rights_clearance', 'current_facts', 'current_qc',
                'publication_authorized', 'production_deployment_authorized'):
        require(boundaries[key] is False, 'historical authority escalation')
    require(boundaries['fresh_qc_must_review_actual_asset'] is True
            and boundaries['first_real_poster'] == 'PAUSED_BY_NITIN', 'QC/human gate changed')
    ids = set()
    for e in excerpts:
        text(e['id']);text(e['text'])
        require(type(e['page']) is int and 1 <= e['page'] <= p['snapshot_pages'], 'source page')
        require(e['id'] not in ids and digest(e['text'].encode()) == e['sha256'], 'excerpt identity/hash')
        ids.add(e['id'])
    require(bool(ids) and bool(package['insights']), 'empty context')
    insight_ids = set()
    for insight in package['insights']:
        text(insight['id']); text(insight['summary'])
        require(insight['id'] not in insight_ids, 'duplicate insight')
        insight_ids.add(insight['id'])
        require(insight['category'] in CATEGORIES, 'unknown category')
        require(insight['status'] == 'HISTORICAL_HYPOTHESIS'
                and insight['fresh_validation_required'] is True, 'unverified current claim')
        require(bool(insight['evidence_ids']) and set(insight['evidence_ids']) <= ids, 'missing source')
    return True


def context_for(package, excerpts, role):
    validate(package, excerpts)
    require(role in ('CREATIVE_INTELLIGENCE', 'INDEPENDENT_QC'), 'unsupported consumer')
    if role == 'INDEPENDENT_QC':
        return {'historical_context': [], 'historical_verdicts_allowed': False,
                'actual_asset_sha256_required': True, 'fresh_independent_review_required': True}
    return {'package_sha256': digest(canonical(package)), 'trust': 'UNTRUSTED_HISTORICAL_CONTEXT',
            'context': package['insights'], 'instructions_from_source_executable': False,
            'fresh_validation_required': True, 'approval_authority': False}
