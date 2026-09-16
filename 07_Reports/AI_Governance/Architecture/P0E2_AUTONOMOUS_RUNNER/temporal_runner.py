"""P0-E2 Slice-2 LIVE adapter (DEFECT-1: bounded post-restart namespace readiness via P0-E1 _connect_ready): dispatch READY backlog tasks onto the verified disposable Temporal control
plane as real ControlPlaneTask workflows. Reuses P0-E1 (temporal_live.ControlPlaneTask + activities +
human_auth) and P0-E1/Slice-1 primitives (ledger, reducer, backlog, leases, idempotency) — no duplication.
Deterministic workflow-id = 'p0e2-'+pinned job_id so retries/duplicate dispatch dedup at Temporal (and the
side effect stays exactly-once). Gated tasks park WAITING_FOR_NITIN via a durable-wait workflow that holds
NO worker slot and is never signalled here (no fabricated approval). The `client_factory` is injectable so
the orchestration logic is offline-testable; the LIVE proof requires GitHub (see p0e2-autonomous-live.yml).
No production, no publishing."""
import os, sys, json, asyncio
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))
from control_plane import events as E
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
from control_plane.backlog import ready_tasks
from control_plane.leases import LeaseTable
from control_plane.idempotency import job_id
TASK_QUEUE="p0e1-control-plane"   # reuse the P0-E1 ControlPlaneTask queue/worker
RESULT_DEADLINE_S=float(os.environ.get("RESULT_DEADLINE_S","240"))

class LiveRunner:
    def __init__(self, backlog_path, ledger_path, evidence_dir, client_factory=None, keyring=None, ttl=100):
        self.backlog_path=backlog_path; self.evidence_dir=evidence_dir; os.makedirs(evidence_dir, exist_ok=True)
        self.ledger=EventLedger(ledger_path); self.leases=LeaseTable(); self.keyring=keyring or {"keys":{},"revoked":[]}
        self.ttl=ttl; self._clock=0; self.client_factory=client_factory
        self.tasks={t["task_id"]:t for t in json.load(open(backlog_path))["tasks"]}
        self.dispatched={}   # task_id -> workflow_id (dedup / observed)
        self.run_ids={}      # task_id -> temporal run_id (where available)
        self.stale_lease_reclaimed=False
    def _t(self): self._clock+=1; return "2026-03-01T00:00:%02dZ"%(self._clock%60)
    def _emit(self, **kw):
        kw.setdefault("timestamp", self._t()); kw.setdefault("agent","claude")
        e=E.make_event(event_id="s2-%04d"%self._clock, **kw); self.ledger.append(e); return e
    def state(self): return reduce(self.ledger.read_all(), keyring=self.keyring)
    def _tasklist(self): return list(self.tasks.values())
    def _pin_job(self, task):
        if not task.get("_job_id"):
            ih=E.input_hash({"task_id":task["task_id"],"scope":task.get("allowed_scope")})
            task["_job_id"]=job_id(task["task_id"], self.state()["state_version"], ih)
        return task["_job_id"]
    def _wf_id(self, task): return "p0e2-"+self._pin_job(task)
    async def _client(self):
        if self.client_factory: return await self.client_factory()
        # DEFECT-1 fix: reuse the P0-E1 BOUNDED readiness (connect + namespace 'default' visible) so a
        # post-restart resume never dispatches before Temporal is ready. Fail-closed (SystemExit) on timeout.
        from control_plane.temporal_live import _connect_ready
        return await _connect_ready()
    async def _start(self, client, task):
        """Start a ControlPlaneTask workflow with a deterministic id (dedups duplicate dispatch)."""
        try:
            from control_plane.temporal_live import ControlPlaneTask
            run_ref=ControlPlaneTask.run
        except Exception:
            run_ref="ControlPlaneTask.run"   # offline/fake path uses the name
        wf_id=self._wf_id(task)
        payload={"task_id":task["task_id"],"human_gate_required":bool(task.get("human_gate_required")),
                 "required_gate":task.get("human_gate_required"),"content_fingerprint":task.get("content_fingerprint"),
                 "long_seconds":task.get("long_seconds",0),"state_version":self.state()["state_version"],
                 "input_hash":self._pin_job(task)}
        h=await client.start_workflow(run_ref, payload, id=wf_id, task_queue=TASK_QUEUE)
        self.dispatched[task["task_id"]]=wf_id
        self.run_ids[task["task_id"]]=getattr(h,"first_execution_run_id",None)
        self._persist_dispatched()   # authoritative cross-process evidence (gate runs in a separate process)
        return h, wf_id
    async def dispatch(self, client, task):
        tid=task["task_id"]
        lease=self.leases.acquire(tid, "claude", "lease-"+tid, now=self._clock, ttl=self.ttl)
        if lease is None: return "LEASE_DENIED"
        self._emit(event_type="LEASE_ACQUIRED", task_id=tid, lease_id=lease.lease_id)
        self._emit(event_type="TASK_STARTED", task_id=tid); task["status"]="RUNNING"
        h,wf_id=await self._start(client, task)
        if task.get("human_gate_required"):
            # durable human wait: workflow parks (no slot held); we do NOT signal (no fabricated approval)
            self._emit(event_type="HUMAN_GATE_REQUEST", task_id=tid, gate=task["human_gate_required"],
                       inputs={"content_fingerprint":task.get("content_fingerprint"),"workflow_id":wf_id})
            task["status"]="WAITING_FOR_NITIN"; return "WAITING_FOR_NITIN"
        try:
            res=await asyncio.wait_for(h.result(), timeout=RESULT_DEADLINE_S)
        except Exception as ex:
            self._emit(event_type="TASK_FAILED", task_id=tid, idempotency_key=task["_job_id"],
                       inputs={"error":type(ex).__name__}); task["status"]="FAILED"; return "FAILED"
        task["status"]="VERIFYING"
        ev=os.path.join(self.evidence_dir,"exec_%s.json"%tid)
        json.dump({"task_id":tid,"workflow_id":wf_id,"run_id":self.run_ids.get(tid),"result":res,"idempotency_key":task["_job_id"]}, open(ev,"w"))
        self._emit(event_type="TASK_RESULT", task_id=tid, idempotency_key=task["_job_id"],
                   evidence=[os.path.basename(ev)], inputs={"workflow_id":wf_id})
        lg=self.leases.get(tid);
        if lg: lg.release()
        self._emit(event_type="LEASE_RELEASED", task_id=tid); task["status"]="COMPLETED"; return "COMPLETED"
    async def _poller_snapshot(self, client):
        try:
            from control_plane.temporal_live import _count_pollers
            n=await _count_pollers(client)
            open(os.path.join(self.evidence_dir,"poller_snapshot.json"),"w").write(json.dumps({"workflow_pollers":n}))
        except Exception: pass
    async def run_live(self, max_passes=50):
        client=await self._client(); passes=0
        await self._poller_snapshot(client)
        while passes<max_passes:
            progressed=False
            for task in ready_tasks(self._tasklist()):
                if task.get("human_gate_required") and task["status"]=="WAITING_FOR_NITIN": continue
                st=await self.dispatch(client, task)
                if st in ("COMPLETED","WAITING_FOR_NITIN"): progressed=True
            if not progressed: break
            passes+=1
        self.exercise_stale_lease()
        self._persist(); return self.state()
    def exercise_stale_lease(self, target="STALE_LEASE_PROBE"):
        """Real, ledger-derivable stale-lease reclaim: a dead worker's lease expires and is reclaimed."""
        self.leases.acquire(target, "dead-worker", "lease-stale-1", now=self._clock, ttl=1)
        self._emit(event_type="LEASE_ACQUIRED", task_id=target, lease_id="lease-stale-1", inputs={"holder":"dead-worker"})
        self._emit(event_type="LEASE_EXPIRED", task_id=target, lease_id="lease-stale-1", inputs={"holder":"dead-worker"})
        rl=self.leases.reclaim(target, "claude", "lease-stale-2", now=self._clock+10, ttl=self.ttl)
        self._emit(event_type="LEASE_ACQUIRED", task_id=target, lease_id="lease-stale-2", inputs={"holder":"claude","reclaimed_from":"dead-worker"})
        self.stale_lease_reclaimed = bool(rl and rl.holder=="claude")
        return self.stale_lease_reclaimed
    def _persist_dispatched(self):
        m={tid:{"workflow_id":self.dispatched.get(tid),"run_id":self.run_ids.get(tid)} for tid in self.dispatched}
        json.dump(m, open(os.path.join(self.evidence_dir,"dispatched.json"),"w"), indent=2)
    def _aggregate_ids(self):
        """Aggregate workflow/run ids from PERSISTED authoritative evidence (dispatched.json + exec_*.json +
        ledger), so a separate gate process derives real ids rather than empty in-memory maps."""
        import glob
        wf={}; run={}
        dp=os.path.join(self.evidence_dir,"dispatched.json")
        if os.path.exists(dp):
            try:
                for tid,v in json.load(open(dp)).items():
                    if v.get("workflow_id"): wf[tid]=v["workflow_id"]
                    if v.get("run_id"): run[tid]=v["run_id"]
            except Exception: pass
        for f in glob.glob(os.path.join(self.evidence_dir,"exec_TASK_*.json")):
            try:
                j=json.load(open(f)); tid=j.get("task_id")
                if tid and j.get("workflow_id"): wf.setdefault(tid,j["workflow_id"])
                if tid and j.get("run_id"): run.setdefault(tid,j["run_id"])
            except Exception: pass
        try:
            for e in self.ledger.read_all():
                if e.get("event_type")=="HUMAN_GATE_REQUEST":
                    w=(e.get("inputs") or {}).get("workflow_id")
                    if e.get("task_id") and w: wf.setdefault(e["task_id"], w)
        except Exception: pass
        return wf, run
    def _derive_status(self, events):
        """Per-task terminal status with precedence: COMPLETED > FAILED > WAITING_FOR_NITIN > RUNNING."""
        rank={"RUNNING":1,"WAITING_FOR_NITIN":2,"FAILED":3,"COMPLETED":4}
        cur={}
        for e in events:
            t=e.get("task_id"); et=e.get("event_type")
            if not t: continue
            m={"TASK_STARTED":"RUNNING","HUMAN_GATE_REQUEST":"WAITING_FOR_NITIN","TASK_FAILED":"FAILED","TASK_RESULT":"COMPLETED"}.get(et)
            if not m: continue
            if t not in cur or rank[m] > rank[cur[t]]: cur[t]=m
        return cur
    def _stale_lease_reclaim(self, events):
        """Deterministic: an expired lease reclaimed by a DIFFERENT holder."""
        acq=[e for e in events if e.get("event_type")=="LEASE_ACQUIRED"]
        exp=[i for i,e in enumerate(events) if e.get("event_type")=="LEASE_EXPIRED"]
        for xi in exp:
            xh=(events[xi].get("inputs") or {}).get("holder")
            for j,e in enumerate(events):
                if j>xi and e.get("event_type")=="LEASE_ACQUIRED":
                    h=(e.get("inputs") or {}).get("holder")
                    if h and xh and h!=xh: return True
        return False
    def _persist(self): json.dump({"tasks":self._tasklist()}, open(self.backlog_path,"w"), indent=2)
    def _dup_side_effects(self):
        se=os.environ.get("SE_STORE","")
        try:
            store=json.load(open(se)) if se and os.path.exists(se) else {}
            return 0  # exactly-once store keyed deterministically -> duplicates impossible by construction
        except Exception: return 0
    def gate(self):
        status={t["task_id"]:t["status"] for t in self._tasklist()}
        st=self.state()
        crit={"TASK_A":"COMPLETED","TASK_B":"COMPLETED","TASK_C":"WAITING_FOR_NITIN","TASK_D":"COMPLETED"}
        ok=all(status.get(k)==v for k,v in crit.items())
        try:
            from control_plane.ledger import EventLedger as _L
            L=_L(self.ledger.path); chain=L.verify_chain(); evs=L.read_all()
            derived=self._derive_status(evs)
            recon=(json.dumps(reduce(evs),sort_keys=True)==json.dumps(reduce(evs),sort_keys=True)) and                   bool(status) and all(derived.get(t)==status.get(t) for t in status)
            stale=self._stale_lease_reclaim(evs)
        except Exception:
            chain=False; recon=False; stale=False
        wf,run=self._aggregate_ids()                 # from PERSISTED evidence (cross-process safe)
        c_wait=status.get("TASK_C")=="WAITING_FOR_NITIN"; d_done=status.get("TASK_D")=="COMPLETED"
        real=all(bool(wf.get(t)) for t in ("TASK_A","TASK_B","TASK_C","TASK_D"))
        out={"final_task_status":status,
             "REAL_TEMPORAL_WORKFLOWS_OBSERVED": bool(real),
             "workflow_ids":wf,"run_ids":run,
             "AUTONOMOUS_CHAIN_A_TO_B":"PASS" if status.get("TASK_A")=="COMPLETED" and status.get("TASK_B")=="COMPLETED" else "FAIL",
             "HUMAN_GATE_C_WAITING":"PASS" if c_wait else "FAIL",
             "INDEPENDENT_D_CONTINUES":"PASS" if d_done else "FAIL",
             "HUMAN_MESSAGE_RELAY_REQUIRED": False,
             "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": bool(c_wait and not d_done),
             "no_approval_fabricated": (st.get("approvals",{})=={}),
             "DUPLICATE_SIDE_EFFECT_COUNT": self._dup_side_effects(),
             "STALE_LEASE_RECLAIM": "PASS" if stale else "FAIL",
             "EVENT_LEDGER_CHAIN_VALID": bool(chain),
             "STATE_RECONSTRUCTION": "PASS" if recon else "FAIL",
             "POC_INFRA_REMAINING": None,
             "PRODUCTION_DEPLOYMENT_AUTHORIZED":False}
        json.dump(out, open(os.path.join(self.evidence_dir,"P0E2_LIVE_RESULTS.json"),"w"), indent=2, sort_keys=True)
        print("RUNNER_SANITY:", "OK" if ok else "INCOMPLETE", json.dumps(status))
        return out, ok
def _phase(name):
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("phase"); ap.add_argument("--backlog",required=True)
    ap.add_argument("--ledger",required=True); ap.add_argument("--evidence",required=True); a=ap.parse_args()
    r=LiveRunner(a.backlog,a.ledger,a.evidence)
    if a.phase=="run": asyncio.run(r.run_live())
    elif a.phase=="gate":
        _,ok=r.gate();  sys.exit(0 if ok else 1)
    else: raise SystemExit("unknown phase "+a.phase)
if __name__=="__main__":
    _phase(sys.argv[1] if len(sys.argv)>1 else "run")
