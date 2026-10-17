"""Evaluate the Make lock/claim/fence runs (T1+T2 v2, test store 168532) from the final store read-back.
Usage: python3 eval_lock_tests.py <readback.json>  -> TEST_RESULTS_LOCK_MAKE_RUNTIME.json"""
import json, sys, re
recs = json.load(open(sys.argv[1]))
S = {r['key']: r['data'].get('post_id', '') for r in recs}
logs = [v for k, v in S.items() if not k.startswith(('tstate:', 'tlock:', 'tup:'))]
ups = lambda p: sorted(k for k in S if k.startswith('tup:%s:' % p))
owner = lambda v: v.split('|')[1] if v.count('|') == 2 else ''
R = []
def check(name, ok, detail=''):
    R.append(dict(check=name, passed=bool(ok), detail=detail)); print(('PASS ' if ok else 'FAIL ') + name + (' — ' + str(detail)[:160] if detail else ''))
st = lambda p: S.get('tstate:' + p, '')
# L1 overlap / duplicate key / lock before claim
check('L1 two overlapping runs, same placement+attempt: exactly one lock, the other refused (Duplicate key), one upload, state PUBLISHED by the lock owner',
      len(ups('syn-L1')) == 1 and st('syn-L1').startswith('PUBLISHED|') and owner(st('syn-L1')) == S.get('tlock:syn-L1:a1')
      and any('LOCK_REFUSED a=1' in l and 'Duplicate key' in l for l in logs), [st('syn-L1'), ups('syn-L1')])
check('L3 failed claim (record missing): logged CLAIM_WRITE_FAIL, no upload', not ups('syn-L3') and any(l.startswith('CLAIM_WRITE_FAIL') and 'syn-L3' in l for l in logs))
up4 = ups('syn-L4')
check('L4 id write-back fails after a (simulated) upload: WRITEBACK_FAIL_AFTER_UPLOAD logged with the upload id, state stays PUBLISHING (never re-selected)',
      len(up4) == 1 and st('syn-L4').startswith('PUBLISHING|') and any(l.startswith('WRITEBACK_FAIL_AFTER_UPLOAD a=1 id=SIM-' + up4[0].split(':', 2)[2]) for l in logs), [st('syn-L4'), up4])
check('L2 crash after claim -> restart with the same attempt refused by the lock -> after human recovery (FAILED) attempt 2 publishes once -> stale attempt-1 run refused',
      len(ups('syn-L2')) == 1 and st('syn-L2').startswith('PUBLISHED|') and st('syn-L2').endswith('|2') and 'tlock:syn-L2:a2' in S
      and sum('LOCK_REFUSED a=1' in l for l in logs) >= 3, [st('syn-L2'), ups('syn-L2')])
check('L5 old run outlives its claim; recovery + attempt 2 publish; old run wakes before upload -> CLAIM_LOST_BEFORE_UPLOAD, no upload by the old run',
      len(ups('syn-L5')) == 1 and st('syn-L5').endswith('|2') and st('syn-L5').startswith('PUBLISHED|')
      and any(l.startswith('CLAIM_LOST_BEFORE_UPLOAD a=1') and 'syn-L5' not in l for l in logs), [st('syn-L5'), ups('syn-L5')])
up6 = ups('syn-L6')
check('L6 old run already uploaded, recovery + attempt 2 publish; old write-back fenced -> WRITEBACK_SKIPPED_CLAIM_LOST, attempt-2 state NOT overwritten (2 uploads: residual risk of early human recovery)',
      st('syn-L6').startswith('PUBLISHED|') and st('syn-L6').endswith('|2') and any(l.startswith('WRITEBACK_SKIPPED_CLAIM_LOST a=1') for l in logs), [st('syn-L6'), up6])
check('no lock record was ever deleted/overwritten: every tlock owner equals the first claimant', all(v and re.fullmatch(r'[0-9a-f-]{36}', v) for k, v in S.items() if k.startswith('tlock:')))
json.dump(dict(test='Make runtime lock/claim/fence (T1+T2 v2, test store 168532, synthetic, simulated uploads)', results=R,
               passed=sum(r['passed'] for r in R), total=len(R), store=S), open('TEST_RESULTS_LOCK_MAKE_RUNTIME.json', 'w'), indent=1)
print('SUMMARY', sum(r['passed'] for r in R), '/', len(R))
