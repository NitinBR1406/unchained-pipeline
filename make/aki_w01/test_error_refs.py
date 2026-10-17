"""Every error reference inside a Make error handler must name the module whose onerror route it is in
(T2 v3 runtime finding: bare {{error.*}} is empty in handlers). Also checks the P2 classifier binds to the upload module."""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_error_refs import bare_error_refs
REF = re.compile(r'(?<![\w.])(\d+)\.error\b')
res = []
def check(name, flow):
    bad = []
    def own(m): return json.dumps({k: v for k, v in m.items() if k not in ('routes', 'onerror')})
    def walk(fl, parent=None):
        for m in fl:
            for ref in REF.findall(own(m)):
                if parent is None or int(ref) != parent: bad.append((parent, m['id'], ref))
            if m.get('onerror'): walk(m['onerror'], m['id'])
            for r in m.get('routes') or []: walk(r['flow'], parent)
    walk(flow)
    res.append((name + ': no bare error.* left', not bare_error_refs(flow)))
    res.append((name + ': handler refs point to failing module', not bad, bad[:3]))
for f in ('P2_blueprint.json', 'P3_blueprint.json', 'M1_blueprint.json'):
    check(f, json.loads((HERE / f).read_text())['flow'])
p2 = json.dumps(json.loads((HERE / 'P2_blueprint.json').read_text()))
mods = {}
def idx(fl):
    for m in fl:
        mods[m['id']] = m
        idx(m.get('onerror') or [])
        for r in m.get('routes') or []: idx(r['flow'])
idx(json.loads(p2)['flow'])
cls_ids = sorted({int(x) for x in re.findall(r'ifempty\((\d+)\.error\.type; \\"UNKNOWN\\"\)', p2)})
res.append(('P2 classifier bound to upload modules only', bool(cls_ids) and all(
    mods[i]['module'].split(':')[0] in ('instagram-business', 'facebook-pages', 'youtube') for i in cls_ids), [mods[i]['module'] for i in cls_ids]))
ok = all(r[1] for r in res)
for r in res: print('PASS' if r[1] else 'FAIL', *r[::2] if len(r) > 2 and not r[1] else r[:1])
(HERE / 'TEST_RESULTS_ERROR_REFS.json').write_text(json.dumps({'all_pass': ok, 'checks': res}, indent=1, default=str) + '\n')
sys.exit(0 if ok else 1)
