"""P0-E2 Slice-1 autonomous runner (NON-PRODUCTION). Reuses P0-E1 primitives (events, ledger, reducer,
backlog, leases, idempotency, human_auth) — no duplication. Drives:
  BACKLOG -> ready(deps satisfied) -> claim+lease -> idempotency -> execute -> verify -> evidence
  -> append-only EVENT_LEDGER -> deterministic STATE_REDUCER -> MASTER STATE -> COMPLETED -> next READY
Human-gated tasks park at WAITING_FOR_NITIN (emit HUMAN_GATE_REQUEST; never self-approve); a waiting task
never blocks independent READY tasks. Deterministic: explicit clock, no wall time, no hidden state.
No production, no publishing, no external mutation."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))
from control_plane import events as E
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
from control_plane.backlog import ready_tasks, summary, TERMINAL
from control_plane.leases import LeaseTable
from control_plane.idempotency import job_id, SideEffectStore

class Runner:
    def __init__(self, backlog_path, ledger_path, se_store_path, evidence_dir, keyring=None, ttl=100):
        self.backlog_path=backlog_path; self.evidence_dir=evidence_dir; os.makedirs(evidence_dir, exist_ok=True)
        self.ledger=EventLedger(ledger_path); self.leases=LeaseTable(); self.se=SideEffectStore()
        self.se_store_path=se_store_path; self.keyring=keyring or {"keys":{},"revoked":[]}
        self.ttl=ttl; self._clock=0
        self.tasks={t["task_id"]:t for t in json.load(open(backlog_path))["tasks"]}
    def _t(self): self._clock+=1; return "2026-02-01T00:00:%02dZ"%(self._clock%60)
    def _emit(self, **kw):
        kw.setdefault("timestamp", self._t()); kw.setdefault("agent","claude")
        e=E.make_event(event_id="r%04d"%self._clock, **kw); self.ledger.append(e); return e
    def state(self): return reduce(self.ledger.read_all(), keyring=self.keyring)
    def _tasklist(self): return list(self.tasks.values())
    def _approved(self, task):
        gate=task.get("human_gate_required")
        return bool(gate) and gate in self.state().get("approvals",{})
    def execute_task(self, task, worker="claude", simulate_crash_before_result=False):
        tid=task["task_id"]
        ih=E.input_hash({"task_id":tid,"scope":task.get("allowed_scope")})
        lease=self.leases.acquire(tid, worker, "lease-%s"%tid, now=self._clock, ttl=self.ttl)
        if lease is None: return "LEASE_DENIED"
        # PIN job identity at claim so a crash/resume reuses the SAME idempotency key (exactly-once across resume)
        if not task.get("_job_id"):
            task["_job_id"]=job_id(tid, self.state()["state_version"], ih)
        key=task["_job_id"]
        self._emit(event_type="LEASE_ACQUIRED", task_id=tid, lease_id=lease.lease_id)
        self._emit(event_type="TASK_STARTED", task_id=tid); task["status"]="RUNNING"
        result,dup=self.se.once(key, lambda: {"task_id":tid,"ok":True})  # exactly-once side effect
        if simulate_crash_before_result:
            return "CRASHED_BEFORE_RESULT"                   # lease left held; result not recorded
        task["status"]="VERIFYING"
        ev=os.path.join(self.evidence_dir, "exec_%s.json"%tid)
        json.dump({"task_id":tid,"status":"COMPLETED","idempotency_key":key,"duplicate":dup}, open(ev,"w"))
        self._emit(event_type="TASK_RESULT", task_id=tid, idempotency_key=key, evidence=[os.path.basename(ev)])
        self.leases.get(tid).release(); self._emit(event_type="LEASE_RELEASED", task_id=tid)
        task["status"]="COMPLETED"; return "COMPLETED"
    def run_once(self):
        progressed=False
        for task in ready_tasks(self._tasklist()):
            tid=task["task_id"]
            if task.get("human_gate_required") and not self._approved(task):
                if task["status"]!="WAITING_FOR_NITIN":
                    self._emit(event_type="HUMAN_GATE_REQUEST", task_id=tid, gate=task["human_gate_required"],
                               inputs={"content_fingerprint": task.get("content_fingerprint")})
                    task["status"]="WAITING_FOR_NITIN"; progressed=True     # parked; does not block others
                continue
            if self.execute_task(task)=="COMPLETED": progressed=True
        return progressed
    def run_to_quiescence(self, max_passes=50):
        passes=0
        while passes<max_passes and self.run_once(): passes+=1
        self._persist(); return self.state()
    def _persist(self):
        json.dump({"tasks":self._tasklist()}, open(self.backlog_path,"w"), indent=2)
        open(self.se_store_path,"w").write(json.dumps(getattr(self.se,"_done",{})))
    def next_ready(self):
        r=ready_tasks(self._tasklist()); return r[0]["task_id"] if r else None
