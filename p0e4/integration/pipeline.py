"""Golden boundary toward E2E: strict chain -> existing wrapper -> rights -> wait.

The only successful terminal is WAITING_FOR_NITIN_PUBLISH_APPROVAL. There is no
publish/deploy implementation. Trusted receipts/review verification are injected
by deployment wiring; untrusted package fields cannot set them.
"""
from .contracts import canonical, digest, validate_chain, require
from .existing_system import prepare
from .rights import evaluate


def prepare_release(creative, production, qc, *, resolver, authenticated_receipts,
                    rights_store, reviewer_keys, scope, at, final_review_verifier=None):
    result = {'schema_version': 1, 'status': 'BLOCKED', 'publish_ready': False,
              'blockers': [], 'platforms': [], 'publication_authorized': False,
              'production_deployment_authorized': False, 'first_real_poster': 'PAUSED_BY_NITIN',
              'next_gate': 'NITIN_PUBLISH_APPROVAL', 'hard_stop': True,
              'external_side_effect_count': 0}
    try:
        validate_chain(creative, production, qc, resolver, authenticated_receipts)
        result['handoff'] = prepare(production)
        result['production_package_sha256'] = digest(canonical(production))
        for row in production['payload']['platforms']:
            request = dict(scope, content_id=production['content_id'],
                asset_sha256=row['asset_sha256'], platform=row['platform'], at=at)
            decision = evaluate(request, rights_store, reviewer_keys, resolver)
            result['platforms'].append({'platform': row['platform'], 'rights': decision})
            if decision['pass'] is not True:
                result['blockers'].append('RIGHTS_HOLD:' + row['platform'])
        # This is a trusted verifier over the EXACT package hash. No approvals
        # are accepted from package JSON, QC verdicts or rights records.
        if final_review_verifier is None or final_review_verifier(
                production['content_id'], result['production_package_sha256']) is not True:
            result['blockers'].append('NITIN_FINAL_ASSET_VIDEO_AND_RELEASE_REVIEW_REQUIRED')
        if not result['blockers']:
            result.update(status='WAITING_FOR_NITIN_PUBLISH_APPROVAL', publish_ready=True)
    except Exception:
        result['blockers'].append('INVALID_OR_UNVERIFIED_PACKAGE_CHAIN')
    return result
