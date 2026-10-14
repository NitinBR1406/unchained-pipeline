"""P2 failure/recovery safety, without any platform call.

Part A: structural proofs on the ACTUAL P2 blueprint (P2_blueprint.json == what is deployed to Make 9974134).
Part B: a state-machine simulation of P2 per placement that uses the blueprint's own selection groups and its own
        OUTCOME_UNKNOWN classifier, with mocked gate / Drive / platform responses (timeouts, 5xx, garbage, success).
Writes TEST_RESULTS_P2_SAFETY.json."""
import json, re, re, time
from collections import Counter

bp = json.load(open('P2_blueprint.json'))
reg = json.load(open('AKI_W01_CAMPAIGN_REGISTRY.json'))
R = []
def check(name, cond, detail=''):
    R.append(dict(check=name, passed=bool(cond), detail=str(detail)[:300])); print(('PASS ' if cond else 'FAIL ') + name + (' — ' + str(detail)[:160] if detail else ''))

def walk(flow, path=()):
    for m in flow:
        yield m, path
        for i, r in enumerate(m.get('routes', [])): yield from walk(r['flow'], path + ((m['id'], i),))
        for e in m.get('onerror', []): yield e, path + (('onerror', m['id']),)
mods = list(walk(bp['flow']))
byid = {m['id']: m for m, _ in mods}
UPLOADS = {'instagram-business:CreateAReelPost', 'instagram-business:CreatePostPhoto', 'facebook-pages:uploadAReel',
           'facebook-pages:UploadPhoto', 'youtube:ActionUploadVideo'}
uploads = [(m, p) for m, p in mods if m['module'] in UPLOADS]

# ---------- Part A: structure ----------
GATES = [m for m, _ in mods if m['module'] == 'http:ActionSendDataAPIKeyAuth']
FETCH = [m for m, _ in mods if m['module'] in ('google-drive:getAFile', 'http:MakeRequest')]
SEL = [m for m, _ in mods if '(api ' in (m.get('filter') or {}).get('name', '')]   # route selectors (Drive fetch / IG hosting-register parse)
check('A1 HTTP modules: only the 6 per-route approval gates and the 2 Instagram media fetches (GET); no TikTok call',
      len(GATES) == 6 and sorted(m['mapper']['method'] for m in FETCH if m['module'] == 'http:MakeRequest') == ['get', 'get']
      and not any('tiktok' in json.dumps(m.get('mapper', {})).lower() and m['module'].startswith('http') for m, _ in mods))
def path_ids(path): return [rid for rid, _ in path if rid != 'onerror']
def ancestors_in_route(m, p):
    """modules that run before m inside its route (walk the route flows along the path)"""
    seen, flow = [], bp['flow']
    for rid, idx in p:
        if rid == 'onerror': break
        for x in flow:
            if x['id'] == rid: break
            seen.append(x)
        seen.append(byid[rid]); flow = byid[rid]['routes'][idx]['flow']
    for x in flow:
        if x['id'] == m['id']: break
        seen.append(x)
    return seen
per_upload = []
for m, p in uploads:
    before = ancestors_in_route(m, p)
    mods_before = [x['module'] for x in before]
    fetch = next(x for x in before if x['module'] in ('google-drive:getAFile', 'http:MakeRequest'))
    hashv = next(x for x in before if x['module'] == 'util:SetVariables' and 'bytes_sha256' in json.dumps(x['mapper']))
    gatem = next(x for x in before if x['module'] == 'http:ActionSendDataAPIKeyAuth')
    hv = '{{%d.bytes_sha256}}' % hashv['id']
    gate_cond = json.dumps(gatem['filter']['conditions'])
    per_upload.append(dict(
        order=before.index(fetch) < before.index(hashv) < before.index(gatem),
        hashes_fetched=hashv['mapper']['variables'][0]['value'] == '{{sha256(%d.data)}}' % fetch['id'],
        gate_uses_computed=('\\"asset_sha256\\":\\"%s\\"' % hv) in json.dumps(gatem['mapper']['data']) or ('"asset_sha256":"%s"' % hv) in gatem['mapper']['data'],
        gate_needs_match=hv in gate_cond and '{{1.data.asset_sha256}}' in gate_cond,
        drive_meta=(fetch['module'] != 'google-drive:getAFile') or ('{{%d.sha256Checksum}}' % fetch['id']) in gate_cond,
        ig_pinned=(fetch['module'] != 'http:MakeRequest') or (fetch['mapper']['allowRedirects'] is False and all(t in json.dumps(fetch['filter']) for t in
                  ('text:startwith', 'https://storage.googleapis.com/', '[?&]generation={{', 'generation=.*generation=', 'X-Goog-Signature', 'expires_epoch'))),
        same_bytes=(fetch['module'] == 'http:MakeRequest' and '{{1.data.media_url}}' in json.dumps(m['mapper'])) or ('{{%d.data}}' % fetch['id']) in json.dumps(m['mapper']),
        eligible=(lambda f: any(c['b'] == 'VALID_PUBLISH_APPROVAL' and c['o'] == 'text:equal' for c in f['conditions'][0])
                 and any(c['b'] == 'EOK' and 'eligible = true' in c['a'] for c in f['conditions'][0]) and len(f['conditions']) == 1)(
                 next(x for x in reversed(before) if x['module'] == 'datastore:GetRecord')['filter']),
        fenced=next(x for x in reversed(before) if x['module'] == 'datastore:GetRecord')['id'] == int(re.search(r'\{\{(\d+)\.claim_token', json.dumps(m['filter'])).group(1))
               and '{{49.owner}}' in json.dumps(m['filter'])))
check('A2 6 uploads; each: fetch -> sha256 over fetched bytes -> gate -> upload', len(uploads) == 6 and all(u['order'] and u['hashes_fetched'] for u in per_upload), per_upload)
check('A3 gate request carries the COMPUTED bytes hash (not the record value) -> a changed file invalidates the approval', all(u['gate_uses_computed'] for u in per_upload))
check('A4 gate only called when computed hash == registered; Drive routes also require Drive sha256Checksum == registered',
      all(u['gate_needs_match'] and u['drive_meta'] for u in per_upload))
check('A5 Instagram: URL must be generation-pinned and content-addressed; redirects not followed', all(u['ig_pinned'] for u in per_upload))
check('A6 the upload uses the same fetched buffer (FB/YT) or the same pinned URL (IG)', all(u['same_bytes'] for u in per_upload))
check('A5b Instagram route parses the hosting register before fetching', all(byid[f['id'] + 15]['module'] == 'json:ParseJSON' and 'hosting_register' in json.dumps(byid[f['id'] + 15])
      for f in FETCH if f['module'] == 'http:MakeRequest'))
check('A7 every upload behind eligible==true AND reason==VALID_PUBLISH_APPROVAL', all(u['eligible'] for u in per_upload))
check('A7b every upload behind a fresh ownership re-read (claim_token = own execution id, same attempt, PUBLISHING)', all(u['fenced'] for u in per_upload))
def onerror_status(mid):
    return [e['mapper']['data'].get('status') for e in byid[mid].get('onerror', []) if e['module'] == 'datastore:UpdateRecord']
check('A8 gate HTTP error / unreadable answer / fetch error -> FAILED and logged (nothing published)',
      all(onerror_status(g['id']) == ['FAILED'] for g in GATES) and all(onerror_status(g['id'] + 1) == ['FAILED'] for g in GATES)
      and all(onerror_status(f['id']) == ['FAILED'] for f in FETCH) and all(g['parameters'].get('handleErrors') is True for g in GATES))
blocked_hash = [m for m, _ in mods if m['module'] == 'datastore:UpdateRecord' and 'ASSET_HASH_MISMATCH' in json.dumps(m['mapper'])]
check('A9 hash mismatch / missing hash / unpinned URL -> BLOCKED route on every media route (6)', len(blocked_hash) == 6
      and all(m['mapper']['data']['status'] == 'BLOCKED' for m in blocked_hash))
cls = onerror_status(uploads[0][0]['id'])[0]
definite = re.search(r'split\("([^"]+)"', cls.replace('\\"', '"')).group(1).split(',')
def classify(err_type):  # same expression P2 uses: exact element match in the list
    return 'FAILED' if (err_type or 'UNKNOWN') in definite else 'OUTCOME_UNKNOWN'
# T2 v3: each handler must read the error of ITS OWN upload module ({{<id>.error.type}}; bare error.* is empty)
check('A10 upload error handlers use the exact-match OUTCOME_UNKNOWN classifier (no substring match), bound to their own upload module',
      all(onerror_status(m['id'])[0] == cls.replace('%d.error.type' % uploads[0][0]['id'], '%d.error.type' % m['id'])
          and '%d.error.type' % m['id'] in onerror_status(m['id'])[0] for m, _ in uploads) and 'contains(split(' in cls)
check('A11 timeout / connection / 5xx / unknown / partial type names -> OUTCOME_UNKNOWN',
      all(classify(t) == 'OUTCOME_UNKNOWN' for t in ('ConnectionError', 'RuntimeError', 'TimeoutError', 'Data', 'Error', '', None)))
check('A12 definite rejections (auth/config) -> FAILED (retryable)', all(classify(t) == 'FAILED' for t in ('InvalidAccessTokenError', 'InvalidConfigurationError', 'AccountValidationError')))
check('A12b DataError at a publish call -> OUTCOME_UNKNOWN (Make uses DataError for both never-sent and answered requests; T2 v3)', classify('DataError') == 'OUTCOME_UNKNOWN')
sel = byid[1]['mapper']['filter']
statuses = {c['b'] for g in sel for c in g if c['a'] == 'status'}
check('A13 selection only READY or FAILED (never PUBLISHING / OUTCOME_UNKNOWN / BLOCKED / PUBLISHED)', statuses == {'READY', 'FAILED'}, statuses)
lk = byid[51]
check('A14 exclusive lock: insert-only (overwrite=No), key placement+next attempt, Ignore on duplicate',
      lk['module'] == 'datastore:AddRecord' and lk['mapper']['overwrite'] is False and lk['mapper']['key'] == 'plock:{{1.key}}:a{{1.data.attempt_count + 1}}'
      and [e['module'] for e in lk.get('onerror', [])] == ['builtin:Ignore'])
order = [m['id'] for m in bp['flow']]
check('A15 owner token, then lock BEFORE the claim update and before every fetch/gate/upload', order == [1, 49, 51, 50, 70], order)
check('A15b owner token is a fresh {{uuid}} per bundle (var.execution.id is empty in Make runs)', byid[49]['mapper']['variables'][0]['value'] == '{{uuid}}')
check('A16 gate request carries target_account', all('"target_account":"{{1.data.target_account}}"' in g['mapper']['data'] for g in GATES))
vr = [byid[m['id'] + 1000] for m, _ in mods if 'CHANNEL_VARIANT_MISMATCH' in json.dumps(m.get('mapper', {}))]   # routing filter sits on the fencing re-read
check('A17 wrong format variant for the channel -> BLOCKED (exact channel:variant pair list)', len(vr) == 1 and 'array:notcontain' in json.dumps(vr[0]['filter'])
      and len(SEL) == 6 and all('format_variant' in json.dumps(f['filter']) for f in SEL))

check('A18 claim write failure is logged (no silent stuck record)', [e['module'] for e in byid[50].get('onerror', [])] == ['datastore:AddRecord'])
hashmods = [m for m, _ in mods if m['module'] == 'util:SetVariables' and 'bytes_sha256' in json.dumps(m['mapper'])]
check('A19 hash computation error -> logged + BLOCKED on all 6 routes', len(hashmods) == 6 and all(
      [e['module'] for e in m.get('onerror', [])] == ['datastore:AddRecord', 'datastore:GetRecord', 'datastore:UpdateRecord'] and m['onerror'][2]['mapper']['data']['status'] == 'BLOCKED' for m in hashmods))
oks = [m for m, p in mods if m['module'] == 'datastore:UpdateRecord' and m['mapper']['data'].get('status') == 'PUBLISHED' and not any(x == 'onerror' for x, _ in p)]
check('A20 every id write-back after an upload logs its failure (record stays PUBLISHING, never re-uploaded)', len(oks) == 6 and all(m.get('onerror') for m in oks))
check('A21 media routes select on platform_api + channel + variant, and require a non-empty registered hash',
      len(SEL) == 6 and all('{{1.data.platform_api}}' in json.dumps(f['filter']) for f in SEL) and all('"b": ""' in json.dumps(g['filter']) for g in GATES))
own_writes = [m for m, p in mods if m['module'] == 'datastore:UpdateRecord' and m['id'] != 50]
unfenced = [m['id'] for m in own_writes if '{{49.owner}}' not in json.dumps(m.get('filter', {}))]
check('A22 every status write after the claim is fenced on ownership (no stale execution overwrites another attempt)', unfenced == [], unfenced)

# ---------- Part B: simulation ----------
NOW = [int(time.time())]
def selected(r):
    def op(o, a, b):
        return {'text:equal': lambda: str(a) == str(b), 'notexist': lambda: a in (None, ''), 'number:less': lambda: float(a or 0) < float(b)}[o]()
    return any(all(op(c['o'], r.get(c['a']), c.get('b')) for c in g) for g in sel)
class World:
    def __init__(self, recs): self.db = {r['placement_id']: dict(r) for r in recs}; self.posts = Counter(); self.errlog = []; self.locks = set()
    def search(self): return [dict(r) for r in self.db.values() if selected(r)]
def due(r):
    return (0 < r['scheduled_at_epoch'] <= NOW[0] and r['scheduled_at_epoch'] > NOW[0] - 6 * 3600 and not r.get('lock_until')
            and (r['platform_api'] != 'instagram' or r.get('media_url')) and r['gate_content_id'].startswith('aki:post:'))
def run_one(w, snap, exec_id, gate='ok', drive='ok', platform='ok', after_claim=None, media='ok'):
    """one bundle of P2 version e for record snapshot `snap` (taken at search time)."""
    k = snap['placement_id']
    if not due(snap): return 'not_due'
    key = 'plock:%s:a%d' % (k, snap['attempt_count'] + 1)                               # module 51: insert-only lock FIRST
    if key in w.locks: return 'lost_claim'
    w.locks.add(key)
    w.db[k].update(status='PUBLISHING', attempt_count=snap['attempt_count'] + 1, lock_until='+30m')   # module 50
    if after_claim: after_claim()
    if snap['platform_api'] == 'tiktok':
        w.db[k].update(status='BLOCKED', lock_until=''); return 'blocked_tiktok'
    if drive == 'error':                                                                 # Drive download / media URL fetch error
        w.db[k].update(status='FAILED', lock_until=''); w.errlog.append((k, 'FETCH_FAIL')); return 'failed_fetch'
    if media in ('mismatch', 'missing', 'unpinned') or drive == 'sha_mismatch':           # computed/meta hash or pinning check
        w.db[k].update(status='BLOCKED', lock_until=''); return 'blocked_sha'
    if gate in ('timeout', '5xx', 'conn'):
        w.db[k].update(status='FAILED', lock_until=''); w.errlog.append((k, 'GATE_HTTP_FAIL')); return 'failed_gate'
    if gate == 'garbage':
        w.db[k].update(status='FAILED', lock_until=''); w.errlog.append((k, 'GATE_PARSE_FAIL')); return 'failed_parse'
    if gate in ('no', 'valid_but_not_eligible'):
        w.db[k].update(status='BLOCKED', lock_until=''); return 'blocked'
    if platform == 'ok':
        w.posts[k] += 1; w.db[k].update(status='PUBLISHED', platform_post_id='P-' + k, lock_until=''); return 'published'
    if platform == 'timeout_after_success':
        w.posts[k] += 1                                                               # the platform DID create the post
        st = classify('ConnectionError'); w.db[k].update(status=st); w.errlog.append((k, st)); return st
    if platform == 'rejected':
        st = classify('InvalidAccessTokenError'); w.db[k].update(status=st, lock_until=''); w.errlog.append((k, st)); return st
    if platform == 'data_error':
        w.posts[k] += 1                                                               # worst case: the post WAS created
        st = classify('DataError'); w.db[k].update(status=st); w.errlog.append((k, st)); return st
def run(w, **kw):
    out = []
    for snap in w.search():
        out.append(run_one(w, snap, 'exec-%d' % len(out), **kw))
    return out
base = [dict(p, publishable='TRUE', approval_status='APPROVED', status='READY', scheduled_at_epoch=NOW[0] - 60,
             media_url='https://storage.example.invalid/aki/%s.mp4?generation=1' % p['asset_sha256'] if p['platform_api'] == 'instagram' else '', attempt_count=0,
             platform_post_id='', lock_until='', claim_token='')
        for p in reg['placements'] if p['post_id'] == 'aki:post:D01-V01']
ig = next(p for p in base if p['channel'] == 'instagram_reels')

w = World([ig]); r1 = run(w, gate='timeout'); r2 = run(w, gate='timeout'); r3 = run(w, gate='timeout'); r4 = run(w)
check('B1 gate timeout x3: FAILED each time, retried, stops after 3 attempts, nothing posted, 3 log lines',
      r1 == r2 == r3 == ['failed_gate'] and r4 == [] and w.db[ig['placement_id']]['attempt_count'] == 3 and sum(w.posts.values()) == 0 and len(w.errlog) == 3)
for g, label in (('5xx', 'B2 gate 5xx'), ('conn', 'B3 gate unreachable'), ('garbage', 'B4 unreadable gate answer'), ('valid_but_not_eligible', 'B5 technically valid call answering eligible:false')):
    w = World([ig]); res = run(w, gate=g)
    check(label + ' -> no publication', sum(w.posts.values()) == 0 and res[0] in ('failed_gate', 'failed_parse', 'blocked'), res)
w = World([ig]); res = run(w, platform='timeout_after_success'); again = run(w); again2 = run(w)
check('B6 timeout AFTER a possibly successful upload -> OUTCOME_UNKNOWN, never re-uploaded (1 post total)',
      res == ['OUTCOME_UNKNOWN'] and again == [] and again2 == [] and w.posts[ig['placement_id']] == 1)
w = World([ig]); res = run(w, platform='rejected'); res2 = run(w)
check('B7 definite auth/config rejection -> FAILED and retried only that placement', res == ['FAILED'] and res2 == ['published'])
w = World([ig]); res = run(w, platform='data_error'); res2 = run(w)
check('B7b DataError at publish -> OUTCOME_UNKNOWN, never auto-retried (left for R1/human)', res == ['OUTCOME_UNKNOWN'] and res2 == [])
w = World(base); first = run(w)
fb = next(p for p in base if p['channel'] == 'facebook_reels')
w.db[fb['placement_id']].update(status='FAILED', platform_post_id='', attempt_count=1)       # one channel failed
second = run(w)
check('B8 only the failed channel placement is retried; published siblings untouched',
      second == ['published'] and w.posts[fb['placement_id']] == 2 - 1 + 1 and all(w.posts[k] == 1 for k in w.posts if k != fb['placement_id']), (first, second))
w = World([ig]); snapA = w.search()[0]; snapB = w.search()[0]                                  # two executions saw READY
resB = []
resA = run_one(w, snapA, 'exec-A', after_claim=lambda: resB.append(run_one(w, snapB, 'exec-B')))
check('B9 concurrent runs (B claims while A is between claim and re-read) -> exactly one upload', w.posts[ig['placement_id']] == 1, (resA, resB))
w = World([ig]); run(w); run(w); run(w)
check('B10 repeated runs after success never post again', w.posts[ig['placement_id']] == 1)
w = World([dict(ig, gate_content_id='test:aki-synthetic:post:D01-V01')])
check('B11 synthetic test placement is never claimed', run(w) == ['not_due'])
w = World([next(p for p in base if p['channel'] == 'youtube_shorts')]); res = run(w, drive='sha_mismatch')
check('B12 Drive bytes differ from registered sha -> BLOCKED, no upload', res == ['blocked_sha'] and sum(w.posts.values()) == 0)
w = World([next(p for p in base if p['channel'] == 'youtube_shorts')]); res = run(w, drive='error')
check('B13 Drive download error -> FAILED (retryable), logged, no upload', res == ['failed_fetch'] and len(w.errlog) == 1)

for mode, label in (('mismatch', 'B14 hosted bytes differ'), ('missing', 'B15 registered hash missing'), ('unpinned', 'B16 media URL not generation-pinned')):
    w = World([ig]); res = run(w, media=mode)
    check(label + ' -> BLOCKED, no gate call, no upload', res == ['blocked_sha'] and sum(w.posts.values()) == 0)
w = World([ig]); snapA = w.search()[0]; snapB = w.search()[0]
run_one(w, snapA, 'A'); rb = run_one(w, snapB, 'B')
check('B17 stale bundle after a finished publication: lock rejects it and the PUBLISHED record is NOT rewritten',
      rb == 'lost_claim' and w.db[ig['placement_id']]['status'] == 'PUBLISHED' and w.posts[ig['placement_id']] == 1)

uploads = [m for m, _ in mods if m['module'].split(':')[0] in ('instagram-business', 'facebook-pages', 'youtube') and 'Get' not in m['module']]
wb_ok = []
for u in uploads:
    rd = byid[u['id'] + 20]   # write-back ownership read (b+26 where upload = b+6)
    h = rd.get('onerror', [])
    wb_ok.append(rd['module'] == 'datastore:GetRecord' and len(h) == 1 and h[0]['mapper']['data']['error_type'].startswith('WRITEBACK_FAIL_AFTER_UPLOAD a=')
                 and ' id={{' in h[0]['mapper']['data']['error_type'])
check('A23 write-back ownership read failing after an upload logs the platform id (WRITEBACK_FAIL_AFTER_UPLOAD a=.. id=..) for R1',
      len(uploads) == 6 and all(wb_ok), [u['id'] for u in uploads])
residual = ('Model test, not real Make concurrency. Run in Make on a synthetic test store (2026-10-14): duplicate-key rejection, '
            'second concurrent execution refused, Ignore semantics, sha256() over bytes, lock/claim/recovery cases L1-L6. '
            'Residual: an old run that already uploaded before a human recovery can lead to a second upload by the next attempt (L6); '
            'no compare-and-set in Make data stores. A crash between the lock insert and the claim update leaves the record READY with '
            'its lock present: it is then never selected again with the same attempt (fail-closed, visible as plock:<placement>:a<n>).')
out = dict(test='P2 safety (structure + mocked simulation)', run_at_epoch=NOW[0], results=R, residual_risk=residual,
           passed=sum(r['passed'] for r in R), total=len(R))
json.dump(out, open('TEST_RESULTS_P2_SAFETY.json', 'w'), indent=1)
print('SUMMARY', out['passed'], '/', out['total'])
