"""Deterministic, inert JSON shadow bundle; no operational Sheets/Make client."""
import io
import json
import zipfile
from integration.contracts import canonical, digest, require


def build(files):
    require(type(files) is dict and bool(files), 'empty bundle')
    for name, data in files.items():
        require(type(name) is str and name.endswith('.json') and '/' not in name
                and '\\' not in name and name != 'MANIFEST.json', 'unsafe bundle name')
        require(type(data) is bytes, 'bundle bytes required')
        json.loads(data)
    manifest = dict(schema='CANONICAL_SHADOW_BUNDLE', schema_version=1,
                    mode='SHADOW_ONLY_NOT_DISPATCHABLE', production_deployment_authorized=False,
                    publication_authorized=False, first_real_poster='PAUSED_BY_NITIN',
                    files={name: digest(data) for name, data in sorted(files.items())})
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(dict(files, **{'MANIFEST.json': canonical(manifest)}).items()):
            entry = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    return output.getvalue()


def verify(blob, expected_sha256):
    require(digest(blob) == expected_sha256, 'remote bundle hash mismatch')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'duplicate entry')
        manifest = json.loads(z.read('MANIFEST.json'))
        require(set(names) == set(manifest['files']) | {'MANIFEST.json'}, 'manifest entry mismatch')
        files = {name: z.read(name) for name in manifest['files']}
    # Canonical rebuild rejects unknown manifest fields, unsafe names, changed flags,
    # altered content, timestamps, ordering or compression. Never extracts to disk.
    require(build(files) == blob, 'noncanonical bundle')
    return files
