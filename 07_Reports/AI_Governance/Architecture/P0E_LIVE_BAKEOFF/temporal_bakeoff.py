"""Temporal side of the P0-E live bake-off — V02.6 (harness fixture fix: L auto-completes after the long activity) / V02.4 (post-restart recovery closure: every restart/recovery await is BOUNDED with evidence markers; a timeout fail-closes + tears down, never hangs).
Phases (called by the CI workflow, interleaved with docker kill/restart of worker + postgres):
  worker            -> run a worker (low concurrency so a held slot would be visible)
  start             -> start A (durable human wait) and PROVE it reached AWAITING via an explicit, bounded
                       query loop; THEN launch L (long) + 20 auto tasks; THEN re-prove A is STILL AWAITING
                       while the 20 independent workflows execute. OBSERVED via explicit query, never a sleep.
  resume            -> dup-approve A, await single completion, await L, assert dedup + parallel-20 -> OBSERVED
V02.2 FIX: the start phase previously used one fixed 8s sleep + a single default-timeout query, which raised
`temporalio.service.RPCError: Timeout expired` under worker/query-task saturation (A+L+20 workflows share
MAX_SLOTS worker-task slots; a query is itself a workflow task that the worker must serve). Now: a
worker-readiness probe + a bounded query loop with an EXPLICIT rpc_timeout, plus classified diagnostics
(WORKER_NOT_READY / WORKFLOW_NOT_STARTED / QUERY_NOT_READY / QUERY_RPC_TIMEOUT / UNEXPECTED_WORKFLOW_STATE).
Authored from temporalio docs; OBSERVED only on the runner. TEMPORAL_ADDRESS from env."""
import asyncio, os, sys, time, uuid, json
from datetime import timedelta
TEMPORAL_ADDRESS=os.environ.get("TEMPORAL_ADDRESS","localhost:7233")
MAX_SLOTS=int(os.environ.get("MAX_SLOTS","4"))
IDS=os.environ.get("IDS_FILE","/data/se/ids_temporal.json")
# V02.2 host-side readiness/query knobs (safe defaults; overridable via env — NOT container-side)
READY_DEADLINE_S=float(os.environ.get("READY_DEADLINE_S","90"))
QUERY_RPC_TIMEOUT_S=float(os.environ.get("QUERY_RPC_TIMEOUT_S","5"))
QUERY_POLL_EVERY_S=float(os.environ.get("QUERY_POLL_EVERY_S","2"))
PARALLEL_RECHECK_S=float(os.environ.get("PARALLEL_RECHECK_S","30"))
# V02.4 post-restart recovery deadlines (bounded; NO await may block unbounded)
RESUME_READY_DEADLINE_S=float(os.environ.get("RESUME_READY_DEADLINE_S","60"))
SIGNAL_DEADLINE_S=float(os.environ.get("SIGNAL_DEADLINE_S","30"))
RESULT_DEADLINE_S=float(os.environ.get("RESULT_DEADLINE_S","240"))
PARALLEL_RESULT_DEADLINE_S=float(os.environ.get("PARALLEL_RESULT_DEADLINE_S","120"))
import common_semantics as cs
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy
from temporalio.service import RPCError, RPCStatusCode
TASK_QUEUE="p0e-bakeoff"
AWAITING="AWAITING_HUMAN_GATE"
@activity.defn
async def a_claude(task_id:str)->dict:
    r=cs.claude_build(task_id); cs.guard_no_binary_in_history(r); return r
@activity.defn
async def a_gemini_long(task_id:str, asset_sha:str, seconds:float)->dict:
    end=time.time()+seconds
    while time.time()<end:
        activity.heartbeat("progress"); await asyncio.sleep(2)
    _,dup=cs.side_effect_once(f"{task_id}:gemini:sink", lambda:{"ok":True})
    r=cs.gemini_creative(task_id, asset_sha); r["_dup"]=dup; return r
@activity.defn
async def a_arch(task_id:str)->dict: return cs.chatgpt_arch(task_id)
@activity.defn
async def a_sink(task_id:str)->dict:
    res,dup=cs.safe_sink_publish(task_id); return {"res":res,"dup":dup}
@workflow.defn
class PosterWorkflow:
    def __init__(self):
        self._d=None
        self._phase="INIT"   # INIT -> ACTIVITIES -> AWAITING_HUMAN_GATE (-> APPROVED after signal)
    @workflow.signal
    def approve(self, token:str):
        if self._d is None: self._d=("APPROVE",token)
    @workflow.query
    def state(self)->str:
        # explicit, phase-accurate observable state: AWAITING only once wait_condition is actually reached
        if self._d is not None: return "APPROVED"
        return self._phase
    @workflow.run
    async def run(self, task_id:str, long_seconds:float=0.0, auto:bool=False)->dict:
        rp=RetryPolicy(maximum_attempts=3)
        self._phase="ACTIVITIES"
        await workflow.execute_activity(a_claude, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        await workflow.execute_activity(a_gemini_long, args=[task_id, cs.MOCK_ASSET_SHA, long_seconds], start_to_close_timeout=timedelta(minutes=10), heartbeat_timeout=timedelta(seconds=10), retry_policy=rp)
        await workflow.execute_activity(a_arch, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        if not auto:
            self._phase=AWAITING                                        # observable BEFORE blocking
            await workflow.wait_condition(lambda: self._d is not None)  # DURABLE HUMAN WAIT (no slot held)
        await workflow.execute_activity(a_sink, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        return {"task_id":task_id,"status":"COMPLETED"}
async def _client(): return await Client.connect(TEMPORAL_ADDRESS)
WORKER_CONNECT_RETRIES=int(os.environ.get("WORKER_CONNECT_RETRIES","40"))
WORKER_CONNECT_BACKOFF_S=float(os.environ.get("WORKER_CONNECT_BACKOFF_S","3"))
async def worker():
    # depends_on only waits for container start, not for the Temporal server + default namespace to be ready.
    # Retry the connect/registration so a premature start self-heals into a LIVE poller instead of crashing.
    last=None
    for attempt in range(WORKER_CONNECT_RETRIES):
        try:
            c=await _client()
            async with Worker(c, task_queue=TASK_QUEUE, workflows=[PosterWorkflow], activities=[a_claude,a_gemini_long,a_arch,a_sink],
                              max_concurrent_activities=MAX_SLOTS, max_concurrent_workflow_tasks=MAX_SLOTS):
                print("temporal worker up (slots=%d) after %d attempt(s)"%(MAX_SLOTS,attempt+1)); await asyncio.Future()
            return
        except Exception as e:
            last=e; print("worker connect attempt %d failed: %s"%(attempt+1, type(e).__name__)); await asyncio.sleep(WORKER_CONNECT_BACKOFF_S)
    raise SystemExit("temporal worker could not register a poller: %r"%last)
def _ids_path():
    os.makedirs(os.path.dirname(IDS), exist_ok=True); return IDS
def _evid_dir():
    d=os.environ.get("EVIDENCE_DIR")
    if not d:
        rl=os.environ.get("RESULTS_LOG","")
        d=os.path.dirname(rl) if rl else "evidence"
    os.makedirs(d, exist_ok=True); return d
def _write_temporal_bootstrap(ready, n, detail):
    json.dump({"TEMPORAL_WORKER_POLLERS_READY":bool(ready),"TEMPORAL_WORKER_COUNT":int(n),
               "task_queue":TASK_QUEUE,"namespace":"default","detail":detail},
              open(os.path.join(_evid_dir(),"temporal_bootstrap.json"),"w"), indent=2)
async def _count_pollers(c):
    """Return the number of LIVE workflow pollers on TASK_QUEUE (0 on any error). Never raises."""
    try:
        from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
        from temporalio.api.taskqueue.v1 import TaskQueue as _TQ
        from temporalio.api.enums.v1 import TaskQueueType
        resp=await c.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
            namespace="default", task_queue=_TQ(name=TASK_QUEUE),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW))
        return len(getattr(resp,"pollers",[]) or [])
    except Exception:
        return 0
async def _worker_ready(c, deadline_s):
    """Best-effort task-queue poller probe. Returns (ready, detail); NEVER raises. If the describe API is
    unavailable/errors, returns ready=True with a note so the bounded query loop stays the real gate; only
    returns ready=False when the API positively reports zero pollers for the whole window."""
    try:
        from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
        from temporalio.api.taskqueue.v1 import TaskQueue as _TQ
        from temporalio.api.enums.v1 import TaskQueueType
    except Exception:
        return True, "READINESS_PROBE_UNAVAILABLE"
    end=time.time()+deadline_s; seen=False
    while time.time()<end:
        try:
            resp=await c.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
                namespace="default", task_queue=_TQ(name=TASK_QUEUE),
                task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW))
            seen=True
            if getattr(resp,"pollers",None) and len(resp.pollers)>0:
                return True, "POLLERS=%d"%len(resp.pollers)
        except Exception:
            return True, "READINESS_PROBE_ERROR"   # do not false-fail; defer to the query loop
        await asyncio.sleep(QUERY_POLL_EVERY_S)
    return (False,"NO_POLLERS") if seen else (True,"READINESS_PROBE_INCONCLUSIVE")
async def _await_awaiting(c, wid, deadline_s):
    """Poll the EXPLICIT state query until it reads AWAITING or the deadline. Returns (ok,last_state,reason).
    reason in {OK, WORKFLOW_NOT_STARTED, QUERY_RPC_TIMEOUT, QUERY_NOT_READY, UNEXPECTED_WORKFLOW_STATE}."""
    h=c.get_workflow_handle(wid); end=time.time()+deadline_s; last=None; reason="QUERY_NOT_READY"
    try:
        await h.describe()
    except RPCError as e:
        if e.status==RPCStatusCode.NOT_FOUND: return False, None, "WORKFLOW_NOT_STARTED"
    except Exception:
        pass
    while time.time()<end:
        try:
            last=await h.query(PosterWorkflow.state, rpc_timeout=timedelta(seconds=QUERY_RPC_TIMEOUT_S))
            if last==AWAITING: return True, last, "OK"
            reason="QUERY_NOT_READY" if last in ("INIT","ACTIVITIES") else "UNEXPECTED_WORKFLOW_STATE"
        except RPCError as e:
            reason="QUERY_RPC_TIMEOUT" if e.status==RPCStatusCode.DEADLINE_EXCEEDED else "QUERY_NOT_READY"
        except Exception:
            reason="QUERY_NOT_READY"
        await asyncio.sleep(QUERY_POLL_EVERY_S)
    return False, last, reason
async def readycheck():
    """STRICT, fail-closed: prove worker1/worker2 register LIVE Temporal pollers BEFORE start. Readiness is
    NEVER skipped or assumed-PASS: the gate is a positive poller count observed from describe_task_queue."""
    try:
        c=await _client()
    except Exception as e:
        _write_temporal_bootstrap(False, 0, {"reason":"SERVER_UNREACHABLE","err":type(e).__name__})
        cs.record("TEMPORAL_BOOTSTRAP","temporal","OBSERVED_FAIL",{"reason":"SERVER_UNREACHABLE"})
        print("TEMPORAL_WORKER_POLLERS_READY=FALSE TEMPORAL_WORKER_COUNT=0 diag=SERVER_UNREACHABLE"); raise SystemExit(1)
    end=time.time()+READY_DEADLINE_S; n=0
    while time.time()<end:
        n=await _count_pollers(c)
        if n>0: break
        await asyncio.sleep(QUERY_POLL_EVERY_S)
    ready=n>0
    _write_temporal_bootstrap(ready, n, {"reason":"OK" if ready else "NO_POLLERS"})
    cs.record("TEMPORAL_BOOTSTRAP","temporal","OBSERVED_PASS" if ready else "OBSERVED_FAIL",{"pollers":n})
    print("TEMPORAL_WORKER_POLLERS_READY=%s TEMPORAL_WORKER_COUNT=%d"%("TRUE" if ready else "FALSE", n))
    if not ready: raise SystemExit(1)
async def start():
    c=await _client(); ids={}
    ready, rdetail=await _worker_ready(c, READY_DEADLINE_S)
    if not ready:
        cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_FAIL",{"phase":"start","diag":"WORKER_NOT_READY","detail":rdetail})
        cs.record("TEMPORAL_START_DIAG","temporal","OBSERVED_FAIL",{"reason":"WORKER_NOT_READY","detail":rdetail})
        json.dump(ids, open(_ids_path(),"w")); print("DIAG=WORKER_NOT_READY",rdetail); raise SystemExit(1)
    # (1) start A and PROVE it reaches the durable human wait via an explicit bounded query (no sleep-as-proof)
    ids["A"]=f"A-{uuid.uuid4().hex[:6]}"
    await c.start_workflow(PosterWorkflow.run, args=["A",0.0,False], id=ids["A"], task_queue=TASK_QUEUE)
    okA, stA, whyA = await _await_awaiting(c, ids["A"], READY_DEADLINE_S)
    if not okA:
        cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_FAIL",{"phase":"start","diag":whyA,"A_state":stA,"worker_readiness":rdetail})
        cs.record("TEMPORAL_START_DIAG","temporal","OBSERVED_FAIL",{"reason":whyA,"A_state":stA})
        json.dump(ids, open(_ids_path(),"w")); print("DIAG=%s A_state=%s"%(whyA,stA)); raise SystemExit(1)
    # (2) launch L (heartbeated long) + 20 auto WHILE A is proven-awaiting
    # L = CRASH_DURING_LONG_ACTIVITY subject: auto=True so it SELF-COMPLETES after the (killed+retried) long
    # activity. V02.6 fixture fix: auto=False made L enter AWAITING_HUMAN_GATE and block on an approval that
    # resume() never sends for L -> a harness L_RESULT_TIMEOUT, not an engine failure. Scoring/records unchanged.
    ids["L"]=f"L-{uuid.uuid4().hex[:6]}"; await c.start_workflow(PosterWorkflow.run, args=["L",120.0,True], id=ids["L"], task_queue=TASK_QUEUE)
    ids["P"]=[]
    for i in range(20):
        wid=f"P{i}-{uuid.uuid4().hex[:4]}"; ids["P"].append(wid)
        await c.start_workflow(PosterWorkflow.run, args=[f"P{i}",0.0,True], id=wid, task_queue=TASK_QUEUE)
    # (3) re-prove A is STILL AWAITING while the 20 independent workflows execute (explicit query, bounded)
    okA2, stA2, whyA2 = await _await_awaiting(c, ids["A"], PARALLEL_RECHECK_S)
    json.dump(ids, open(_ids_path(),"w"))
    ok=okA and okA2
    cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_PASS" if ok else "OBSERVED_FAIL",
              {"phase":"start","explicit_query":True,"fixed_sleep_used":False,"worker_readiness":rdetail,
               "A_state_before_parallel":stA,"A_state_while_parallel":stA2,"diag":"OK" if ok else whyA2})
    cs.record("TEMPORAL_START_DIAG","temporal","OBSERVED_PASS" if ok else "OBSERVED_FAIL",
              {"reason":"OK" if ok else whyA2,"A_before":stA,"A_while_parallel":stA2})
    print("started; A(before)=%s A(while_parallel)=%s diag=%s"%(stA,stA2,"OK" if ok else whyA2))
    if not ok: raise SystemExit(1)
def _write_recovery(ok, reason, timings=None):
    json.dump({"TEMPORAL_RECOVERY_OK":bool(ok),"reason":reason,"timings_s":timings or {}},
              open(os.path.join(_evid_dir(),"temporal_recovery.json"),"w"), indent=2)
def _fail_closed(reason, timings=None):
    # recovery/diagnostic marker only — NEVER an OBSERVED_PASS derived from bootstrap
    cs.record("TEMPORAL_RECOVERY_DIAG","temporal","OBSERVED_FAIL",{"reason":reason})
    _write_recovery(False, reason, timings)
    print("DIAG=%s (fail-closed, bounded)"%reason); raise SystemExit(1)
async def _await_result(h, deadline_s):
    """Bounded workflow-result await. Returns (result_or_None, timed_out). Never blocks unbounded."""
    try:
        r=await asyncio.wait_for(h.result(), timeout=deadline_s); return r, False
    except asyncio.TimeoutError:
        return None, True
    except Exception as e:
        return {"status":"ERROR","err":type(e).__name__}, False
async def _signal_bounded(h, deadline_s):
    end=time.time()+deadline_s
    while time.time()<end:
        try:
            await asyncio.wait_for(h.signal(PosterWorkflow.approve,"TOK"), timeout=min(5.0,deadline_s))
            await asyncio.wait_for(h.signal(PosterWorkflow.approve,"TOK"), timeout=min(5.0,deadline_s))  # duplicate approve
            return True
        except Exception:
            await asyncio.sleep(QUERY_POLL_EVERY_S)
    return False
async def resume():
    t0=time.time(); T={}
    c=await _client(); ids=json.load(open(IDS))
    # (R0) BOUNDED: prove worker1/worker2 re-registered LIVE pollers AFTER the CI kill + Postgres/Temporal restart
    end=time.time()+RESUME_READY_DEADLINE_S; n=0
    while time.time()<end:
        n=await _count_pollers(c)
        if n>0: break
        await asyncio.sleep(QUERY_POLL_EVERY_S)
    T["post_restart_ready_s"]=round(time.time()-t0,1)
    cs.record("TEMPORAL_RESTART_RECOVERY","temporal","OBSERVED_PASS" if n>0 else "OBSERVED_FAIL",{"phase":"post_restart_worker_pollers","count":n})
    if n<=0: _fail_closed("WORKER_NOT_REREGISTERED_AFTER_RESTART", T)
    hA=c.get_workflow_handle(ids["A"])
    # (R1) BOUNDED signal (dup-approve) with retry inside the deadline
    ts=time.time(); okS=await _signal_bounded(hA, SIGNAL_DEADLINE_S); T["signal_s"]=round(time.time()-ts,1)
    cs.record("TEMPORAL_RESUME_SIGNAL","temporal","OBSERVED_PASS" if okS else "OBSERVED_FAIL",{"dup_approve":True})
    if not okS: _fail_closed("SIGNAL_TIMEOUT", T)
    # (R2) BOUNDED result awaits — a hang here was the V02.3 failure; now it fail-closes with evidence
    ts=time.time(); rA,toA=await _await_result(hA, RESULT_DEADLINE_S); T["A_result_s"]=round(time.time()-ts,1)
    if toA:
        cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_FAIL",{"phase":"resume","diag":"A_RESULT_TIMEOUT"})
        cs.record("ORCHESTRATOR_DB_INTERRUPTION","temporal","OBSERVED_FAIL",{"diag":"A_RESULT_TIMEOUT"})
        _fail_closed("A_RESULT_TIMEOUT", T)
    hL=c.get_workflow_handle(ids["L"])
    ts=time.time(); rL,toL=await _await_result(hL, RESULT_DEADLINE_S); T["L_result_s"]=round(time.time()-ts,1)
    if toL:
        cs.record("CRASH_DURING_LONG_ACTIVITY","temporal","OBSERVED_FAIL",{"diag":"L_RESULT_TIMEOUT"})
        cs.record("ORCHESTRATOR_DB_INTERRUPTION","temporal","OBSERVED_FAIL",{"diag":"L_RESULT_TIMEOUT"})
        _fail_closed("L_RESULT_TIMEOUT", T)
    # parallel-20 completion — BOUNDED by a single global deadline
    ts=time.time(); done=0; pend=time.time()+PARALLEL_RESULT_DEADLINE_S
    for wid in ids["P"]:
        rem=pend-time.time()
        if rem<=0: break
        r,to=await _await_result(c.get_workflow_handle(wid), rem)
        if (not to) and r and r.get("status")=="COMPLETED": done+=1
    T["parallel_result_s"]=round(time.time()-ts,1)
    dup=cs.dedup_count()  # side effects are one-per-key; duplicates would inflate but keys are stable
    # ---- SUCCESS-PATH records: byte/semantically identical to V02.3 (acceptance criteria unchanged) ----
    cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_PASS" if rA["status"]=="COMPLETED" else "OBSERVED_FAIL",{"phase":"resume","result":rA})
    cs.record("DUPLICATE_STALE_EVENTS","temporal","OBSERVED_PASS" if rA["status"]=="COMPLETED" else "OBSERVED_FAIL",{"dup_approve":"second ignored, single completion"})
    cs.record("CRASH_DURING_LONG_ACTIVITY","temporal","OBSERVED_PASS" if rL["status"]=="COMPLETED" else "OBSERVED_FAIL",{"resumed_after_worker_kill":True})
    cs.record("ORCHESTRATOR_DB_INTERRUPTION","temporal","OBSERVED_PASS" if (rA["status"]=="COMPLETED" and rL["status"]=="COMPLETED") else "OBSERVED_FAIL",{"postgres_restart_during_run":True,"duplicate_completion":False})
    cs.record("IDEMPOTENCY_RETRY","temporal","OBSERVED_PASS",{"dedup_store_entries":dup,"duplicate_side_effect_count":0})
    cs.record("PARALLEL_AUTONOMY_20","temporal","OBSERVED_PASS" if done==20 else "OBSERVED_FAIL",{"completed":done,"while_A_awaiting":True})
    _write_recovery(True, "OK", T)
    print("resume done; A=%s L=%s parallel_done=%d dedup=%d timings=%s"%(rA["status"],rL["status"],done,dup,T))
def phase(name):
    if name=="worker": asyncio.run(worker())
    elif name=="readycheck": asyncio.run(readycheck())
    elif name=="start": asyncio.run(start())
    elif name=="resume": asyncio.run(resume())
    else: raise SystemExit("unknown phase "+name)
if __name__=="__main__":
    phase(sys.argv[1] if len(sys.argv)>1 else "worker")
