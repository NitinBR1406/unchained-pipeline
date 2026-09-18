"""Version 1 strict wire contracts; deterministic validation, no external actions.

Hashes verify bytes, not authorship. Agent identities require authenticated transport
receipts before use as independent QC. UNKNOWN models remain explicit null values.
"""
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path

KINDS = ('CREATIVE_INTELLIGENCE_PACKAGE', 'PRODUCTION_RELEASE_PACKAGE', 'INDEPENDENT_QC_PACKAGE')
PLATFORMS = ('youtube_hero', 'youtube_shorts', 'instagram_reels', 'instagram_feed',
             'instagram_stories', 'facebook_reels', 'tiktok', 'x')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'unexpected/missing fields: ' + names)


def text(value):
    require(type(value) is str and 0 < len(value.strip()) <= 4096, 'invalid text')


def sha(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'invalid SHA256')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def timestamp(value):
    text(value)
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z', value), 'UTC timestamp required')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def refs(value):
    require(type(value) is list and bool(value), 'evidence refs required')
    for ref in value:
        keys(ref, 'uri sha256')
        text(ref['uri']); sha(ref['sha256'])
    require(len({r['uri'] for r in value}) == len(value), 'duplicate refs')


def verify_refs(value, resolver):
    refs(value)
    for ref in value:
        require(digest(resolver(ref['uri'])) == ref['sha256'], 'evidence bytes mismatch')


def file_resolver(root):
    root = Path(root).resolve()
    def resolve(uri):
        text(uri)
        path = (root / uri).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'unresolvable evidence path')
        return path.read_bytes()
    return resolve


def asset(value):
    keys(value, 'role uri sha256')
    require(value['role'] in ('raw_video', 'authoritative_audio', 'master', 'derivative'), 'asset role')
    text(value['uri']); sha(value['sha256'])


def validate(package):
    keys(package, 'schema schema_version content_id package_id created_at producer inputs evidence_refs payload')
    require(package['schema'] in KINDS, 'unknown schema')
    require(type(package['schema_version']) is int and package['schema_version'] == 1, 'unknown version')
    text(package['content_id']); text(package['package_id']); timestamp(package['created_at'])
    producer = package['producer']
    keys(producer, 'agent model run_id')
    text(producer['agent']); text(producer['run_id'])
    if producer['model'] is not None: text(producer['model'])
    require(type(package['inputs']) is list and bool(package['inputs']), 'inputs required')
    for item in package['inputs']: asset(item)
    require(len({(x['role'], x['uri']) for x in package['inputs']}) == len(package['inputs']), 'duplicate input')
    refs(package['evidence_refs'])
    p = package['payload']
    if package['schema'] == KINDS[0]:
        keys(p, 'edit_plan')
        require({x['role'] for x in package['inputs']} >= {'raw_video', 'authoritative_audio'}, 'RAW/audio pair required')
        validate_edit(p['edit_plan'], package['inputs'])
    elif package['schema'] == KINDS[1]:
        keys(p, 'creative_package_sha256 edit_plan_sha256 outputs platforms')
        sha(p['creative_package_sha256']); sha(p['edit_plan_sha256'])
        require(type(p['outputs']) is list and bool(p['outputs']), 'outputs required')
        for item in p['outputs']:
            asset(item)
            require(item['role'] in ('master', 'derivative'), 'production output must be rendered video')
        require(len({x['sha256'] for x in p['outputs']}) == len(p['outputs']), 'duplicate output')
        require(type(p['platforms']) is list and bool(p['platforms']), 'platform packages required')
        require(len({x['platform'] for x in p['platforms']}) == len(p['platforms']), 'duplicate platform')
        for row in p['platforms']:
            keys(row, 'platform asset_sha256 title caption')
            require(row['platform'] in PLATFORMS, 'unknown platform')
            require(row['asset_sha256'] in {x['sha256'] for x in p['outputs']}, 'unbound platform asset')
            text(row['title']); text(row['caption'])
    else:
        keys(p, 'production_package_sha256 checked_assets verdict checks')
        sha(p['production_package_sha256'])
        require(type(p['checked_assets']) is list and bool(p['checked_assets']), 'checked assets required')
        for value in p['checked_assets']: sha(value)
        require(len(set(p['checked_assets'])) == len(p['checked_assets']), 'duplicate QC asset')
        require(p['verdict'] in ('PASS', 'FAIL', 'UNKNOWN'), 'QC verdict')
        keys(p['checks'], 'technical look_match full_motion lipsync audio platform_safe_area performance_rule')
        require(all(v in ('PASS', 'FAIL', 'UNKNOWN') for v in p['checks'].values()), 'QC check verdict')
        if p['verdict'] == 'PASS':
            require(all(v == 'PASS' for v in p['checks'].values()), 'partial QC cannot pass')
    canonical(package)
    return package


def positive_int(value):
    require(type(value) is int and value > 0, 'positive integer required')


def validate_edit(plan, inputs):
    """Milliseconds on OUTPUT timeline; full contiguous coverage, >=80% performance.

    Only a visible, unobscured performer counts; durations cannot be double counted.
    Effects never authorize changes to the locked Aakhri Ishq master.
    """
    keys(plan, 'duration_ms segments effects baseline_locked execution_mode')
    positive_int(plan['duration_ms'])
    require(type(plan['baseline_locked']) is bool, 'baseline lock type')
    require(plan['execution_mode'] == 'RECOMMENDATION_ONLY', 'execution is separately gated')
    require(type(plan['segments']) is list and bool(plan['segments']), 'segments required')
    allowed = {x['sha256']: x['role'] for x in inputs}
    cursor = performance = 0
    for s in plan['segments']:
        keys(s, 'start_ms end_ms source_sha256 source_start_ms source_end_ms performer_visible')
        for key in ('start_ms','end_ms','source_start_ms','source_end_ms'):
            require(type(s[key]) is int and s[key] >= 0, 'invalid segment time')
        require(s['start_ms'] == cursor and s['end_ms'] > cursor, 'gap/overlap in output timeline')
        require(s['source_end_ms'] - s['source_start_ms'] == s['end_ms'] - s['start_ms'], 'retiming forbidden')
        require(allowed.get(s['source_sha256']) in ('raw_video','master','derivative'), 'unbound video source')
        require(type(s['performer_visible']) is bool, 'visibility must be boolean')
        cursor = s['end_ms']
        if s['performer_visible']: performance += s['end_ms'] - s['start_ms']
    require(cursor == plan['duration_ms'], 'duration mismatch')
    require(performance * 5 >= cursor * 4, '80_PERCENT_PERFORMANCE_RULE')
    require(type(plan['effects']) is list, 'effects must be list')
    for effect in plan['effects']:
        keys(effect, 'kind start_ms end_ms intensity_milli performer_obscured')
        require(effect['kind'] in ('reframe','zoom','shake','caption','grade','cut'), 'unsupported effect')
        require(all(type(effect[k]) is int for k in ('start_ms','end_ms','intensity_milli')), 'effect integer bounds')
        require(0 <= effect['start_ms'] < effect['end_ms'] <= cursor, 'effect outside timeline')
        require(0 <= effect['intensity_milli'] <= 1000, 'effect intensity')
        require(effect['performer_obscured'] is False, 'obscuring effects forbidden')
    return {'performance_ms': performance, 'duration_ms': cursor, 'minimum_fraction': '4/5'}


def validate_chain(creative, production, qc, resolver, authenticated_receipts):
    """Receipts must come from the trusted integration transport, never package payloads."""
    for package, kind in zip((creative, production, qc), KINDS):
        validate(package); require(package['schema'] == kind, 'chain package type')
        verify_refs(package['evidence_refs'], resolver)
        for item in package['inputs']:
            require(digest(resolver(item['uri'])) == item['sha256'], 'input bytes mismatch')
    require(len({x['content_id'] for x in (creative,production,qc)}) == 1, 'cross-content chain')
    require(timestamp(creative['created_at']) <= timestamp(production['created_at']) <= timestamp(qc['created_at']), 'chain time order')
    cp, pp = creative['payload'], production['payload']
    require(pp['creative_package_sha256'] == digest(canonical(creative)), 'creative lineage mismatch')
    require(pp['edit_plan_sha256'] == digest(canonical(cp['edit_plan'])), 'edit lineage mismatch')
    require(production['inputs'] == creative['inputs'], 'production source lineage mismatch')
    for item in pp['outputs']:
        require(digest(resolver(item['uri'])) == item['sha256'], 'output bytes mismatch')
    require(qc['inputs'] == pp['outputs'], 'QC input lineage mismatch')
    require(qc['payload']['production_package_sha256'] == digest(canonical(production)), 'QC lineage mismatch')
    require(set(qc['payload']['checked_assets']) == {x['sha256'] for x in pp['outputs']}, 'partial QC coverage')
    require(qc['producer']['agent'] != production['producer']['agent'], 'QC reviewer not independent')
    require(qc['producer']['run_id'] != production['producer']['run_id'], 'QC run not independent')
    for package in (creative, production, qc):
        receipt = authenticated_receipts.get(digest(canonical(package)))
        require(receipt == package['producer'], 'authenticated producer receipt absent/mismatch')
    require(qc['payload']['verdict'] == 'PASS', 'QC not passed')
    return True
