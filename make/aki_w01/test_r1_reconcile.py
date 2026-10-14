"""R1 v2 reconcile — local model over the REAL filter JSON of R1_blueprint.json (synthetic records/posts only).
The Error_Log search + id extraction (modules 3-5) is mirrored in Python; all decision filters (by-id proof, mismatch,
candidate aggregation) are evaluated exactly as stored. Writes TEST_RESULTS_R1_RECONCILE.json."""
import json, re, time
from datetime import datetime, timezone, timedelta
bp = json.load(open('R1_blueprint.json'))
def walk(f):
    for m in f:
        yield m
        for r in m.get('routes') or []: yield from walk(r['flow'])
        for e in m.get('onerror') or []: yield e
BY = {m['id']: m for m in walk(bp['flow'])}
ROUTES_ID = BY[11]['routes']; ROUTES_C = BY[12]['routes']
ep = lambda iso: int(datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())
iso = lambda dt: dt.strftime('%Y-%m-%dT%H:%M:%SZ')
NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)

def resolver(rec, ctx, sid):
    start = ep(rec.get('attempt_started_at') or iso(datetime.fromisoformat(rec['lock_until'].replace('Z', '+00:00')) - timedelta(minutes=45)))
    def val(path):
        n, rest = path.split('.', 1)
        if n == '1' and rest.startswith('data.'): return rec.get(rest[5:], '')
        if n == '5': return {'stored_id': sid[0], 'stored_ids': str(sid[1])}[rest]
        x = ctx.get(int(n), {})
        for k in rest.split('.'): x = (x or {}).get(k, '') if isinstance(x, dict) else ''
        return x
    def one(m):
        e = m.group(1)
        if e.startswith('formatDate(addMinutes(ifempty(1.data.attempt_started_at') and '-2' in e: return str(start - 120)
        if e.startswith('formatDate(addHours(ifempty(1.data.attempt_started_at'): return str(start + 6 * 3600)
        mm = re.fullmatch(r'formatDate\((\d+\.[\w.]+); "X"\)', e)
        if mm: return str(ep(val(mm.group(1)))) if val(mm.group(1)) else ''
        if e == 'if(1.data.channel = "instagram_reels"; "REELS"; "FEED")': return 'REELS' if rec['channel'] == 'instagram_reels' else 'FEED'
        if re.fullmatch(r'\d+\.[\w.]+', e): return str(val(e))
        raise ValueError(e)
    return lambda s: re.sub(r'\{\{(.+?)\}\}', one, s)
def cond(c, R):
    a, b = R(c['a']), R(c.get('b', ''))
    n = lambda x: float(x) if re.fullmatch(r'-?\d+(\.\d+)?', str(x)) else float('nan')
    return {'text:equal': a == b, 'text:notequal': a != b, 'text:contain': b in a, 'text:startwith': a.startswith(b),
            'number:greaterorequal': n(a) >= n(b), 'number:less': n(a) < n(b), 'number:lessorequal': n(a) <= n(b), 'number:greater': n(a) > n(b)}[c['o']]
def filt(f, R): return any(all(cond(c, R) for c in g) for g in f['conditions'])

def r1(rec, errlog, platform):
    """returns (record updates, decision). platform: {'by_id': {id: obj}, 200: [...ig], 210: [...fb videos], 220: [...fb posts], 230: [...yt search]}"""
    R0 = resolver(rec, {}, ('', 0))
    if rec['status'] not in ('OUTCOME_UNKNOWN', 'PUBLISHING') or not filt(BY[2]['filter'], lambda s: s.replace(
            '{{if(1.data.lock_until; formatDate(1.data.lock_until; "X"); 0)}}', str(ep(rec['lock_until']) if rec['lock_until'] else 0)).replace(
            '{{formatDate(now; "X")}}', str(int(NOW.timestamp()))).replace('{{1.data.platform_api}}', rec['platform_api'])):
        return {}, 'NOT_SELECTED'
    ids = sorted({re.sub(r'^.* id=([^ ]+).*$', r'\1', e['error_type']) for e in errlog
                  if e['post_id'] == rec['key'] and 'WRITEBACK_' in e['error_type'] and ' a=%s id=' % rec['attempt_count'] in e['error_type']})
    sid = (ids[0] if len(ids) == 1 else '', len(ids))
    if len(ids) > 1: return {'reconcile_status': 'CONFLICTING_STORED_IDS'}, 'CONFLICT'
    if len(ids) == 1:
        rt = next(r for r in ROUTES_ID if filt(r['flow'][0]['filter'], resolver(rec, {}, sid)))
        get = rt['flow'][0]; obj = platform['by_id'].get(sid[0])
        if obj is None: return get['onerror'][0]['mapper']['data'], 'STORED_ID_NOT_VERIFIABLE'
        R = resolver(rec, {get['id']: obj}, sid)
        okm, badm = rt['flow'][1]['routes'][0]['flow'][0], rt['flow'][1]['routes'][1]['flow'][0]
        o, b = filt(okm['filter'], R), filt(badm['filter'], R)
        assert o != b, (o, b)
        return (okm if o else badm)['mapper']['data'], ('PROVEN' if o else 'MISMATCH')
    rt = next(r for r in ROUTES_C if filt(r['flow'][0]['filter'], resolver(rec, {}, sid)))
    src, agg = rt['flow'][0], rt['flow'][1]
    cands = [it['id'] for it in platform.get(src['id'], []) if filt(agg['filter'], resolver(rec, {src['id']: it}, sid))]
    st = 'NOT_FOUND' if not cands else ('CANDIDATE_UNVERIFIED' if len(cands) == 1 else 'MULTIPLE_CANDIDATES')
    data = dict(rt['flow'][2]['mapper']['data']); data['reconcile_status'] = st; data['_candidates'] = cands
    return data, st

T = []
def check(name, c, d=''):
    T.append(dict(check=name, passed=bool(c), detail=str(d)[:200])); print(('PASS ' if c else 'FAIL ') + name + (' — ' + str(d)[:150] if d else ''))
start = NOW - timedelta(hours=1)
base = dict(key='aki:post:D01-V01:instagram_reels', channel='instagram_reels', platform_api='instagram', caption='Exact caption 🎶', title='',
            status='OUTCOME_UNKNOWN', attempt_count=1, attempt_started_at=iso(start), lock_until=iso(start + timedelta(minutes=45)))
IGA = '17841457677776171'
ig = lambda i, ts, cap='Exact caption 🎶', owner=IGA, t='REELS': dict(id=i, caption=cap, owner={'id': owner}, media_product_type=t, timestamp=iso(ts))

d, s = r1(base, [], {'by_id': {}, 200: [ig('OLD', start - timedelta(days=30))]})
check('R1-1 older post with the same caption (30 days before the attempt) -> NOT_FOUND, never PUBLISHED', s == 'NOT_FOUND' and 'status' not in d, s)
yt = dict(base, key='aki:post:D01-V01:youtube_shorts', channel='youtube_shorts', platform_api='youtube', title='Aakhri Ishq (cover)', caption='x')
d, s = r1(yt, [], {'by_id': {}, 230: [dict(id='OTHER', title='Aakhri Ishq (cover)', dateCreated=iso(start + timedelta(minutes=5)))]})
check('R1-2 same-name YouTube video (global search, channel unverifiable) inside the window -> CANDIDATE_UNVERIFIED only', s == 'CANDIDATE_UNVERIFIED' and 'status' not in d, s)
d, s = r1(yt, [], {'by_id': {}, 230: [dict(id='OLD', title='Aakhri Ishq (cover)', dateCreated=iso(start - timedelta(days=200)))]})
check('R1-2b same-name YouTube video from long before the attempt -> NOT_FOUND', s == 'NOT_FOUND', s)
d, s = r1(base, [], {'by_id': {}, 200: [ig('C1', start + timedelta(minutes=3))]})
check('R1-3 one plausible candidate (text+account+type+window) -> CANDIDATE_UNVERIFIED, status unchanged, id listed', s == 'CANDIDATE_UNVERIFIED' and 'status' not in d and d['_candidates'] == ['C1'], d.get('_candidates'))
d, s = r1(base, [], {'by_id': {}, 200: [ig('C1', start + timedelta(minutes=3)), ig('C2', start + timedelta(minutes=9))]})
check('R1-4 multiple candidates -> MULTIPLE_CANDIDATES, status unchanged', s == 'MULTIPLE_CANDIDATES' and 'status' not in d, s)
d, s = r1(base, [], {'by_id': {}, 200: []})
check('R1-5 delayed visibility (post not yet listed) -> NOT_FOUND, status unchanged (P2 never re-selects OUTCOME_UNKNOWN: no re-upload)', s == 'NOT_FOUND' and 'status' not in d, s)
log = [dict(post_id=base['key'], error_type='WRITEBACK_FAIL_AFTER_UPLOAD a=1 id=17890001')]
d, s = r1(base, log, {'by_id': {'17890001': ig('17890001', start + timedelta(minutes=2))}})
check('R1-6 proven match via stored platform id (own upload response, this attempt, verified by id) -> PUBLISHED / RECONCILED_BY_ID',
      s == 'PROVEN' and d['status'] == 'PUBLISHED' and d['published_via'] == 'RECONCILED_BY_ID', s)
d, s = r1(base, log, {'by_id': {'17890001': ig('17890001', start + timedelta(minutes=2), owner='999')}})
check('R1-7 stored id but other account -> STORED_ID_MISMATCH, not PUBLISHED', s == 'MISMATCH' and 'status' not in d, s)
d, s = r1(base, log, {'by_id': {'17890001': ig('17890001', start + timedelta(minutes=2), t='FEED')}})
check('R1-7b stored id but wrong media product type -> MISMATCH', s == 'MISMATCH', s)
d, s = r1(base, log, {'by_id': {}})
check('R1-8 stored id cannot be looked up -> STORED_ID_NOT_VERIFIABLE, not PUBLISHED', s == 'STORED_ID_NOT_VERIFIABLE' and 'status' not in d, s)
old_attempt = [dict(post_id=base['key'], error_type='WRITEBACK_FAIL_AFTER_UPLOAD a=0 id=17880000')]
d, s = r1(base, old_attempt, {'by_id': {'17880000': ig('17880000', start + timedelta(minutes=2))}, 200: []})
check('R1-9 stored id from ANOTHER attempt is ignored -> candidate search (no proof)', s == 'NOT_FOUND', s)
two = log + [dict(post_id=base['key'], error_type='WRITEBACK_SKIPPED_CLAIM_LOST a=1 id=17890002 owner=x')]
d, s = r1(base, two, {'by_id': {}})
check('R1-10 two different stored ids for one attempt -> CONFLICTING_STORED_IDS (human)', s == 'CONFLICT', s)
fb = dict(base, key='aki:post:D02-S1:facebook_feed', channel='facebook_feed', platform_api='facebook')
d, s = r1(fb, [dict(post_id=fb['key'], error_type='WRITEBACK_FAIL_AFTER_UPLOAD a=1 id=P_1')],
          {'by_id': {'P_1': dict(id='P_1', message='Exact caption 🎶', created_time=iso(start + timedelta(minutes=1)), **{'from': {'id': '123'}})}})
check('R1-11 FB post found by id but from another page -> MISMATCH', s == 'MISMATCH', s)
d, s = r1(dict(base, status='PUBLISHING', lock_until=iso(NOW + timedelta(minutes=10))), [], {'by_id': {}, 200: []})
check('R1-12 PUBLISHING with a live lock (P2 may still be working) -> not touched', s == 'NOT_SELECTED', s)
d, s = r1(dict(base, attempt_started_at=''), log, {'by_id': {'17890001': ig('17890001', start + timedelta(minutes=2))}})
check('R1-13 record claimed before f2 (no attempt_started_at): window from lock_until - 45 min still proves the stored id', s == 'PROVEN', s)
writes = {k for m in BY.values() if m['module'] == 'datastore:UpdateRecord' for k in m['mapper']['data']}
platform_mods = sorted({m['module'] for m in BY.values() if m['module'].split(':')[0] in ('instagram-business', 'facebook-pages', 'youtube')})
check('R1-14 platform modules are read-only lookups', platform_mods == ['facebook-pages:GetPost', 'facebook-pages:GetVideo', 'facebook-pages:ListPosts',
      'facebook-pages:ListVideos', 'instagram-business:GetMedia', 'instagram-business:GetUserMedia', 'youtube:ActionGetVideo', 'youtube:ActionSearchVideo'], platform_mods)
pub = [m['id'] for m in BY.values() if m['module'] == 'datastore:UpdateRecord' and m['mapper']['data'].get('status') == 'PUBLISHED']
check('R1-15 status=PUBLISHED is written ONLY in the stored-id proof branch', sorted(pub) == [102, 112, 122, 132], pub)
ok = all(t['passed'] for t in T)
json.dump(dict(test='R1 v2 reconcile (local model over stored filter JSON)', level='LOCAL MODEL; R1 not executed in Make (inactive)',
               internal_writes=sorted(writes), results=T, passed=sum(t['passed'] for t in T), total=len(T)), open('TEST_RESULTS_R1_RECONCILE.json', 'w'), indent=1)
print('SUMMARY', sum(t['passed'] for t in T), '/', len(T))
