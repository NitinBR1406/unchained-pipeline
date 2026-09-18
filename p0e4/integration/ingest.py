"""Read-only, hash-bound drop-folder intake. Never substitutes a rendered master for RAW."""
from .contracts import keys, require, text, asset, digest, timestamp, file_resolver


def inspect_inbox(manifest, root):
    keys(manifest, 'schema_version content_id received_at assets')
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1, 'ingest version')
    text(manifest['content_id']); timestamp(manifest['received_at'])
    require(type(manifest['assets']) is list and len(manifest['assets']) == 2, 'RAW + authoritative audio required')
    resolve = file_resolver(root)
    for item in manifest['assets']:
        asset(item)
        require(digest(resolve(item['uri'])) == item['sha256'], 'ingest hash mismatch')
    require({x['role'] for x in manifest['assets']} == {'raw_video','authoritative_audio'}, 'RAW/audio identity not established')
    require(len({x['uri'] for x in manifest['assets']}) == 2, 'distinct RAW/audio files required')
    return {'schema_version':1,'content_id':manifest['content_id'], 'status':'INGEST_VERIFIED_BYTES',
            'assets':manifest['assets'],'received_at':manifest['received_at'],
            'technical_decode':'NOT_PERFORMED','publication_authorized':False}
