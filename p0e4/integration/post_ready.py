"""Post-ready routing after read-only RAW/audio intake; all authority stays external."""
from copy import deepcopy
from .contracts import keys, require, sha, text


def reconcile_raw(raw_hash, binding):
    keys(raw_hash, 'file_id path bytes sha256 method status source_mutations')
    require(raw_hash['status'] == 'RAW_BYTES_HASHED', 'RAW not hash-observed')
    sha(raw_hash['sha256']); text(raw_hash['path']); text(raw_hash['file_id'])
    require(type(raw_hash['bytes']) is int and raw_hash['bytes'] > 0, 'RAW byte count')
    require(raw_hash['source_mutations'] == 0, 'RAW source mutated')
    require(binding['raw_sha256'] == raw_hash['sha256'], 'binding RAW hash drift')
    require(binding['raw_file_id'] == raw_hash['file_id'], 'binding RAW identity drift')
    require(binding['raw_bytes'] == raw_hash['bytes'], 'binding RAW size drift')
    require(binding['authoritative_audio'] is None, 'unexpected audio binding')
    require(binding['real_e2e_allowed'] is False, 'unexpected E2E authority')
    require(binding['status'] == 'WAITING_FOR_NITIN_AUDIO_SOURCE_BINDING', 'binding gate drift')
    return {'schema': 'RAW_INGEST_RECONCILIATION_V01', 'schema_version': 1,
            'content_id': binding['content_id'], 'raw': deepcopy(raw_hash),
            'raw_contract_status': 'RAW_IDENTITY_HASH_RECONCILED',
            'full_ingest_status': 'BLOCKED_MISSING_AUTHORITATIVE_AUDIO',
            'authoritative_audio': None, 'human_gate': 'AKI_AUTHORITATIVE_AUDIO_BINDING',
            'source_mutations': 0, 'production_deployment_authorized': False,
            'publication_authorized': False}


def route(reconciliation, production_deployment_authorized=False,
          publication_authorized=False):
    require(reconciliation['schema'] == 'RAW_INGEST_RECONCILIATION_V01', 'reconciliation schema')
    require(reconciliation['raw_contract_status'] == 'RAW_IDENTITY_HASH_RECONCILED', 'RAW not ready')
    require(reconciliation['source_mutations'] == 0, 'source mutation')
    require(production_deployment_authorized is False, 'production authority cannot be inferred')
    require(publication_authorized is False, 'publication authority cannot be inferred')
    if reconciliation['authoritative_audio'] is None:
        status = 'WAITING_FOR_NITIN_AUDIO_SOURCE_BINDING'
        next_stage = 'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING'
    else:
        sha(reconciliation['authoritative_audio']['sha256'])
        status = 'READY_FOR_AUTHORIZED_REAL_MEDIA_ORCHESTRATION'
        next_stage = 'REAL_MEDIA_ORCHESTRATION'
    return {'schema': 'POST_READY_CONTRACT_V01', 'schema_version': 1,
            'content_id': reconciliation['content_id'], 'status': status,
            'next_stage': next_stage,
            'required_before_real_media': ['AUTHORITATIVE_RAW_AUDIO_PAIR',
                                           'PRODUCTION_DEPLOYMENT_AUTHORIZED'],
            'required_before_publication': ['NITIN_PUBLISH_APPROVAL'],
            'rights_source_binding_preserved': True,
            'evidence_required': True, 'production_deployment_authorized': False,
            'publication_authorized': False, 'first_real_poster': 'PAUSED_BY_NITIN'}
