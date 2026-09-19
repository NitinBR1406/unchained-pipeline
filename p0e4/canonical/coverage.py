"""Execution readiness is stronger than lossless canonical shadow storage.

No execution approval is emitted. Existing V1 adapter only proves three fields;
all other fields stay blocked until a tested consumer adapter is implemented.
"""
from integration.contracts import require, canonical, digest
from .adapter import shadow, readback

REQUIRED = {
 'title': 'PLATFORM_PACKAGES[*].title',
 'caption': 'PLATFORM_PACKAGES[*].caption',
 'hashtags': 'PLATFORM_PACKAGES[*].hashtags',
 'cta': 'PLATFORM_PACKAGES[*].cta',
 'hooks': 'DERIVATIVES[*].hook',
 'timestamps': 'DERIVATIVES[*].start_ms,end_ms',
 'derivatives': 'DERIVATIVES',
 'aspect_ratios': 'DERIVATIVES[*].aspect_ratio',
 'edit_effects': 'creative_package.payload.edit_plan',
 'thumbnails_posters': 'PLATFORM_PACKAGES[*].thumbnail_asset_id,poster_asset_id',
 'platform_targeting': 'PLATFORM_PACKAGES[*].platform',
 'schedules': 'PLATFORM_PACKAGES[*].scheduled_at,schedule_timezone,schedule_version',
 'experiments': 'EXPERIMENTS',
 'provenance': 'AGENT_EVIDENCE,evidence_refs,source_package_sha256',
}
# Never add a field here solely because a report says that Make consumes it.
PROVEN_ADAPTER_FIELDS = frozenset(('title', 'caption', 'hashtags'))


def assess(data, creative, field_map, snapshot, resolver):
    result = shadow(data, creative, field_map, snapshot, resolver)
    restored = readback(result, field_map, snapshot, resolver)
    require(restored == data, 'SEMANTIC_DRIFT')
    require(bool(data['PLATFORM_PACKAGES']), 'no platform packages')
    rows = []
    for package in data['PLATFORM_PACKAGES']:
        mappings = {m['canonical_field']: m for m in field_map['fields']
                    if m['platform'] == package['platform'] and m['status'] == 'VERIFIED'}
        for field, path in REQUIRED.items():
            m = mappings.get(field)
            proven = field in PROVEN_ADAPTER_FIELDS and m is not None and bool(m['make_consumers'])
            rows.append(dict(package_id=package['package_id'], field=field, canonical_path=path,
                             storage='LOSSLESS_SHADOW',
                             execution='PROJECTED_LEGACY_FIELD' if proven else 'REQUIRED_UNMAPPED_EXECUTION_FIELD',
                             authenticated_live_execution=False))
    covered = sum(r['execution'] == 'PROJECTED_LEGACY_FIELD' for r in rows)
    return dict(schema='EXECUTION_COVERAGE_REPORT', schema_version=1,
                canonical_sha256=digest(canonical(data)), map_sha256=digest(canonical(field_map)),
                required_count=len(rows), projected_count=covered,
                missing_count=len(rows)-covered, fields=rows,
                shadow_zero_drift=True, execution_coverage_complete=covered == len(rows),
                live_execution_proven=False, dispatch_authorized=False,
                status='BLOCKED_REQUIRED_EXECUTION_COVERAGE')


def require_execution(data, creative, field_map, snapshot, resolver):
    report = assess(data, creative, field_map, snapshot, resolver)
    require(report['execution_coverage_complete'], 'REQUIRED_UNMAPPED_EXECUTION_FIELD')
    # Completeness alone can never grant deployment or publication.
    raise ValueError('LIVE_CUTOVER_NOT_AUTHORIZED')
