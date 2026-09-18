"""Read-only byte fingerprint and full decode; never edits approved media."""
import hashlib
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg


def verify(path, metadata):
    path = Path(path)
    with path.open('rb') as f:
        before = hashlib.file_digest(f, 'sha256').hexdigest()
    size = path.stat().st_size
    if size != int(metadata['size_bytes']):
        raise ValueError('Drive size does not match downloaded bytes')
    frames = imageio_ffmpeg.read_frames(str(path))
    try:
        probe = next(frames)
    finally:
        frames.close()
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-xerror', '-nostdin',
           '-i', str(path), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']
    decoded = subprocess.run(cmd, capture_output=True, timeout=600)
    with path.open('rb') as f:
        after = hashlib.file_digest(f, 'sha256').hexdigest()
    if before != after:
        raise ValueError('source changed during verification')
    return {**metadata, 'sha256': before, 'size_bytes': size,
            'probe': probe, 'full_av_decode_exit_code': decoded.returncode,
            'decode_diagnostics': decoded.stderr.decode(errors='replace')[-4000:],
            'bytes_unchanged': True, 'technical_decode_pass': decoded.returncode == 0,
            'creative_approval_inferred': False, 'publication_approval_inferred': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--cache', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    entries = json.loads(Path(args.manifest).read_text())
    results = [verify(Path(args.cache)/m['cache_name'], m) for m in entries]
    Path(args.out).write_text(json.dumps({'schema_version': 1, 'assets': results}, indent=2))
    print([(a['name'],a['technical_decode_pass'],a['sha256']) for a in results])
