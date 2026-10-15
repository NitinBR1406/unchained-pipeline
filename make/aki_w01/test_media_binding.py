"""Approved file <-> published file binding (P2 version e), with SYNTHETIC files only.

Evaluates the filter conditions exactly as stored in P2_blueprint.json (mini evaluator over the real condition JSON),
feeds them real bytes (synthetic files in the private Drive test folder + the PR fixture), and sends the resulting gate
request to the REAL verifier code of PR #38 (isolated test grants, temp stores). Instagram hosting is simulated by a
local object store with GCS-like generations (versioning off: an overwrite creates a new generation, the old generation
URL returns 404). Nothing leaves this machine. Writes TEST_RESULTS_MEDIA_BINDING.json.

Cases (brief item 1): 1 exact approved file; 2 changed bytes, same name; 3 file replaced after an earlier check;
4 wrong / missing hash; 5 wrong format variant."""
import hashlib, json, os, re, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
PR = str(Path(__file__).resolve().parents[2])   # repo root (unpipe/, tests/fixtures)
sys.path.insert(0, PR)
from unpipe.approvals import ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_FINAL_ASSET, GATE_PUBLISH, APPROVE
from unpipe.placement_provisioner import PlacementProvisioner
from unpipe.publish_approval import PublishApprovalService
from unpipe import canonical as C

SYN = Path(os.environ['AKI_SYN_DIR'])   # folder with the synthetic SYN_B/SYN_C test images (no campaign media)
A = (SYN / 'SYN_A_approved.bin').read_bytes()
B4x5 = (SYN / 'SYN_B_variant_4x5.jpg').read_bytes()
C9x16 = (SYN / 'SYN_C_variant_9x16.jpg').read_bytes()
FIX = (Path(PR) / 'tests/fixtures/synthetic_media/SYN_HTTP_MEDIA.bin').read_bytes()
sha = lambda b: hashlib.sha256(b).hexdigest()
NOW_EPOCH = int(time.time())

def walk(flow):
    for m in flow:
        yield m
        for r in m.get('routes', []): yield from walk(r['flow'])
        for e in m.get('onerror') or []: yield e
TEST_BUCKET = 'aki-test-bucket'
PROD_BUCKET = json.dumps(json.load(open(HERE / 'P2_blueprint.json'))).split('https://storage.googleapis.com/')[1].split('/')[0]
def load(bucket=None):
    """bucket: test copy with the production bucket name replaced (local GCS-like store); 'UNCONFIGURED' = hosting switched off"""
    def sub(x):
        if isinstance(x, dict):
            if x.get('a') == PROD_BUCKET and x.get('b') == 'UNCONFIGURED':      # the "bucket is configured" sentinel: keep b
                return dict(x, a=bucket)
            return {k: sub(v) for k, v in x.items()}
        if isinstance(x, list): return [sub(v) for v in x]
        return x.replace(PROD_BUCKET, bucket) if isinstance(x, str) else x
    flow = json.load(open(HERE / 'P2_blueprint.json'))['flow']
    return {m['id']: m for m in walk(sub(flow) if bucket else flow)}
BY = load(); BYT = load(TEST_BUCKET)
MODS = list(BY.values())
def media_route(ch, by=None):
    by = by or BY
    sel = next(m for m in by.values() if m.get('filter', {}).get('name', '').startswith(ch + ' '))
    b = sel['id'] - 15 if sel['module'] == 'json:ParseJSON' else sel['id']
    return by[b], by[b + 3], by[b + 11 + 1000], sel
VARIANT_ROUTE = BY[next(m['id'] for m in MODS if 'CHANNEL_VARIANT_MISMATCH' in json.dumps(m.get('mapper', {}))) + 1000]

def resolve(expr, rec, env):
    def one(m):
        e = m.group(1)
        if e.startswith('1.data.'): return str(rec.get(e[7:], ''))
        mm = re.fullmatch(r'ifempty\((\d+)\.sha256Checksum; "NONE"\)', e)
        if mm: return env.get('meta') or 'NONE'
        if re.fullmatch(r'\d+\.bytes_sha256', e): return env['computed']
        if re.fullmatch(r'\d+\.sha256Checksum', e): return env.get('meta') or ''
        mm = re.fullmatch(r'\d+\.(bucket|object|generation|sha256|expires_epoch)', e)
        if mm: return str((env.get('reg') or {}).get(mm.group(1), ''))
        mm = re.fullmatch(r'ifempty\(\d+\.expires_epoch; 0\)', e)
        if mm: return str((env.get('reg') or {}).get('expires_epoch', '') or 0)
        if e == 'formatDate(addMinutes(now; 15); "X")': return str(env['now'] + 900)
        if e.startswith('split("'):
            return e   # handled by caller
        raise ValueError(e)
    return re.sub(r'\{\{(.+?)\}\}', one, expr)
def cond_true(c, rec, env):
    if c['o'] == 'array:notcontain':
        pairs = c['a'][len('{{split("'):].split('"')[0].split(',')
        return resolve(c['b'], rec, env) not in pairs
    a, b = resolve(c['a'], rec, env), resolve(c.get('b', ''), rec, env)
    num = lambda x: float(x) if re.fullmatch(r'-?\d+(\.\d+)?', x) else float('nan')
    return {'text:equal': a == b, 'text:notequal': a != b, 'text:contain': b in a, 'text:notcontain': b not in a,
            'text:startwith': a.startswith(b), 'text:notstartwith': not a.startswith(b),
            'text:pattern': re.search(b, a) is not None, 'text:notpattern': re.search(b, a) is None,
            'number:greater': num(a) > num(b), 'number:lessorequal': not (num(a) > num(b))}[c['o']]
def filt(f, rec, env): return any(all(cond_true(c, rec, env) for c in g) for g in f['conditions'])

# ---- isolated verifier with a test grant for the approved bytes ----
tmp = tempfile.mkdtemp()
store = ApprovalStore(str(Path(tmp) / 'a.json')); grants = str(Path(tmp) / 'g.json')
def approve(content_id, ch, asset_sha, caption, medium):
    fp, pkg = PlacementProvisioner.fingerprint(content_id, asset_sha, ch, '', caption, '2')
    for g in (GATE_CREATIVE, GATE_FINAL_VIDEO if medium == 'video' else GATE_FINAL_ASSET, GATE_PUBLISH):
        store.record(PlacementProvisioner.grant_key(content_id, ch), 'synthetic', g, APPROVE, 'test-harness', fp)
    PlacementProvisioner(store, grants).create_grant(content_id, asset_sha, ch, 'TEST ACCOUNT', '', caption, '2026-10-19 19:00:00', '2', 1999999999,
                                                    medium=medium, test_only=True)
    return pkg
def gate_answer(rec, computed):
    svc = PublishApprovalService(store, grants, now=lambda: C.scheduled_at_to_epoch('2026-10-19 19:00:00'), allow_test_grants=True)
    body = json.loads(resolve(media_route(rec['channel'])[1]['mapper']['data'].replace('{{%d.bytes_sha256}}' % (media_route(rec['channel'])[0]['id'] + 1), computed), rec, {'computed': computed}))
    return body, svc.evaluate(body)

def p2(rec, fetched, meta=None, reg=None, by=None, fetch_url=None):
    """P2 f2 for one placement: variant route, route selector, (IG) hosting register + URL validation, fetch, hash filter, gate, eligible."""
    by = by or BY
    if filt(VARIANT_ROUTE['filter'], rec, {}): return 'BLOCKED_VARIANT', None
    fetch, gate, blocked, sel = media_route(rec['channel'], by)
    if not filt(sel['filter'], rec, {}): return 'NO_ROUTE', None
    env = {'reg': reg, 'now': NOW_EPOCH, 'meta': meta}
    if fetch['module'] == 'http:MakeRequest':
        if not isinstance(reg, dict): return 'BLOCKED_REGISTER', None
        okc = filt(fetch['filter'], rec, env); badc = filt(by[fetch['id'] + 18 + 1000]['filter'], rec, env)
        assert okc != badc, (okc, badc)              # exactly one of the two routes runs (no silent stop)
        if not okc: return 'BLOCKED_URL', None
        assert fetch['mapper']['allowRedirects'] is False
        fetched = fetched(rec['media_url']) if callable(fetched) else fetched
    if fetched is None: return 'FAILED_FETCH', None
    env['computed'] = sha(fetched)
    if filt(blocked['filter'], rec, env):
        assert not filt(gate['filter'], rec, env)
        return 'BLOCKED_HASH', None
    assert filt(gate['filter'], rec, env)
    body, ans = gate_answer(rec, env['computed'])
    return ('UPLOAD' if ans.get('eligible') is True and ans.get('reason') == 'VALID_PUBLISH_APPROVAL' else 'BLOCKED_GATE:' + ans.get('reason', '')), body

# ---- local GCS-like object store: /<bucket>/<object>, generations (versioning off), V4-signature check with a throwaway key ----
KEYDIR = tempfile.mkdtemp()
subprocess.run(['openssl', 'genrsa', '-out', KEYDIR + '/k.pem', '2048'], check=True, capture_output=True)
subprocess.run(['openssl', 'rsa', '-in', KEYDIR + '/k.pem', '-pubout', '-out', KEYDIR + '/p.pem'], check=True, capture_output=True)
from urllib.parse import quote
def _canon(path, params):
    q = '&'.join('%s=%s' % (quote(k, safe='-_.~'), quote(v, safe='-_.~')) for k, v in sorted(params))
    cr = 'GET\n%s\n%s\nhost:storage.googleapis.com\n\nhost\nUNSIGNED-PAYLOAD' % (quote(path, safe='/-_.~'), q)
    return q, cr
def _sts(params, cr):
    d = dict(params); dt = d['X-Goog-Date']
    return 'GOOG4-RSA-SHA256\n%s\n%s/auto/storage/goog4_request\n%s' % (dt, dt[:8], hashlib.sha256(cr.encode()).hexdigest())
def sign_v4(bucket, obj, generation, expires_s=43200):
    """reference V4 signed GET URL (GCS spec) incl. generation INSIDE the signed query; throwaway local key"""
    dt = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(NOW_EPOCH))
    params = [('X-Goog-Algorithm', 'GOOG4-RSA-SHA256'), ('X-Goog-Credential', 'test-signer@example.invalid/%s/auto/storage/goog4_request' % dt[:8]),
              ('X-Goog-Date', dt), ('X-Goog-Expires', str(expires_s)), ('X-Goog-SignedHeaders', 'host'), ('generation', str(generation))]
    q, cr = _canon('/%s/%s' % (bucket, obj), params)
    sig = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', KEYDIR + '/k.pem'], input=_sts(params, cr).encode(), capture_output=True, check=True).stdout.hex()
    return 'https://storage.googleapis.com/%s/%s?%s&X-Goog-Signature=%s' % (bucket, quote(obj, safe='/-_.~'), q, sig)
def verify_v4(path, query):
    params = [(k, v) for k, vs in parse_qs(query, keep_blank_values=True).items() for v in vs]
    sig = [v for k, v in params if k == 'X-Goog-Signature']
    if len(sig) != 1: return False
    params = [(k, v) for k, v in params if k != 'X-Goog-Signature']
    _, cr = _canon(path, params)
    open(KEYDIR + '/s.bin', 'wb').write(bytes.fromhex(sig[0]))
    r = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', KEYDIR + '/p.pem', '-signature', KEYDIR + '/s.bin'], input=_sts(params, cr).encode(), capture_output=True)
    d = dict(params)
    return r.returncode == 0 and time.mktime(time.strptime(d['X-Goog-Date'], '%Y%m%dT%H%M%SZ')) - time.timezone + int(d['X-Goog-Expires']) > time.time()
OBJ, REDIRECT = {}, {}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in REDIRECT: self.send_response(302); self.send_header('Location', REDIRECT[u.path]); self.end_headers(); return
        if 'X-Goog-Signature' in u.query and not verify_v4(u.path, u.query): self.send_response(403); self.end_headers(); return
        name = u.path.lstrip('/'); q = parse_qs(u.query, keep_blank_values=True)
        if name not in OBJ: self.send_response(404); self.end_headers(); return
        gen, data = OBJ[name]
        if 'generation' in q and q['generation'][0] != str(gen): self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
srv = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:%d/' % srv.server_address[1]
def put(name, data):
    gen = OBJ.get(name, (0, b''))[0] + 1000003; OBJ[name] = (gen, data); return gen
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None          # P2: allowRedirects = false
def get(url):
    """P2's fetch: GCS host mapped to the local store; redirects NOT followed; any non-200 -> fetch error"""
    url = url.replace('https://storage.googleapis.com/', BASE)
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=5) as r: return r.read() if r.status == 200 else None
    except (urllib.error.HTTPError, urllib.error.URLError): return None

R = []
def check(name, cond, detail=''):
    R.append(dict(check=name, passed=bool(cond), detail=str(detail)[:300])); print(('PASS ' if cond else 'FAIL ') + name + (' — ' + str(detail)[:150] if detail else ''))

cap = 'Synthetic caption'
base_fb = dict(gate_content_id='test:aki-synthetic:post:S1', channel='facebook_reels', platform_api='facebook', format_variant='9x16', target_account='TEST ACCOUNT',
               asset_sha256=sha(A), schedule_version='2', scheduled_at_epoch=C.scheduled_at_to_epoch('2026-10-19 19:00:00'), caption=cap, title='')
base_fb['packaging_sha256'] = approve(base_fb['gate_content_id'], 'facebook_reels', sha(A), cap, 'video')

# 1 exact approved file (Drive): bytes hash and Drive metadata both match -> gate eligible -> upload of those bytes
res, body = p2(base_fb, A, meta=sha(A))
check('M1 exact approved file -> gate called with the hash of the downloaded bytes -> eligible -> upload', res == 'UPLOAD' and body['asset_sha256'] == sha(A), res)
# 2 changed bytes, same name / same Drive id (Drive reports the new content's sha256)
A2 = bytearray(A); A2[123456] ^= 1; A2 = bytes(A2)
res, _ = p2(base_fb, A2, meta=sha(A2))
check('M2 one byte changed under the same name -> BLOCKED (no gate call, no upload)', res == 'BLOCKED_HASH', res)
res, _ = p2(base_fb, A2, meta=sha(A))
check('M2b Drive metadata still old but downloaded bytes changed -> BLOCKED (computed hash is binding)', res == 'BLOCKED_HASH', res)
res, _ = p2(base_fb, A, meta=sha(A2))
check('M2c bytes match but Drive metadata disagrees -> BLOCKED (both must agree)', res == 'BLOCKED_HASH', res)
rec_changed = dict(base_fb, asset_sha256=sha(A2))
res, _ = p2(rec_changed, A2, meta=sha(A2))
check('M2d record silently re-pointed to the changed file -> gate refuses: the approval is bound to the old bytes', res.startswith('BLOCKED_GATE'), res)
# 3 replaced after an earlier check
#   Drive route: P2 uploads the SAME buffer it hashed (no second download), so a later replacement cannot reach the upload.
fetch_fb = media_route('facebook_reels')[0]
upload_fb = next(m for m in MODS if m['module'] == 'facebook-pages:uploadAReel')
check('M3a Drive: upload maps the very buffer that was hashed ({{%d.data}}) — no re-download between check and upload' % fetch_fb['id'],
      upload_fb['mapper']['data'] == '{{%d.data}}' % fetch_fb['id'])
#   Instagram (f2): media_url must be exactly the signed URL of the object version in the hosting register.
ig = dict(base_fb, channel='instagram_reels', platform_api='instagram', gate_content_id='test:aki-synthetic:post:S2', asset_sha256=sha(FIX))
ig['packaging_sha256'] = approve(ig['gate_content_id'], 'instagram_reels', sha(FIX), cap, 'video')
name = 'aki-ig-staging/%s.mp4' % sha(FIX)
gen = put(TEST_BUCKET + '/' + name, FIX)
REG = dict(bucket=TEST_BUCKET, object=name, generation=str(gen), sha256=sha(FIX), expires_epoch=NOW_EPOCH + 43200)
good = sign_v4(TEST_BUCKET, name, gen)
def igcase(url, reg=REG, by=BYT, rec=ig): return p2(dict(rec, media_url=url), get, reg=reg, by=by)
res, body = igcase(good)
check('I1 signed URL of the registered object version, correct bytes -> eligible', res == 'UPLOAD' and body['asset_sha256'] == sha(FIX), res)
res, _ = igcase(good, by=BY)
check('I1b production blueprint (real private bucket) rejects a perfect URL signed for another bucket', res == 'BLOCKED_URL', res)
res, _ = igcase(good, by=load('UNCONFIGURED'))
check('I1c hosting switched off (bucket UNCONFIGURED) blocks even a perfect URL', res == 'BLOCKED_URL', res)
res, _ = igcase('https://evil.example.com/%s/%s?generation=%d&sha=%s&X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Signature=%s' % (TEST_BUCKET, name, gen, sha(FIX), 'a' * 64))
check('I2 other host with generation= and the hash in the URL -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase('https://storage.googleapis.com.evil.example.com/%s/%s?' % (TEST_BUCKET, name) + good.split('?', 1)[1])
check('I2b look-alike host (storage.googleapis.com.evil...) -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(sign_v4(TEST_BUCKET, name, gen + 1))
check('I3 validly signed URL for a DIFFERENT object version than registered -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(sign_v4(TEST_BUCKET, name, gen + 1), reg=dict(REG, generation=str(gen + 1)))
check('I3b register and URL agree on a generation that does not exist (object replaced/deleted) -> fetch 404 -> FAILED, no upload', res == 'FAILED_FETCH', res)
res, _ = igcase(good + '&generation=%d' % gen)
check('I4a duplicate generation parameter -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good.replace('generation=%d' % gen, 'generation='))
check('I4b empty generation parameter -> BLOCKED_URL', res == 'BLOCKED_URL', res)
other = 'aki-ig-staging/other.mp4'; put(TEST_BUCKET + '/' + other, FIX)
res, _ = igcase(sign_v4(TEST_BUCKET, other, OBJ[TEST_BUCKET + '/' + other][0]) + '&note=' + sha(FIX))
check('I5 hash only in an irrelevant query parameter, different object path -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good, reg=dict(REG, object=other))
check('I5b register points to another object than <asset_sha256>.mp4 -> BLOCKED_URL', res == 'BLOCKED_URL', res)
FIX2 = bytearray(FIX); FIX2[10] ^= 0xFF; FIX2 = bytes(FIX2)
name2 = 'aki-ig-staging/%s.mp4' % sha(FIX); OBJ[TEST_BUCKET + '/' + name2] = (gen, FIX2)       # same version id serving changed bytes (simulated store fault)
res, _ = igcase(good)
check('I6 changed bytes behind the registered version -> computed hash differs -> BLOCKED_HASH', res == 'BLOCKED_HASH', res)
OBJ[TEST_BUCKET + '/' + name2] = (gen, FIX)
res, _ = igcase(good, reg=dict(REG, expires_epoch=NOW_EPOCH + 300))
check('I7a link expires within 15 min (register) -> BLOCKED_URL, no fetch', res == 'BLOCKED_URL', res)
expired = sign_v4(TEST_BUCKET, name, gen, expires_s=1); time.sleep(2)
res, _ = igcase(expired)
check('I7b signature itself expired (store refuses) -> fetch error -> FAILED, no upload', res == 'FAILED_FETCH', res)
res, _ = p2(dict(ig, media_url=good), lambda u: None, reg=REG, by=BYT)
check('I7c URL unreachable -> FAILED, no upload', res == 'FAILED_FETCH', res)
REDIRECT['/%s/%s' % (TEST_BUCKET, name)] = 'https://evil.example.com/x.mp4'
res, _ = igcase(good)
check('I8 store answers with a redirect to another destination -> not followed -> FAILED, no upload', res == 'FAILED_FETCH', res)
REDIRECT.clear()
res, _ = igcase(good.split('&X-Goog-Signature=')[0])
check('I9 signature missing -> BLOCKED_URL', res == 'BLOCKED_URL', res)
appended = sign_v4(TEST_BUCKET, name, gen).replace('&generation=%d' % gen, '').replace('generation=%d&' % gen, '')
check('I9b reference V4 signing: generation is inside the signed query (removing it breaks the signature)',
      verify_v4('/%s/%s' % (TEST_BUCKET, name), good.split('?', 1)[1]) and not verify_v4('/%s/%s' % (TEST_BUCKET, name), appended.split('?', 1)[1]))
res, _ = igcase(good + '#frag')
check('I10 fragment in URL -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good, reg=dict(REG, bucket='other-bucket'))
check('I11 register names another bucket than configured -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good, reg=None)
check('I12 no hosting register -> BLOCKED_REGISTER (parse error handler -> BLOCKED + log)', res == 'BLOCKED_REGISTER', res)
res, _ = igcase(good, reg=dict(REG, sha256='0' * 64))
check('I13 register sha256 differs from the approved asset -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good, reg={k: v for k, v in REG.items() if k != 'expires_epoch'})
check('I14 register without expires_epoch -> BLOCKED_URL (not stuck between routes)', res == 'BLOCKED_URL', res)
res, _ = igcase(good + '&x=a@evil.example')
check('I15 "@" in an otherwise valid signed URL -> BLOCKED_URL', res == 'BLOCKED_URL', res)
for tag, cut in (('I16 X-Goog-Credential missing', 'X-Goog-Credential='), ('I17 X-Goog-Expires missing', 'X-Goog-Expires=')):
    q = '&'.join(x for x in good.split('?', 1)[1].split('&') if not x.startswith(cut))
    res, _ = igcase(good.split('?', 1)[0] + '?' + q)
    check(tag + ' -> BLOCKED_URL', res == 'BLOCKED_URL', res)
res, _ = igcase(good.replace('X-Goog-Algorithm=GOOG4-RSA-SHA256', 'X-Goog-Algorithm=GOOG4-HMAC-SHA256'))
check('I18 other signing algorithm -> BLOCKED_URL', res == 'BLOCKED_URL', res)
# 4 wrong / missing hash
res, _ = p2(dict(base_fb, asset_sha256='0' * 64), A, meta=sha(A))
check('M4a wrong registered hash -> BLOCKED', res == 'BLOCKED_HASH', res)
res, _ = p2(dict(base_fb, asset_sha256=''), A, meta=sha(A))
check('M4b missing registered hash -> BLOCKED', res == 'BLOCKED_HASH', res)
res, _ = p2(base_fb, A, meta=None)
check('M4c Drive returns no sha256Checksum -> BLOCKED', res == 'BLOCKED_HASH', res)
res, _ = p2(base_fb, None)
check('M4d file unreachable (download error) -> FAILED, no upload', res == 'FAILED_FETCH', res)
# 5 wrong format variant
ff = dict(base_fb, channel='facebook_feed', format_variant='9x16jpg', asset_sha256=sha(C9x16))
res, _ = p2(ff, C9x16, meta=sha(C9x16))
check('M5a TikTok 9x16 JPEG registered on facebook_feed -> BLOCKED_VARIANT', res == 'BLOCKED_VARIANT', res)
ff2 = dict(base_fb, channel='facebook_feed', format_variant='4x5', gate_content_id='test:aki-synthetic:post:S3', asset_sha256=sha(B4x5))
ff2['packaging_sha256'] = approve(ff2['gate_content_id'], 'facebook_feed', sha(B4x5), cap, 'poster')
res, _ = p2(ff2, C9x16, meta=sha(C9x16))
check('M5b record says 4x5 but the file is the 9x16 variant -> BLOCKED_HASH', res == 'BLOCKED_HASH', res)
res, _ = p2(ff2, B4x5, meta=sha(B4x5))
check('M5c correct 4x5 variant -> eligible', res == 'UPLOAD', res)
srv.shutdown()
out = dict(test='approved file <-> published file binding (P2 f2, synthetic files, real P2 filter JSON, real PR #38 verifier, GCS-like local store)',
           level='LOCAL (logic + local HTTP); Make sha256() itself proven separately in Make (T1 v4, 14/14)', results=R, passed=sum(r['passed'] for r in R), total=len(R),
           not_proven_here='Real GCS hosting route (needs hosting consent + GCP access); text:pattern operator semantics in Make (see T1 URL-filter run); '
                           'V4 signature produced by a local reference implementation + throwaway key, not by Google.')
json.dump(out, open(HERE / 'TEST_RESULTS_MEDIA_BINDING.json', 'w'), indent=1)
print('SUMMARY', out['passed'], '/', out['total'])
