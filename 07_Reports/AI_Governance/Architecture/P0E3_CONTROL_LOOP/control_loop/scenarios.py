"""Deterministic, reusable P0-E3 scenarios shared by the acceptance gate and the offline tests.

Every scenario is a pure function of a throwaway workdir + explicit clock. No wall clock, no randomness,
no network, no production side effects. Each returns structured facts the caller verifies independently.
"""
import os, json, shutil, tempfile
from .control_loop import DurableControlLoop, Clock, CrashInjected
from . import state_model
from .persistence import CentralPersistence, LocalDirBackend, CONFLICT, OK

SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed", "backlog_slice1.json")


def _fresh_workdir():
    d = tempfile.mkdtemp(prefix="p0e3_")
    shutil.copy(SEED, os.path.join(d, "BACKLOG.json"))
    return d


def _invocations(loop):
    if os.path.exists(loop.invocation_log):
        return json.load(open(loop.invocation_log))
    return []


def happy_path(workdir=None):
    """Full autonomous run: A->B chain, C parks (human-gated), D continues independently."""
    d = workdir or _fresh_workdir()
    loop = DurableControlLoop(d, clock=Clock(1000))
    result = loop.run(max_iterations=50)
    status = {t["task_id"]: t["status"] for t in loop.backlog.tasks}
    return {"workdir": d, "loop": loop, "result": result, "status": status,
            "invocations": _invocations(loop),
            "persisted": loop.persisted_state(),
            "master": loop.master_state()}


def concurrent_double_claim(workdir=None):
    """Two workers race for the same READY task WHILE the lease is live; the loser must not execute.

    worker-1 takes a live lease on TASK_A (mid-flight). worker-2 then attempts to process the same task at
    the same tick: its claim must be refused (NOT_CLAIMED) and it must not apply any side effect.
    """
    d = workdir or _fresh_workdir()
    loop = DurableControlLoop(d, clock=Clock(1000))
    loop.reconcile_backlog_from_ledger()
    task = loop.backlog.by_id("TASK_A")
    # worker-1 holds a LIVE lease (simulating in-flight execution)
    held = loop.leases.acquire("TASK_A", "worker-1", "L-held", now=1000, ttl=loop.ttl)
    # worker-2 tries to grab the SAME task while the lease is live
    o2 = loop.process_one(task, worker_id="worker-2")
    inv = _invocations(loop)
    a_invocations = [i for i in inv if i["task_id"] == "TASK_A"]
    double_claims = 0 if o2 == "NOT_CLAIMED" else 1
    return {"workdir": d, "loop": loop,
            "worker1_holds_live_lease": held is not None,
            "outcome_worker2": o2,
            "concurrent_double_claim_count": double_claims,
            "task_a_side_effect_count": len(a_invocations)}


def stale_lease_reclaim(workdir=None):
    """A live lease cannot be reclaimed; after TTL expiry a DIFFERENT holder can reclaim safely."""
    d = workdir or _fresh_workdir()
    clock = Clock(1000)
    loop = DurableControlLoop(d, clock=clock, ttl=30)
    loop.reconcile_backlog_from_ledger()
    lt = loop.leases
    live = lt.acquire("TASK_A", "worker-1", "L1", now=1000, ttl=30)
    reclaim_while_live = lt.reclaim("TASK_A", "worker-2", "L2", now=1010, ttl=30)   # must be None
    reclaim_after_expiry = lt.reclaim("TASK_A", "worker-2", "L3", now=1040, ttl=30)  # must succeed, new holder
    return {"workdir": d,
            "live_acquired": live is not None,
            "reclaim_while_live_blocked": reclaim_while_live is None,
            "reclaim_after_expiry_ok": reclaim_after_expiry is not None,
            "reclaim_holder": getattr(reclaim_after_expiry, "holder", None),
            "reclaim_different_holder": getattr(reclaim_after_expiry, "holder", None) == "worker-2"}


def stale_write_rejected(workdir=None):
    """Optimistic concurrency: a writer with a stale expectation is rejected (no silent last-write-wins)."""
    d = workdir or _fresh_workdir()
    hp = happy_path(d)                 # produces a committed HEAD
    loop = hp["loop"]
    cp = loop.persistence
    head = cp.read_head()
    current = cp.read_current()
    # forge a candidate as if a stale worker tried to advance from an OLD version it once read
    stale_candidate = dict(current)
    stale_candidate["state_version"] = head["state_version"] + 1
    stale_candidate["ledger_head_hash"] = "STALE_" + head["ledger_head_hash"]
    stale_candidate["state_hash"] = "STALE_HASH"
    before = cp.head_bytes()
    res = cp.write(stale_candidate,
                   expected_state_version=head["state_version"] - 1,        # stale expectation
                   expected_ledger_head_hash="OLD_HEAD_HASH")
    after = cp.head_bytes()
    return {"workdir": d, "result": res, "rejected": res["status"] == CONFLICT,
            "head_unchanged": before == after}


def crash_and_recover(boundary, workdir=None):
    """Crash the loop at a named boundary, then restart a fresh loop over the SAME durable state.

    Returns facts proving: deterministic reconcile, no duplicate side effect, no lost completed work,
    no fabricated approval, and that independent work continues.
    """
    d = workdir or _fresh_workdir()

    def hook(b, ctx):
        if b == boundary:
            raise CrashInjected(b)

    crashed = False
    try:
        loop1 = DurableControlLoop(d, clock=Clock(1000), crash_hook=hook)
        loop1.run(max_iterations=50)
    except CrashInjected:
        crashed = True

    # RESTART: brand-new loop instance, same durable files (ledger, se_store, central, backlog)
    loop2 = DurableControlLoop(d, clock=Clock(2000))   # clock advanced so lapsed leases are reclaimable
    result = loop2.run(max_iterations=50)

    inv = _invocations(loop2)
    from collections import Counter
    per_job = Counter(i["job_id"] for i in inv)
    duplicate_side_effects = sum(c - 1 for c in per_job.values())
    status = {t["task_id"]: t["status"] for t in loop2.backlog.tasks}
    persisted = loop2.persisted_state()
    ok_replay, replay_detail = state_model.verify_replay(loop2.ledger, persisted) if persisted else (False, "NO_PERSISTED")
    return {"workdir": d, "boundary": boundary, "crashed": crashed,
            "status": status, "invocations": inv,
            "duplicate_side_effects": duplicate_side_effects,
            "a_done": status.get("TASK_A") == "COMPLETED",
            "b_done": status.get("TASK_B") == "COMPLETED",
            "d_done": status.get("TASK_D") == "COMPLETED",
            "c_waiting": status.get("TASK_C") == "WAITING_FOR_NITIN",
            "no_fabricated_approval": "NITIN_PUBLISH_APPROVAL" not in (persisted or {}).get("approvals", {}),
            "replay_matches": ok_replay, "replay_detail": replay_detail}


# Map the six required crash-recovery boundaries onto concrete loop hook boundaries.
BOUNDARY_MAP = {
    "A_after_ledger_before_state":        "after_result_append",            # ledger has TASK_RESULT, no persist
    "B_after_state_before_readback":      "state_written_before_readback",  # file written, HEAD not committed
    "C_after_claim_before_exec":          "after_claim",                    # claimed + leased, no execution
    "D_during_execution":                 "after_started",                  # STARTED, execution in flight
    "E_after_effect_before_completion":   "after_side_effect",              # effect applied, no completion event
    "F_while_waiting_for_nitin":          "after_park",                     # a task parked WAITING_FOR_NITIN
}
