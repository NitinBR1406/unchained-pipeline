"""Verify preserved bytes before cross-track synthesis; not a claim-quality test."""
from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parent
prompt = (root / 'FROZEN_PROMPT.txt').read_bytes()
result = {}
for name in ['GEMINI_A', 'CLAUDE_B', 'CHATGPT_C']:
    folder = root / name
    errors = []
    if (folder / 'RAW_PROMPT.txt').read_bytes() != prompt:
        errors.append('PROMPT_MISMATCH')
    receipt = folder / ('RECEPTION_RECEIPT.json' if name == 'CLAUDE_B' else 'RECEIPT.json')
    manifest = folder / 'FREEZE_MANIFEST.sha256'
    if not receipt.exists() or json.loads(receipt.read_text()).get('status') != 'FROZEN_V01':
        errors.append('MISSING_FROZEN_RECEIPT')
    if not manifest.exists():
        errors.append('MISSING_MANIFEST')
    else:
        for line in manifest.read_text().splitlines():
            digest, relative = line.split('  ', 1)
            target = (folder / relative).resolve()
            if not target.is_relative_to(folder.resolve()):
                errors.append('INVALID_MANIFEST_PATH')
            elif not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                errors.append('HASH_MISMATCH:' + relative)
    result[name] = {'frozen_bytes_verified': not errors, 'issues': errors}
print(json.dumps({'synthesis_allowed': all(v['frozen_bytes_verified'] for v in result.values()),
                  'tracks': result, 'caveat': 'Freeze does not validate research claims.'}, indent=2))
