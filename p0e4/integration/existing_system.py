"""Wrap the repository's existing Claude-authored packaging system, never rebuild it.

This adapter prepares immutable handoff records only. It cannot invoke Make/P1,
Shotstack Production, deploy, activate a scenario or publish. The external Claude
service/endpoint is NOT ESTABLISHED by a historical blueprint.
"""
import sys
from pathlib import Path
from .contracts import canonical, digest, validate

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from unpipe.adapters import PackagingEngine

SOURCES = ('unpipe/adapters.py', 'unpipe/executor.py', 'unpipe/production.py',
           'unpipe/orchestrator.py', 'unpipe/dispatcher.py',
           'make/V3_SECURE_blueprint.json', 'P0D_REAL_P1_WIRING_PLAN_V01.md',
           'CANONICAL_FACTORY_DATA_GOVERNANCE_MODEL_V01.json', 'CAPABILITY_MATRIX.md')


def inventory(root=ROOT):
    return {'schema_version': 1,
        'system': 'Existing repository production/packaging + historical Make P1 integration',
        'external_claude_service': 'NOT_ESTABLISHED',
        'historical_p1_scenario_id': '9627055', 'live_p1_inspected': False,
        'sources': [{'uri': p, 'sha256': digest((root/p).read_bytes())} for p in SOURCES],
        'reused_entrypoint': 'unpipe.adapters.PackagingEngine.build',
        'production_entrypoint_observed': 'unpipe.executor.run_production_job',
        'limitations': ['PackagingEngine produces metadata drafts, not rendered assets',
                       'Claude/Gemini authenticated transports not configured',
                       'Historical snapshots are not proof of current remote state'],
        'production_deployment_authorized': False, 'publication_authorized': False,
        'first_real_poster': 'PAUSED_BY_NITIN'}


def prepare(package):
    validate(package)
    rows = package['payload'].get('platforms')
    if package['schema'] != 'PRODUCTION_RELEASE_PACKAGE' or not rows:
        raise ValueError('production package required')
    draft = PackagingEngine().build(package['content_id'], [x['platform'] for x in rows],
                                    {'title': rows[0]['title'], 'rights_status': 'RIGHTS_HOLD'})
    # Existing generator has a wall-clock field. The wrapper binds it to the input
    # event time so retries yield the same canonical handoff bytes.
    draft['generated_at'] = package['created_at']
    for target, source in zip(draft['packages'], rows):
        target.update(title=source['title'], caption=source['caption'], asset_sha256=source['asset_sha256'])
    return {'schema_version': 1, 'content_id': package['content_id'],
        'production_package_sha256': digest(canonical(package)),
        'idempotency_key': digest(canonical(package)), 'existing_system_draft': draft,
        'status': 'PREPARED_NOT_DISPATCHED', 'external_side_effect_count': 0,
        'execution_blockers': ['AUTHENTICATED_CLAUDE_CAPABILITY_NOT_ESTABLISHED',
                               'PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED']}
