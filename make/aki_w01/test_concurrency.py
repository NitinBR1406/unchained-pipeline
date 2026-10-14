"""Forced-overlap proof for P2 (publish) and M1 (measure) claims.

The only Make semantics assumed are the ones proven live on data store 196442 (2026-10-14):
  * 'Add a record' with overwrite=No on an existing key fails with "Duplicate key error" (7 attempts on 2 keys: exactly
    one insert per key succeeded, the rest were rejected);
  * a module error with an Ignore (Skip) handler ends that bundle — later modules of that bundle do not run.
Every interleaving of two concurrent executions is enumerated exhaustively (not sampled). Writes TEST_RESULTS_CONCURRENCY.json."""
import itertools, json

class Store:
    def __init__(self, rec): self.rec = dict(rec); self.locks = set(); self.posts = 0; self.rows = []
    def insert(self, key):          # proven: unique keys, second insert fails
        if key in self.locks: return False
        self.locks.add(key); return True

def p2_steps(st, name, crash_after=None):
    """P2 for one placement: search -> claim update -> insert lock -> gate -> upload -> write back."""
    ctx = {}
    def search():
        r = st.rec
        ctx['sel'] = r['status'] in ('READY', 'FAILED') and not r['platform_post_id'] and r['attempt_count'] < 3
        ctx['att'] = r['attempt_count']
    def lock():     # P2 version e: insert-only lock FIRST (module 51)
        if ctx['sel']: ctx['own'] = st.insert('plock:X:a%d' % (ctx['att'] + 1))
    def claim():    # module 50: only the lock winner writes the record
        if ctx['sel'] and ctx.get('own'): st.rec.update(status='PUBLISHING', attempt_count=ctx['att'] + 1)
    def upload():
        if ctx['sel'] and ctx.get('own'): st.posts += 1; ctx['posted'] = True
    def writeback():
        if ctx.get('posted') and crash_after != 'upload': st.rec.update(status='PUBLISHED', platform_post_id='P1')
    return [search, lock, claim, upload, writeback]

def p2_steps_v_d(st, name):
    """previous order (claim update BEFORE the lock) — kept as a contrast"""
    ctx = {}
    def search():
        r = st.rec; ctx['sel'] = r['status'] in ('READY', 'FAILED') and not r['platform_post_id'] and r['attempt_count'] < 3; ctx['att'] = r['attempt_count']
    def claim():
        if ctx['sel']: st.rec.update(status='PUBLISHING', attempt_count=ctx['att'] + 1)
    def lock():
        if ctx['sel']: ctx['own'] = st.insert('plock:X:a%d' % (ctx['att'] + 1))
    def upload():
        if ctx['sel'] and ctx.get('own'): st.posts += 1; ctx['posted'] = True
    def writeback():
        if ctx.get('posted'): st.rec.update(status='PUBLISHED', platform_post_id='P1')
    return [search, claim, lock, upload, writeback]

def interleavings(a, b):
    n, m = len(a), len(b)
    for pos in itertools.combinations(range(n + m), n):
        seq, ia, ib = [], 0, 0
        for i in range(n + m):
            if i in pos: seq.append(a[ia]); ia += 1
            else: seq.append(b[ib]); ib += 1
        yield seq

R = []
def check(name, cond, detail=''):
    R.append(dict(check=name, passed=bool(cond), detail=str(detail))); print(('PASS ' if cond else 'FAIL ') + name + (' — ' + str(detail) if detail else ''))

base = dict(status='READY', platform_post_id='', attempt_count=0)
worst, n = 0, 0
for k in range(len(list(interleavings(range(5), range(5))))):
    pass
for order in itertools.combinations(range(10), 5):
    st = Store(base); A = p2_steps(st, 'A'); B = p2_steps(st, 'B')
    ia = ib = 0
    for i in range(10):
        if i in order: A[ia](); ia += 1
        else: B[ib](); ib += 1
    worst = max(worst, st.posts); n += 1
check('C1 P2: two overlapping runs, all %d interleavings -> never more than one upload' % n, worst <= 1, 'max uploads=%d' % worst)
corrupt_new = corrupt_old = 0
for order in itertools.combinations(range(10), 5):
    for steps, which in ((p2_steps, 'new'), (p2_steps_v_d, 'old')):
        st = Store(base); A = steps(st, 'A'); B = steps(st, 'B'); ia = ib = 0
        for i in range(10):
            if i in order: A[ia](); ia += 1
            else: B[ib](); ib += 1
        bad = st.rec['platform_post_id'] and st.rec['status'] != 'PUBLISHED'
        if which == 'new': corrupt_new += bool(bad)
        else: corrupt_old += bool(bad)
check('C1b P2 lock-before-claim: a stale bundle never rewrites a PUBLISHED record (previous order did in %d of %d interleavings)' % (corrupt_old, n),
      corrupt_new == 0 and corrupt_old > 0, 'new=%d old=%d' % (corrupt_new, corrupt_old))

# naive search-then-write (the old claim) for contrast: show it is NOT exclusive
def naive(st):
    ctx = {}
    def s(): ctx['sel'] = st.rec['status'] == 'READY'
    def c():
        if ctx['sel']: st.rec['status'] = 'PUBLISHING'
    def u():
        if ctx['sel']: st.posts += 1
    return [s, c, u]
bad = 0
for order in itertools.combinations(range(6), 3):
    st = Store(base); A = naive(st); B = naive(st); ia = ib = 0
    for i in range(6):
        if i in order: A[ia](); ia += 1
        else: B[ib](); ib += 1
    bad += st.posts > 1
check('C2 control: the previous search-then-update claim DOES double-post in some interleavings (why the lock was needed)', bad > 0, '%d of 20 interleavings' % bad)

# crash after the platform accepted the upload but before the id was written back
st = Store(base); steps = p2_steps(st, 'A', crash_after='upload')
for f in steps: f()
again = p2_steps(st, 'B')
for f in again: f()
check('C3 crash after upload, before id write-back: placement stays PUBLISHING, a later run does not upload again',
      st.rec['status'] == 'PUBLISHING' and st.posts == 1)

def r1(st, found_on_platform):
    """R1 reconcile: read-only lookup; only exactly one match marks PUBLISHED."""
    if st.rec['status'] in ('PUBLISHING', 'OUTCOME_UNKNOWN'):
        if found_on_platform: st.rec.update(status='PUBLISHED', platform_post_id='P1', reconcile_status='FOUND_ON_PLATFORM')
        else: st.rec['reconcile_status'] = 'NOT_FOUND'
r1(st, True)
check('C4 R1 reconciles the unknown outcome to PUBLISHED with the platform id (no second upload)', st.rec['status'] == 'PUBLISHED' and st.posts == 1)

st = Store(base); steps = p2_steps(st, 'A'); steps[0](); steps[1](); steps[2]()        # crash after lock, before upload
r1(st, False)
blocked = p2_steps(st, 'B'); [f() for f in blocked]
check('C5 expired claim with nothing on the platform: R1 marks NOT_FOUND and P2 does NOT retry on its own', st.posts == 0 and st.rec['reconcile_status'] == 'NOT_FOUND')
st.rec['status'] = 'FAILED'                                                            # human decision after checking
retry = p2_steps(st, 'C'); [f() for f in retry]
check('C6 after a human sets FAILED, the next attempt uses a fresh lock key (a2) and publishes once', st.posts == 1 and 'plock:X:a2' in st.locks)

st = Store(dict(base, status='OUTCOME_UNKNOWN')); [f() for f in p2_steps(st, 'A')]
check('C7 timeout after a possibly successful upload (OUTCOME_UNKNOWN) is never auto-retried', st.posts == 0)

# M1: two overlapping runs on the same window
def m1_steps(st, ledger):
    ctx = {}
    def search():   # module 1 snapshot + module 5 filter (metrics_lock_until must be expired)
        ctx['gen'] = st.rec.get('gen', 0) + 1
        ctx['due'] = st.rec.get('w') != 'DONE' and not st.rec.get('locked')
    def raise_gen():  # module 5: ONE write sets generation AND metrics_lock_until together
        if ctx['due']: st.rec['gen'] = ctx['gen']; st.rec['locked'] = True
    def lock():
        if ctx['due']: ctx['own'] = st.insert('mlock:X:g%d' % ctx['gen'])
    def read_col_a():
        if ctx.get('own'): ctx['seen'] = set(ledger)
    def write():
        if ctx.get('own'):
            for m in ('views', 'reach', 'likes'):
                if 'X:24h:' + m not in ctx['seen']: ledger.append('X:24h:' + m)
            st.rec['w'] = 'DONE'; st.rec['locked'] = False
    return [search, raise_gen, lock, read_col_a, write]
dup = 0; cnt = 0
for order in itertools.combinations(range(10), 5):
    st = Store({}); ledger = []; A = m1_steps(st, ledger); B = m1_steps(st, ledger); ia = ib = 0
    for i in range(10):
        if i in order: A[ia](); ia += 1
        else: B[ib](); ib += 1
    dup += len(ledger) != len(set(ledger)); cnt += 1
check('C8 M1: two overlapping runs, all %d interleavings -> no duplicate measurement rows' % cnt, dup == 0, '%d with duplicates' % dup)

st = Store({}); ledger = []; s = m1_steps(st, ledger); s[0](); s[1](); s[2]()             # crash after taking the lock
st.rec['locked'] = False                                                                   # 45-min lock expired
s2 = m1_steps(st, ledger); [f() for f in s2]                                              # lock expired -> next generation
check('C9 M1: crash after claiming does not block forever; next generation (g2) collects once', len(ledger) == 3 and 'mlock:X:g2' in st.locks)

out = dict(test='forced overlap / crash / reconcile', results=R, passed=sum(r['passed'] for r in R), total=len(R),
           make_semantics_evidence='Live API on data store 196442, 2026-10-14: duplicate insert -> "Duplicate key error. A record with the same key exists or was already inserted in this scenario." (1 success of 2 and 1 of 5 attempts); test records deleted afterwards.',
           not_proven_live='No P2/M1 execution was run (Make API requires an active scenario to run it).')
json.dump(out, open('TEST_RESULTS_CONCURRENCY.json', 'w'), indent=1)
print('SUMMARY', out['passed'], '/', out['total'])
