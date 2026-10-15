"""Stored Make blueprints (live read-back files) vs local builders. Read-only. Writes TEST_RESULTS_STORED_VS_BUILDERS.json."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
def strip(x):
    if isinstance(x, dict): return {k: strip(v) for k, v in x.items() if k != 'metadata'}
    if isinstance(x, list): return [strip(v) for v in x]
    return x
out = {}
import hashlib
for name, stored, local in (('P2 9974134', 'P2_9974134_STORED_20261015h.json', 'P2_blueprint.json'),
                            ('M1 9974218', 'M1_9974218_STORED_20261014f.json', 'M1_blueprint.json'),
                            ('P3 9975129', 'P3_9975129_STORED_20261014f.json', 'P3_blueprint.json'),
                            ('R1 9975098', 'R1_9975098_STORED_20261014f.json', 'R1_blueprint.json')):
    d = json.loads((HERE / stored).read_text())
    out[name] = dict(equal=strip(d['blueprint']['flow']) == strip(json.loads((HERE / local).read_text())['flow']),
                     isinvalid=d.get('isinvalid'), isActive=d.get('isActive'), lastEdit=d.get('lastEdit'),
                     misleading_label_downloaded_bytes='downloaded bytes' in json.dumps(d['blueprint']),
                     stored_sha256=hashlib.sha256((HERE / stored).read_bytes()).hexdigest(),
                     builder_sha256=hashlib.sha256((HERE / local).read_bytes()).hexdigest())
(HERE / 'TEST_RESULTS_STORED_VS_BUILDERS.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
