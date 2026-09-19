"""Offline request mapping to the inspected existing /clip implementation.

No HTTP transport. This endpoint always uploads to GCS. It cannot be used as a
private smoke route merely by setting save_to_drive=false. Generic effect kinds
are not guessed into unrelated compositor event schemas.
"""
from decimal import Decimal
from integration.contracts import require,canonical,digest,verify_refs
from copy import deepcopy


def prepare_clip(groups,evidence,resolver):
    verify_refs(evidence,resolver)
    require(groups['aspect_ratios']=='9:16','UNMAPPED_RENDER_ASPECT_RATIO')
    require(not groups['edit_effects']['effects'],'UNMAPPED_RENDER_EFFECT_SEMANTICS')
    cut=groups['timestamps'];require(type(cut['start_ms']) is int and type(cut['end_ms']) is int,'integer milliseconds required')
    require(0<=cut['start_ms']<cut['end_ms'],'invalid cut')
    # Native interface consumes seconds. Strings preserve exact milliseconds in
    # JSON, and the existing code explicitly converts these fields with float().
    seconds=lambda ms:format(Decimal(ms)/Decimal(1000),'f')
    request_fields=dict(start=seconds(cut['start_ms']),duration=seconds(cut['end_ms']-cut['start_ms']),hook_text=groups['hooks'],brand_text=groups['cta'],fx=False,save_to_drive=False)
    return dict(schema='EXISTING_CLIP_REQUEST_PREPARATION',schema_version=1,endpoint_path='/clip',request_fields=request_fields,source_asset=deepcopy(groups['derivatives']['source_asset']),source_sha256=groups['derivatives']['source_asset']['sha256'],interface_evidence=deepcopy(evidence),status='BLOCKED_EXTERNAL_RENDER_SETUP',blockers=['PRIVATE_OUTPUT_SINK_NOT_PROVEN','DEPLOYED_SOURCE_PARITY_NOT_PROVEN','SOURCE_MEDIA_SHA_VERIFICATION_NOT_IMPLEMENTED_BY_ENDPOINT','REAL_MEDIA_AND_AUDIO_BINDING_NOT_ESTABLISHED'],render_called=False,publication_authorized=False)


def readback_clip(request):
    r=request['request_fields']
    require(r['fx'] is False and r['save_to_drive'] is False,'unexpected effects/write request')
    start=Decimal(r['start'])*1000;end=start+Decimal(r['duration'])*1000
    require(start==int(start) and end==int(end),'fractional milliseconds lost')
    return dict(timestamps=dict(start_ms=int(start),end_ms=int(end)),hooks=r['hook_text'],cta=r['brand_text'])
