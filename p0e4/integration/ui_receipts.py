"""Validate observed UI receipts without elevating them to provider authority.

This module dispatches nothing. A completed UI smoke is not a durable adapter,
real-media QC, approval, or proof that all remote side effects were absent.
"""
from integration.contracts import require, digest, timestamp, text


def validate(receipt, request, result=None):
    require(receipt['schema'] == 'P0E4_UI_EXECUTION_RECEIPT' and
            type(receipt['schema_version']) is int and receipt['schema_version'] == 1,
            'unsupported receipt')
    text(receipt['request_id']); text(receipt['surface'])
    require(receipt['status'] in ('SUBMITTED', 'RUNNING', 'COMPLETED', 'FAILED', 'BLOCKED'), 'status')
    require(receipt['request_sha256'] == digest(request), 'request bytes mismatch')
    timestamp(receipt['observed_at'])
    if receipt['submitted_at'] is not None:
        require(timestamp(receipt['submitted_at']) <= timestamp(receipt['observed_at']), 'time order')
    require(receipt['NON_PUBLISHING'] is True, 'non-publishing scope required')
    require(receipt['production_deployment_authorized'] is False and
            receipt['publication_authorized'] is False and
            receipt['first_real_poster'] == 'PAUSED_BY_NITIN', 'human gate changed')
    require(receipt['provider_signed'] is False and receipt['durable_dispatcher_proven'] is False
            and receipt['real_media_qc_proven'] is False, 'UI evidence authority exceeded')
    require(receipt['observation_source'] == 'computer_use_ui', 'observation provenance')
    require(receipt['historical_task_reused'] is False, 'historical task is not execution')
    require(type(receipt['observed_events']) is list and bool(receipt['observed_events']), 'events required')
    if receipt['status'] == 'COMPLETED':
        require('completion_observed' in receipt['observed_events'], 'no observed completion')
        require(result is not None and receipt['result_sha256'] == digest(result), 'result bytes mismatch')
        require(receipt['result_capture'] in ('rendered_text', 'rendered_json',
                'local_output_artifact_sanitized'), 'capture boundary')
    elif result is None:
        require(receipt['result_sha256'] is None, 'invented result')
    else:
        require(receipt['result_sha256'] == digest(result), 'partial result mismatch')
    # This result is deliberately insufficient to authorize a production operation.
    return {'receipt_valid': True, 'production_eligible': False,
            'publication_eligible': False, 'retry_safe': False}
