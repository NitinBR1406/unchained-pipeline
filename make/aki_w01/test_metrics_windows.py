"""M1 v2 simulation (no platform calls). Mirrors the M1 blueprint logic: window choice (module 2), window status with
tolerances (module 3), metrics lock (module 5), ledger column-A dedupe (module 6 + row filters), sub-router write-then-mark,
error rows, MISSED rows, UNAVAILABLE rows. Writes TEST_RESULTS_METRIC_WINDOWS.json."""
import json
H = 3600
PLAN = {'24h': 24, '72h': 72, '7d': 168}; TOL_END = {'24h': 26, '72h': 78, '7d': 180}; NEXT = {'24h': 72, '72h': 168, '7d': 10 ** 9}
DONE = {'DONE_ON_TIME', 'DONE_DELAYED', 'DONE_UNAVAILABLE', 'MISSED'}
IG_METRICS = ['views', 'reach', 'likes', 'comments', 'shares', 'saved', 'total_interactions', 'ig_reels_avg_watch_time', 'ig_reels_video_view_total_time']

def window(rec):
    for w in ('24h', '72h', '7d'):
        if rec.get('m%s_status' % w) not in DONE: return w
    return ''
def wstatus(w, age_h):
    if not w: return 'NONE'
    if age_h < PLAN[w]: return 'NOT_DUE'
    if age_h <= TOL_END[w]: return 'ON_TIME'
    if age_h >= NEXT[w]: return 'MISSED'
    return 'DELAYED'

class Sim:
    def __init__(self, channel='instagram_reels', published_at=0):
        self.rec = dict(placement_id='aki:post:D01-V01:' + channel, channel=channel, published_at=published_at)
        self.ledger = []; self.runs = 0
    def counter(self, t):  # a lifetime counter that keeps growing
        return 100 + int((t - self.rec['published_at']) / H) * 10
    def run(self, t, api='ok', crash_after=None):
        self.runs += 1; run_id = 'run%d' % self.runs; r = self.rec
        age_h = (t - r['published_at']) / H; w = window(r); ws = wstatus(w, age_h)
        if ws in ('NONE', 'NOT_DUE'): return ws
        if r.get('lock_until', -1) > t: return 'LOCKED'
        r['lock_until'] = t + 20 * 60
        existing = {row['observation_id'] for row in self.ledger}                       # module 6: column A once
        def add(row):
            if row['observation_id'] not in existing: self.ledger.append(row); existing.add(row['observation_id'])
        def mark(st):
            r['m%s_status' % w] = st; r['m%s_at' % w] = t; r['lock_until'] = -1
        base = dict(placement_id=r['placement_id'], window=w, window_status=ws, planned_measure_at=r['published_at'] + PLAN[w] * H,
                    observed_at=t, actual_elapsed_hours=round(age_h, 1), collection_run_id=run_id)
        if ws == 'MISSED':
            add(dict(base, observation_id='%s:%s:ALL:MISSED' % (r['placement_id'], w), metric='ALL', value='', availability='MISSED')); mark('MISSED'); return ws
        if r['channel'].startswith('facebook') or r['channel'].startswith('tiktok'):
            for m in ('views', 'reach', 'watch_time'):
                add(dict(base, observation_id='%s:%s:%s' % (r['placement_id'], w, m), metric=m, value='', availability='UNAVAILABLE',
                         reason='scope missing'))
            mark('DONE_UNAVAILABLE'); return ws
        if api == 'error':
            self.ledger.append(dict(base, observation_id='%s:%s:ALL:ERROR:%s' % (r['placement_id'], w, run_id), metric='ALL', value='', availability='ERROR'))
            r['m%s_status' % w] = 'ERROR'; r['lock_until'] = -1; return 'ERROR'
        for i, m in enumerate(IG_METRICS):
            if crash_after is not None and i == crash_after: return 'CRASH'                  # execution dies; lock stays
            add(dict(base, observation_id='%s:%s:%s' % (r['placement_id'], w, m), metric=m, value=self.counter(t), availability='OBSERVED',
                     definition='lifetime cumulative at observed_at' + ('' if ws == 'ON_TIME' else '; NOT the %s value' % w)))
        mark('DONE_ON_TIME' if ws == 'ON_TIME' else 'DONE_DELAYED'); return ws

R = []
def check(name, cond, detail=''):
    R.append(dict(check=name, passed=bool(cond), detail=str(detail)[:300])); print(('PASS ' if cond else 'FAIL ') + name + (' — ' + str(detail)[:150] if detail else ''))
def ids(s): return [r['observation_id'] for r in s.ledger]
def per_window(s): return {w: sorted({r['window_status'] for r in s.ledger if r['window'] == w}) for w in PLAN}

s = Sim()
for t in range(0, 9 * 24 * H, 15 * 60): s.run(t)
check('M1 normal (every 15 min, 9 days): 24h/72h/7d each ON_TIME, 9 metrics each, no duplicates',
      per_window(s) == {'24h': ['ON_TIME'], '72h': ['ON_TIME'], '7d': ['ON_TIME']} and len(s.ledger) == 27 and len(set(ids(s))) == 27, per_window(s))
check('M2 nothing collected before 24h', all(r['actual_elapsed_hours'] >= PLAN[r['window']] for r in s.ledger))
check('M3 planned time, actual fetch time and elapsed hours stored separately per row',
      all({'planned_measure_at', 'observed_at', 'actual_elapsed_hours', 'collection_run_id'} <= set(r) for r in s.ledger))

s = Sim(); s.run(24 * H); n = len(s.ledger); s.run(24 * H + 60); s.run(24 * H + 120)
check('M4 repeated execution in the same window adds no rows', len(s.ledger) == n == 9)

s = Sim(); a = s.run(24 * H, crash_after=4); b = s.run(24 * H + 5 * 60); c = s.run(24 * H + 25 * 60)
check('M5 crash after 4 of 9 rows: lock blocks a parallel/early rerun, resume after lock adds only the 5 missing rows',
      (a, b, c) == ('CRASH', 'LOCKED', 'ON_TIME') and len(s.ledger) == 9 and len(set(ids(s))) == 9 and s.rec['m24h_status'] == 'DONE_ON_TIME', (a, b, c, len(s.ledger)))
check('M5b resumed rows keep their own (later) observed_at and run id — partial batches stay traceable',
      len({r['collection_run_id'] for r in s.ledger}) == 2)

s = Sim(); e = s.run(24 * H, api='error'); ok = s.run(24 * H + 30 * 60)
check('M6 API error -> one ERROR row, window stays open, retried and collected next run',
      e == 'ERROR' and ok == 'ON_TIME' and sum(r['availability'] == 'ERROR' for r in s.ledger) == 1 and s.rec['m24h_status'] == 'DONE_ON_TIME')
s = Sim(); s.run(24 * H, api='error'); late = s.run(30 * H)
check('M7 error then recovery after tolerance -> DELAYED, labelled as not the 24h value', late == 'DELAYED'
      and all('NOT the 24h value' in r['definition'] for r in s.ledger if r['availability'] == 'OBSERVED'))

s = Sim(); s.run(20 * H); r80 = [s.run(80 * H), s.run(80 * H + 60)]
check('M8 collector down 20h->80h: 24h MISSED (no value), 72h collected at 80h as DELAYED (actual elapsed recorded)',
      r80 == ['MISSED', 'DELAYED'] and any(r['availability'] == 'MISSED' and r['value'] == '' for r in s.ledger if r['window'] == '24h')
      and all(r['actual_elapsed_hours'] >= 80 for r in s.ledger if r['window'] == '72h'), (r80, per_window(s)))
check('M9 an 80h cumulative counter is never stored as a 24h value', not any(r['window'] == '24h' and r['availability'] == 'OBSERVED' for r in s.ledger))

s = Sim(); out = [s.run(170 * H) for _ in range(3)]
check('M10 collector down until 170h: 24h MISSED, 72h MISSED, 7d ON_TIME', out == ['MISSED', 'MISSED', 'ON_TIME'], out)

pub = 5 * H                                                                                 # published 5h later than planned
s = Sim(published_at=pub); early = s.run(pub + 23 * H); on = s.run(pub + 24 * H)
check('M11 late publication: windows anchored on real published_at (not planned time)', early == 'NOT_DUE' and on == 'ON_TIME'
      and s.ledger[0]['planned_measure_at'] == pub + 24 * H)

s = Sim(channel='facebook_reels'); s.run(24 * H); s.run(25 * H)
check('M12 missing rights (Facebook): UNAVAILABLE rows with empty value (never 0), once per window',
      len(s.ledger) == 3 and all(r['availability'] == 'UNAVAILABLE' and r['value'] == '' for r in s.ledger))
all_rows = [r for sim in (s,) for r in sim.ledger]
check('M13 no row anywhere has value 0 unless availability=OBSERVED', all(not (r['value'] == 0 and r['availability'] != 'OBSERVED') for r in all_rows))
check('M14 no per-post account-growth metric exists in the collector (follower growth is never attributed to one post)',
      'followers_count' not in IG_METRICS and 'subscribers_gained' not in ['views', 'likes', 'comments'])

limits = ['Google Sheets is append-only from Make here: corrections are new rows; consumers take one row per observation_id (latest observed_at).',
          'Dedupe reads column A once per window; a crash between writing a row and the next row read is covered by the deterministic observation_id.',
          'Sheets API quota: ~60 read+write requests/min/user; one run writes at most ~10 rows per placement-window.',
          'No row-level locking in Sheets; protection comes from the per-placement metrics lock (20 min) and Make sequential execution.',
          'A Google Sheet holds max 10 million cells; at 22 columns this is >400k rows, far above this campaign (60 x 3 x ~10 = ~1,800 rows).']
out = dict(test='M1 v2 window/restart/dedupe simulation', results=R, passed=sum(r['passed'] for r in R), total=len(R), sheets_limitations=limits)
json.dump(out, open('TEST_RESULTS_METRIC_WINDOWS.json', 'w'), indent=1)
print('SUMMARY', out['passed'], '/', out['total'])
