"""P0-E3 Durable Autonomous Control Loop (Slice-1 core).

One bounded, resumable loop that drives safe engineering work with NO human relay between tasks:

    resolve READY (deps satisfied) -> claim + lease (exactly one) -> [park if human-gated] ->
    ensure TASK_STARTED -> execute exactly-once (deterministic job identity) -> ensure TASK_RESULT +
    evidence -> reduce -> central persist + read-back verify (CAS) -> next READY

Durability / crash-recovery principle: the EVENT LEDGER is the only source of truth. Backlog status,
lease liveness and Master State are all pure PROJECTIONS re-derived from the ledger on start. A crash at any
boundary is recovered by re-deriving and continuing; the durable, deterministic job identity guarantees a
side effect is never applied twice, and completed work (a TASK_RESULT already in the ledger) is never lost or
re-run. WAITING_FOR_NITIN parks durably and never blocks independent READY work.

`now` is always explicit (a deterministic Clock) — no wall clock, no randomness.
"""
import os, json
from control_plane.ledger import EventLedger                 # frozen P0-E1
from control_plane.leases import LeaseTable                   # frozen P0-E1
from control_plane import events as E                         # frozen P0-E1
from control_plane import human_auth                          # frozen P0-E1
from . import state_model
from .durable_stores import BacklogStore, DurableSideEffectStore
from .persistence import CentralPersistence, CONFLICT


class CrashInjected(Exception):
    """Raised by a test crash hook to simulate a process death at a named boundary."""


class Clock:
    """Deterministic monotonic clock. `now()` returns the current tick; `advance` moves it forward."""
    def __init__(self, t=1000):
        self.t = t
    def now(self):
        return self.t
    def advance(self, dt=1):
        self.t += dt
        return self.t


def _default_executor(exec_dir, invocation_log):
    """Default 'Temporal execution' stand-in: a SAFE, deterministic, non-production side effect.

    Records exactly one exec-evidence file per job and appends every real invocation to a log so tests can
    prove exactly-once. Represents dispatch to the frozen P0-E2 ControlPlaneTask; the real Temporal wiring is
    the frozen LiveRunner and is not re-run offline. Never touches production, Make, Render or any publisher.
    """
    os.makedirs(exec_dir, exist_ok=True)

    def run(task, job_id, now):
        # append-only invocation log => detects any double application
        log = []
        if os.path.exists(invocation_log):
            log = json.load(open(invocation_log))
        log.append({"task_id": task["task_id"], "job_id": job_id, "now": now})
        json.dump(log, open(invocation_log, "w"), indent=2)
        ev = {"task_id": task["task_id"], "job_id": job_id, "status": "OK",
              "definition_of_done": task.get("definition_of_done"),
              "evidence": ["exec:%s" % job_id]}
        json.dump(ev, open(os.path.join(exec_dir, "exec_%s.json" % task["task_id"]), "w"), indent=2)
        return ev

    return run


class DurableControlLoop:
    DEFAULT_TTL = 30

    def __init__(self, workdir, keyring=None, clock=None, executor=None, crash_hook=None, ttl=None):
        self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
        self.ledger = EventLedger(os.path.join(workdir, "EVENT_LEDGER.jsonl"))
        self.backlog = BacklogStore(os.path.join(workdir, "BACKLOG.json"))
        self.se = DurableSideEffectStore(os.path.join(workdir, "se_store.json"))
        self.persistence = CentralPersistence.__new__(CentralPersistence)
        from .persistence import LocalDirBackend
        self.persistence.backend = LocalDirBackend(os.path.join(workdir, "central"))
        self.keyring = keyring if keyring is not None else human_auth.load_keyring()
        self.clock = clock or Clock()
        self.crash_hook = crash_hook
        self.ttl = ttl or self.DEFAULT_TTL
        self.exec_dir = os.path.join(workdir, "evidence", "exec")
        self.invocation_log = os.path.join(workdir, "invocations.json")
        self.executor = executor or _default_executor(self.exec_dir, self.invocation_log)
        self.leases = LeaseTable()
        self._seq = 0
        self.human_relay_used = False   # must remain False for the whole run
        self._rebuild_leases()

    # ---- ledger helpers -------------------------------------------------
    def _eid(self, tag):
        self._seq += 1
        return "e-%s-%d-%d" % (tag, self.clock.now(), self._seq)

    def _append(self, event_type, **kw):
        ev = E.make_event(self._eid(event_type), event_type, str(self.clock.now()), "claude", **kw)
        return self.ledger.append(ev)

    def _events(self):
        return self.ledger.read_all()

    def _has_event(self, task_id, event_type):
        return any(r.get("task_id") == task_id and r.get("event_type") == event_type for r in self._events())

    def _has_event_lease_released(self, task_id, lease_id):
        return any(r.get("task_id") == task_id and r.get("event_type") == "LEASE_RELEASED"
                   and r.get("lease_id") == lease_id for r in self._events())

    def _gate_granted(self, task_id, gate):
        st = state_model.derive(self.ledger, keyring=self.keyring)
        a = st.get("approvals", {}).get(gate)
        return bool(a) and a.get("task_id") == task_id

    # ---- projections re-derived from the ledger (crash recovery) --------
    def _rebuild_leases(self):
        """Reconstruct lease holders from LEASE_ACQUIRED/EXPIRED/RELEASED events (ledger is truth)."""
        self.leases = LeaseTable()
        for r in self._events():
            et = r.get("event_type")
            tid = r.get("task_id")
            if et == "LEASE_ACQUIRED":
                inp = r.get("inputs") or {}
                self.leases.acquire(tid, inp.get("holder"), r.get("lease_id"),
                                    inp.get("acquired_at", 0), inp.get("ttl", self.ttl),
                                    allow_parallel=True)
            elif et in ("LEASE_EXPIRED", "LEASE_RELEASED"):
                cur = self.leases.get(tid)
                if cur:
                    cur.release()

    def reconcile_backlog_from_ledger(self):
        """Backlog status is a deterministic projection of the ledger. Never a second source of truth."""
        now = self.clock.now()
        for t in self.backlog.tasks:
            tid = t["task_id"]
            if self._has_event(tid, "TASK_RESULT"):
                t["status"] = "COMPLETED"
            elif self._has_event(tid, "TASK_FAILED"):
                t["status"] = "FAILED"
            elif self._has_event(tid, "HUMAN_GATE_REQUEST") and not self._gate_granted(
                    tid, t.get("human_gate_required")):
                t["status"] = "WAITING_FOR_NITIN"
            elif self._has_event(tid, "TASK_STARTED") or self._has_event(tid, "LEASE_ACQUIRED"):
                cur = self.leases.get(tid)
                if cur and not cur.released and not cur.is_expired(now):
                    t["status"] = "RUNNING" if self._has_event(tid, "TASK_STARTED") else "CLAIMED"
                else:
                    # in-flight work whose lease lapsed -> safe to re-offer (idempotent re-execution)
                    if t["status"] not in ("BLOCKED",):
                        t["status"] = "READY"
            # else: keep seed status (READY / BLOCKED)
        self.backlog.save()

    def _crash(self, boundary, ctx=None):
        if self.crash_hook:
            self.crash_hook(boundary, ctx or {})

    # ---- persistence step (CAS + read-back) -----------------------------
    def _persist_current(self):
        candidate = state_model.derive(self.ledger, keyring=self.keyring)
        head = self.persistence.read_head()
        exp_v = head["state_version"] if head else 0
        exp_h = head["ledger_head_hash"] if head else None
        res = self.persistence.write(candidate, expected_state_version=exp_v, expected_ledger_head_hash=exp_h,
                                     on_boundary=self._crash)
        return res, candidate

    def _catchup_persist(self):
        """If central state lags the ledger head (e.g. a crash between ledger append and persist),
        deterministically re-persist the current derived state so REPLAY(ledger)==persisted holds."""
        candidate = state_model.derive(self.ledger, keyring=self.keyring)
        head = self.persistence.read_head()
        if head is not None and head["ledger_head_hash"] == candidate["ledger_head_hash"]:
            return {"status": "OK", "noop": True}
        if head is not None and candidate["state_version"] <= head["state_version"]:
            return {"status": "OK", "noop": True}
        exp_v = head["state_version"] if head else 0
        exp_h = head["ledger_head_hash"] if head else None
        return self.persistence.write(candidate, expected_state_version=exp_v,
                                      expected_ledger_head_hash=exp_h)

    def _recorded_job_id(self, tid):
        """The immutable job identity recorded in this task's TASK_STARTED event, if any."""
        for r in self._events():
            if r.get("task_id") == tid and r.get("event_type") == "TASK_STARTED":
                return (r.get("inputs") or {}).get("job_id")
        return None

    # ---- per-task processing -------------------------------------------
    def process_one(self, task, worker_id="worker-1"):
        tid = task["task_id"]
        now = self.clock.now()
        lease_id = "L-%s-%d" % (tid, now)

        # already terminal in the ledger -> never re-execute (idempotent, no lost/duplicated work)
        if self._has_event(tid, "TASK_RESULT"):
            return "ALREADY_DONE"
        if self._has_event(tid, "TASK_FAILED"):
            return "ALREADY_FAILED"

        # CLAIM (exactly one valid claim at a time)
        lease = self.leases.acquire(tid, worker_id, lease_id, now, self.ttl)
        if lease is None:
            return "NOT_CLAIMED"
        self._append("LEASE_ACQUIRED", task_id=tid, lease_id=lease_id,
                     inputs={"holder": worker_id, "acquired_at": now, "ttl": self.ttl})
        self.backlog.set_status(tid, "CLAIMED", claimed_by=worker_id, lease_id=lease_id,
                                lease_expires_at=now + self.ttl)
        self._crash("after_claim", {"task_id": tid})

        # HUMAN GATE: park durably, free the slot, do NOT relay, continue with other work
        gate = task.get("human_gate_required")
        if gate and not self._gate_granted(tid, gate):
            fp = human_auth.content_fingerprint({"content_id": tid, "asset_sha256": task.get("input_hash"),
                                                 "platform": None, "packaging_sha256": None,
                                                 "schedule_version": None})
            self._append("HUMAN_GATE_REQUEST", task_id=tid, gate=gate,
                         inputs={"content_fingerprint": fp})
            self.backlog.set_status(tid, "WAITING_FOR_NITIN", blocked_reason="awaiting " + gate)
            self._append("LEASE_RELEASED", task_id=tid, lease_id=lease_id)
            lease.release()
            self._persist_current()
            self._crash("after_park", {"task_id": tid})   # boundary F: crash while a task is parked
            return "WAITING_FOR_NITIN"

        # deterministic job identity from IMMUTABLE inputs: job_id = SHA256(task_id + state_version + input_hash).
        # Computed once at first start and RECORDED in TASK_STARTED so every retry/restart reuses the same
        # logical job identity (state_version is captured at first start; later re-claims cannot change it).
        ih = task.get("input_hash") or E.input_hash({"scope": task.get("allowed_scope"),
                                                      "dod": task.get("definition_of_done")})
        jid = self._recorded_job_id(tid)
        if jid is None:
            sv = state_model.derive(self.ledger, keyring=self.keyring)["state_version"]
            jid = self.se.job_id(tid, sv, ih)
            self._append("TASK_STARTED", task_id=tid,
                         inputs={"input_hash": ih, "state_version": sv, "job_id": jid})
        self.backlog.set_status(tid, "RUNNING", idempotency_key=jid, input_hash=ih)
        self._crash("after_started", {"task_id": tid})

        # EXECUTE exactly once (durable dedup survives restart)
        result, was_dup = self.se.once(jid, lambda: self.executor(task, jid, now))
        self._crash("after_side_effect", {"task_id": tid, "job_id": jid, "was_dup": was_dup})

        # ensure TASK_RESULT exactly once with the idempotency key
        if not self._has_event(tid, "TASK_RESULT"):
            self._append("TASK_RESULT", task_id=tid, idempotency_key=jid,
                         evidence=result.get("evidence", []), inputs={"job_id": jid})
            self._append("EVIDENCE_REGISTERED", task_id=tid,
                         inputs={"task_id": tid, "job_id": jid, "evidence": result.get("evidence", [])})
        self._crash("after_result_append", {"task_id": tid})

        # release the lease in the ledger BEFORE persisting so the persisted state == full ledger head
        if not self._has_event_lease_released(tid, lease_id):
            self._append("LEASE_RELEASED", task_id=tid, lease_id=lease_id)
        lease.release()

        # REDUCE + CENTRAL PERSIST + READ-BACK VERIFY (captures the complete ledger for this task)
        self._crash("before_readback", {"task_id": tid})
        res, _ = self._persist_current()
        if res["status"] == CONFLICT:
            # a concurrent writer advanced central state: do NOT overwrite; reload happens next start
            return "PERSIST_CONFLICT"
        self._crash("after_persist", {"task_id": tid})

        self.backlog.set_status(tid, "COMPLETED")
        return "COMPLETED"

    # ---- the bounded autonomous loop -----------------------------------
    def run(self, max_iterations=100, worker_id="worker-1"):
        """Drive all currently-safe work to quiescence. Bounded: never an uncontrolled infinite loop."""
        self._rebuild_leases()
        self.reconcile_backlog_from_ledger()
        self._catchup_persist()          # heal any lag left by a crash before the previous persist
        processed = []
        for _ in range(max_iterations):
            ready = self.backlog.ready()
            if not ready:
                break
            task = ready[0]                       # highest-priority dependency-ready safe task
            outcome = self.process_one(task, worker_id=worker_id)
            processed.append((task["task_id"], outcome))
            self.clock.advance(1)
            if outcome == "PERSIST_CONFLICT":
                break
        else:
            raise RuntimeError("max_iterations exceeded — refusing to loop unbounded")
        self._catchup_persist()          # ensure persisted == ledger head at quiescence
        # HUMAN_MESSAGE_RELAY_REQUIRED: the loop advanced across safe tasks with no human relay
        return {"processed": processed,
                "backlog_summary": self.backlog.summary(),
                "human_message_relay_required": self.human_relay_used}

    # ---- read-only status ----------------------------------------------
    def master_state(self):
        return state_model.derive(self.ledger, keyring=self.keyring)

    def persisted_state(self):
        return self.persistence.read_current()
