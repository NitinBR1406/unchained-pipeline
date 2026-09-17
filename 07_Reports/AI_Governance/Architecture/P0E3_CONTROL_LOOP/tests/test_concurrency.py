"""P0-E3 concurrency: exactly-one claim, no double side effect, stale-lease reclaim, stale-write rejection."""
from _harness import Counter
from control_loop import scenarios as S
from control_loop.durable_stores import DurableSideEffectStore
from control_plane.leases import LeaseTable
import tempfile, os
c = Counter("CON")

# concurrent double claim: loser is refused, applies no side effect
cc = S.concurrent_double_claim()
c.ok("worker1_holds_live_lease", cc["worker1_holds_live_lease"])
c.ok("worker2_not_claimed", cc["outcome_worker2"] == "NOT_CLAIMED")
c.ok("CONCURRENT_DOUBLE_CLAIM_COUNT_zero", cc["concurrent_double_claim_count"] == 0)
c.ok("no_side_effect_by_loser", cc["task_a_side_effect_count"] == 0)

# stale lease reclaim
sl = S.stale_lease_reclaim()
c.ok("live_lease_acquired", sl["live_acquired"])
c.ok("reclaim_blocked_while_live", sl["reclaim_while_live_blocked"])
c.ok("reclaim_after_expiry", sl["reclaim_after_expiry_ok"])
c.ok("reclaim_by_different_holder", sl["reclaim_different_holder"])

# a single task cannot be held by two live leases simultaneously
lt = LeaseTable()
l1 = lt.acquire("T", "w1", "L1", now=0, ttl=10)
l2 = lt.acquire("T", "w2", "L2", now=1, ttl=10)   # still live -> refused
c.ok("second_live_claim_refused", l1 is not None and l2 is None)

# stale worker cannot overwrite central state after losing its lease (optimistic concurrency)
sw = S.stale_write_rejected()
c.ok("stale_write_conflict", sw["rejected"])
c.ok("stale_write_head_unchanged", sw["head_unchanged"])

# durable side-effect store dedups across a simulated restart (exactly once)
d = tempfile.mkdtemp(); p = os.path.join(d, "se.json")
runs = {"n": 0}
def fn():
    runs["n"] += 1
    return {"ok": True}
se1 = DurableSideEffectStore(p)
r1, dup1 = se1.once("job-1", fn)
se2 = DurableSideEffectStore(p)                # "restart": reload from disk
r2, dup2 = se2.once("job-1", fn)              # same key -> must NOT re-run fn
c.ok("side_effect_ran_once_across_restart", runs["n"] == 1)
c.ok("dedup_flag_on_restart", dup1 is False and dup2 is True)
c.ok("durable_result_preserved", r1 == r2 == {"ok": True})

c.done()
