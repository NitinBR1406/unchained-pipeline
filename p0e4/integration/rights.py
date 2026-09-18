"""Fail-closed rights router. No grant inferred from a status string or Content ID.

A provisioned reviewer signature attests a reviewed scope, not a Nitin human gate.
No signing key is generated/provisioned here. The store is re-read on every request
so revocation, expiration and corruption take effect without a service restart.
"""
import base64
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .contracts import (PLATFORMS, canonical, digest, keys, require, sha, text,
                        timestamp, verify_refs)

RIGHTS = ('composition', 'lyrics', 'recording', 'performers', 'samples')


def request_check(request):
    keys(request, 'content_id asset_sha256 platform territories account_id use monetized at')
    text(request['content_id']); sha(request['asset_sha256'])
    require(request['platform'] in PLATFORMS, 'unknown platform')
    require(type(request['territories']) is list and bool(request['territories']), 'territories unknown')
    require(all(type(t) is str and len(t) == 2 and t.isupper() and t.isalpha() for t in request['territories']), 'territory must be ISO country code')
    require(len(set(request['territories'])) == len(request['territories']), 'duplicate territory')
    text(request['account_id'])
    require(request['use'] in ('organic', 'paid'), 'unknown use')
    require(type(request['monetized']) is bool, 'unknown monetization')
    timestamp(request['at'])


def review_check(record, public_keys, resolver):
    keys(record, 'review key_id signature')
    review = record['review']
    keys(review, 'schema_version grant_id content_id asset_sha256 platforms territories account_ids uses monetized rights valid_from valid_until revoked evidence_refs reviewed_at')
    require(type(review['schema_version']) is int and review['schema_version'] == 1, 'rights schema')
    text(record['key_id']); text(record['signature']); text(review['grant_id'])
    require(record['key_id'] in public_keys, 'untrusted reviewer')
    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_keys[record['key_id']]))
    key.verify(base64.b64decode(record['signature'], validate=True), canonical(review))
    text(review['content_id']); sha(review['asset_sha256'])
    for field in ('platforms','territories','account_ids','uses'):
        require(type(review[field]) is list and bool(review[field]), 'empty rights scope')
        for item in review[field]: text(item)
        require(len(set(review[field])) == len(review[field]) and '*' not in review[field], 'ambiguous rights scope')
    require(set(review['platforms']) <= set(PLATFORMS), 'unknown grant platform')
    require(set(review['uses']) <= {'organic','paid'}, 'unknown grant use')
    require(type(review['monetized']) is bool and type(review['revoked']) is bool, 'rights flags must be booleans')
    keys(review['rights'], ' '.join(RIGHTS))
    require(all(v in ('CLEARED','NOT_APPLICABLE') for v in review['rights'].values()), 'incomplete rights review')
    require(review['rights']['composition'] == review['rights']['lyrics'] == review['rights']['recording'] == 'CLEARED', 'core rights cannot be waived')
    require(timestamp(review['valid_from']) < timestamp(review['valid_until']), 'invalid term')
    require(timestamp(review['reviewed_at']) <= timestamp(review['valid_until']), 'invalid review time')
    verify_refs(review['evidence_refs'], resolver)
    return review


def evaluate(request, store, public_keys, resolver):
    result = {'schema_version': 1, 'status': 'RIGHTS_HOLD', 'pass': False,
              'reasons': [], 'grant_ids': [], 'request_sha256': None,
              'publish_authorized': False}
    try:
        request_check(request)
        result['request_sha256'] = digest(canonical(request))
        # The complete snapshot is checked before accepting any grant. Malformed,
        # duplicate or forged records invalidate the snapshot rather than hiding errors.
        records = json.loads(Path(store).read_text())
        require(type(records) is list, 'invalid rights store')
        reviews = [review_check(x, public_keys, resolver) for x in records]
        require(len({r['grant_id'] for r in reviews}) == len(reviews), 'duplicate grant')
        now = timestamp(request['at'])
        for r in reviews:
            if (r['content_id'] == request['content_id'] and r['asset_sha256'] == request['asset_sha256']
                and request['platform'] in r['platforms']
                and set(request['territories']) <= set(r['territories'])
                and request['account_id'] in r['account_ids'] and request['use'] in r['uses']
                and (not request['monetized'] or r['monetized'])
                and not r['revoked'] and timestamp(r['reviewed_at']) <= now
                and timestamp(r['valid_from']) <= now < timestamp(r['valid_until'])):
                result['grant_ids'].append(r['grant_id'])
        if result['grant_ids']:
            result.update(status='RIGHTS_PASS', **{'pass': True})
            result['grant_ids'].sort()
        else:
            result['reasons'] = ['NO_VERIFIED_APPLICABLE_CLEARANCE']
    except Exception:
        # Never log external record text/signatures/exception values.
        result['reasons'] = ['INVALID_OR_UNAVAILABLE_RIGHTS_EVIDENCE']
    return result
