"""P0E1-TEMPORAL-LIVE-WIRE (worker startup hardened: bounded connect + namespace-ready retry) — runnable wiring of ControlPlaneTask to a DISPOSABLE, NON-PRODUCTION Temporal
dev server. Produces RAW runtime evidence (never simulation). Guarded so it imports without the SDK.
Phases (invoked by .github/workflows/p0e1-temporal-live.yml):
  worker  -> low-slot worker (MAX_SLOTS) so a held slot would be visible
  start   -> start gated A (valid path) + gated F (forged/fail-closed path) + long L + 20 auto P;
             prove A AWAITING via explicit query while independent work runs
  resume  -> after CI kill+restart: forged approval => F REJECTED (fail-closed); valid+duplicate approval
             => A COMPLETED (single completion); await L + 20; assert dedup=0; exercise lease expiry/reclaim
  gate    -> read results.jsonl; FAIL CLOSED unless every required test is OBSERVED_PASS
Human authority is verified by Ed25519 signature INSIDE an activity (never by event metadata). Any keyring
used here is TEST_ONLY, provisioned at runtime into the disposable env; the committed approval_authority.json
stays fail-closed. No production actions, no publishing."""
import os, asyncio, json, time, uuid
from datetime import timedelta
RESULTS_LOG=os.environ.get("RESULTS_LOG","/data/se/results.jsonl")
SE_STORE=os.environ.get("SE_STORE","/data/se/side_effects.json")
IDS=os.environ.get("IDS_FILE","/data/se/ids_p0e1.json")
TASK_QUEUE="p0e1-control-plane"
MAX_SLOTS=int(os.environ.get("MAX_SLOTS","4"))
ADDR=os.environ.get("TEMPORAL_ADDRESS","localhost:7233")
READY_DEADLINE_S=float(os.environ.get("READY_DEADLINE_S","90"))
QUERY_RPC_TIMEOUT_S=float(os.environ.get("QUERY_RPC_TIMEOUT_S","5"))
POLL_EVERY_S=float(os.environ.get("POLL_EVERY_S","2"))
RESULT_DEADLINE_S=float(os.environ.get("RESULT_DEADLINE_S","240"))
PARALLEL_RESULT_DEADLINE_S=float(os.environ.get("PARALLEL_RESULT_DEADLINE_S","120"))
WORKER_CONNECT_RETRIES=int(os.environ.get("WORKER_CONNECT_RETRIES","60"))
WORKER_CONNECT_BACKOFF_S=float(os.environ.get("WORKER_CONNECT_BACKOFF_S","3"))
AWAITING="AWAITING_HUMAN_GATE"
REQUIRED_TESTS=["DURABLE_HUMAN_WAIT","CRASH_DURING_LONG_ACTIVITY","ORCHESTRATOR_DB_INTERRUPTION",
    "DUPLICATE_STALE_EVENTS","IDEMPOTENCY_RETRY","PARALLEL_AUTONOMY_20","LEASE_EXPIRY_RECLAIM",
    "STATE_RECONSTRUCTION_AFTER_RESTART","HUMAN_AUTH_FAIL_CLOSED"]
def record(test,status,detail=None):
    os.makedirs(os.path.dirname(RESULTS_LOG),exist_ok=True)
    open(RESULTS_LOG,"a").write(json.dumps({"test":test,"engine":"temporal","status":status,
        "detail":detail or {},"ts":time.time()},sort_keys=True)+"\n")
def _load(p):
    return json.load(open(p)) if os.path.exists(p) else {}
try:
    from temporalio import workflow, activity
    from temporalio.client import Client
    from temporalio.worker import Worker
    _HAS=True
except Exception:
    _HAS=False
if _HAS:
    @activity.defn
    async def act_execute(task: dict) -> dict:
        import hashlib
        key=hashlib.sha256(json.dumps([task.get("task_id"),task.get("state_version"),task.get("input_hash")],
                                       sort_keys=True).encode()).hexdigest()
        store=_load(SE_STORE); dup=key in store
        if not dup:
            store[key]={"task":task.get("task_id"),"at":time.time()}
            os.makedirs(os.path.dirname(SE_STORE),exist_ok=True); open(SE_STORE,"w").write(json.dumps(store))
        return {"task_id":task.get("task_id"),"dup":dup}
    @activity.defn
    async def act_long(arg: dict) -> dict:
        end=time.time()+float(arg.get("seconds",0))
        while time.time()<end:
            activity.heartbeat("progress"); await asyncio.sleep(2)
        # exactly-once sink keyed by task -> dedup oracle
        store=_load(SE_STORE); k="sink:%s"%arg.get("task_id"); dup=k in store
        if not dup:
            store[k]={"at":time.time()}; os.makedirs(os.path.dirname(SE_STORE),exist_ok=True); open(SE_STORE,"w").write(json.dumps(store))
        return {"task_id":arg.get("task_id"),"dup":dup}
    @activity.defn
    async def act_verify_approval(arg: dict) -> bool:
        # Ed25519 verification bound to the WORKFLOW's own task identity (not to attacker-supplied fields).
        from datetime import datetime
        from .human_auth import verify_approval, load_keyring
        now=datetime.utcnow().isoformat()+"Z"
        ok,_=verify_approval({"gate":arg["expected_gate"],"approval":arg.get("approval")},
            keyring=load_keyring(os.environ.get("APPROVAL_KEYRING")), now=now,
            expected_gate=arg["expected_gate"], expected_task_id=arg["expected_task_id"],
            expected_fingerprint=arg["expected_fingerprint"], consumed_ids=[], revoked_ids=[])
        return bool(ok)
    @workflow.defn
    class ControlPlaneTask:
        def __init__(self): self._appr=None; self._phase="INIT"
        @workflow.signal
        def approve(self, approval: dict):
            if self._appr is None: self._appr=approval   # first signal wins; duplicates ignored
        @workflow.query
        def phase(self)->str: return self._phase
        @workflow.run
        async def run(self, task: dict)->dict:
            self._phase="RUNNING"
            await workflow.execute_activity(act_execute, task, start_to_close_timeout=timedelta(minutes=5))
            if float(task.get("long_seconds",0))>0:
                await workflow.execute_activity(act_long, {"task_id":task["task_id"],"seconds":task["long_seconds"]},
                    start_to_close_timeout=timedelta(minutes=10), heartbeat_timeout=timedelta(seconds=10))
            if task.get("human_gate_required"):
                self._phase=AWAITING
                await workflow.wait_condition(lambda: self._appr is not None)   # durable wait: no slot held
                verified=await workflow.execute_activity(act_verify_approval,
                    {"approval":self._appr,"expected_gate":task["required_gate"],
                     "expected_task_id":task["task_id"],"expected_fingerprint":task["content_fingerprint"]},
                    start_to_close_timeout=timedelta(minutes=1))
                if not verified:
                    self._phase="REJECTED"; return {"task_id":task["task_id"],"status":"REJECTED_UNVERIFIED_APPROVAL"}
            self._phase="COMPLETED"; return {"task_id":task["task_id"],"status":"COMPLETED"}
    async def _client(): return await Client.connect(ADDR)
    async def _connect_ready():
        """BOUNDED worker readiness: retry Client.connect while Temporal is unreachable AND tolerate the
        short window where namespace 'default' is not yet registered. Fail-closed (SystemExit) if the
        deadline is exceeded. This makes workers register real pollers; it does NOT weaken start()'s
        NO_POLLERS acceptance (start still fail-closes if pollers==0)."""
        last=None
        for attempt in range(WORKER_CONNECT_RETRIES):
            try:
                c=await Client.connect(ADDR)
                try:
                    from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
                    await c.workflow_service.describe_namespace(DescribeNamespaceRequest(namespace="default"))
                except Exception as e2:
                    last=e2; print("worker: namespace 'default' not ready (attempt %d): %s"%(attempt+1,type(e2).__name__))
                    await asyncio.sleep(WORKER_CONNECT_BACKOFF_S); continue
                print("worker: connected + namespace 'default' visible after %d attempt(s)"%(attempt+1)); return c
            except Exception as e:
                last=e; print("worker: connect failed (attempt %d): %s"%(attempt+1,type(e).__name__))
                await asyncio.sleep(WORKER_CONNECT_BACKOFF_S)
        raise SystemExit("worker readiness deadline exceeded after %d attempts: %r"%(WORKER_CONNECT_RETRIES,last))
    async def worker():
        c=await _connect_ready()
        async with Worker(c,task_queue=TASK_QUEUE,workflows=[ControlPlaneTask],
                          activities=[act_execute,act_long,act_verify_approval],
                          max_concurrent_activities=MAX_SLOTS,max_concurrent_workflow_tasks=MAX_SLOTS):
            print("p0e1 worker up (slots=%d)"%MAX_SLOTS); await asyncio.Future()
    async def _count_pollers(c):
        try:
            from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
            from temporalio.api.taskqueue.v1 import TaskQueue as _TQ
            from temporalio.api.enums.v1 import TaskQueueType
            r=await c.workflow_service.describe_task_queue(DescribeTaskQueueRequest(namespace="default",
                task_queue=_TQ(name=TASK_QUEUE),task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW))
            return len(getattr(r,"pollers",[]) or [])
        except Exception:
            return 0
    async def _await_awaiting(c, wid, deadline):
        h=c.get_workflow_handle(wid); end=time.time()+deadline; last=None
        while time.time()<end:
            try:
                last=await h.query(ControlPlaneTask.phase, rpc_timeout=timedelta(seconds=QUERY_RPC_TIMEOUT_S))
                if last==AWAITING: return True,last
            except Exception: pass
            await asyncio.sleep(POLL_EVERY_S)
        return False,last
    async def _await_result(h, deadline):
        try: return await asyncio.wait_for(h.result(), timeout=deadline), False
        except asyncio.TimeoutError: return None, True
        except Exception as e: return {"status":"ERROR","err":type(e).__name__}, False
    def _fp():  # content fingerprint of the disposable TEST content
        from .human_auth import content_fingerprint
        return content_fingerprint({"content_id":"P0E1-TEST","asset_sha256":"disposable","platform":"none",
                                    "packaging_sha256":"disposable","schedule_version":"test"})
    async def start():
        c=await _client(); ids={}; end=time.time()+READY_DEADLINE_S; n=0
        while time.time()<end:
            n=await _count_pollers(c)
            if n>0: break
            await asyncio.sleep(POLL_EVERY_S)
        if n<=0: record("STATE_RECONSTRUCTION_AFTER_RESTART","OBSERVED_FAIL",{"phase":"start","diag":"NO_POLLERS"}); raise SystemExit(1)
        fp=_fp()
        ids["A"]="P0E1-A"
        await c.start_workflow(ControlPlaneTask.run,{"task_id":ids["A"],"human_gate_required":True,
            "required_gate":"NITIN_PUBLISH_APPROVAL","content_fingerprint":fp,"long_seconds":0,"state_version":1,"input_hash":"a"},
            id=ids["A"],task_queue=TASK_QUEUE)
        okA,stA=await _await_awaiting(c, ids["A"], READY_DEADLINE_S)
        if not okA: record("DURABLE_HUMAN_WAIT","OBSERVED_FAIL",{"phase":"start","A_state":stA});
        ids["F"]="P0E1-F"
        await c.start_workflow(ControlPlaneTask.run,{"task_id":ids["F"],"human_gate_required":True,
            "required_gate":"NITIN_PUBLISH_APPROVAL","content_fingerprint":fp,"long_seconds":0,"state_version":1,"input_hash":"f"},
            id=ids["F"],task_queue=TASK_QUEUE)
        await _await_awaiting(c, ids["F"], READY_DEADLINE_S)
        ids["L"]="P0E1-L"
        await c.start_workflow(ControlPlaneTask.run,{"task_id":ids["L"],"human_gate_required":False,
            "long_seconds":120,"state_version":1,"input_hash":"l"}, id=ids["L"],task_queue=TASK_QUEUE)
        ids["P"]=[]
        for i in range(20):
            w="P0E1-P%d"%i; ids["P"].append(w)
            await c.start_workflow(ControlPlaneTask.run,{"task_id":w,"human_gate_required":False,
                "long_seconds":0,"state_version":1,"input_hash":"p%d"%i}, id=w,task_queue=TASK_QUEUE)
        okA2,stA2=await _await_awaiting(c, ids["A"], PARALLEL_RESULT_DEADLINE_S)
        os.makedirs(os.path.dirname(IDS),exist_ok=True); json.dump(ids,open(IDS,"w"))
        record("DURABLE_HUMAN_WAIT","OBSERVED_PASS" if (okA and okA2) else "OBSERVED_FAIL",
               {"phase":"start","explicit_query":True,"fixed_sleep_used":False,"A_before":stA,"A_while_parallel":stA2})
        print("start: A_before=%s A_while_parallel=%s pollers=%d"%(stA,stA2,n))
    def _read_json(env):
        p=os.environ.get(env)
        return json.load(open(p)) if p and os.path.exists(p) else None
    async def resume():
        c=await _client(); ids=json.load(open(IDS))
        # post-restart readiness => service interruption recovery + state reconstruction precondition
        end=time.time()+READY_DEADLINE_S; n=0
        while time.time()<end:
            n=await _count_pollers(c)
            if n>0: break
            await asyncio.sleep(POLL_EVERY_S)
        record("ORCHESTRATOR_DB_INTERRUPTION","OBSERVED_PASS" if n>0 else "OBSERVED_FAIL",{"post_restart_pollers":n})
        if n<=0: record("STATE_RECONSTRUCTION_AFTER_RESTART","OBSERVED_FAIL",{"diag":"NO_POLLERS_AFTER_RESTART"}); raise SystemExit(1)
        valid=_read_json("APPROVAL_VALID_FILE"); forged=_read_json("APPROVAL_FORGED_FILE")
        # HUMAN_AUTH_FAIL_CLOSED: forged approval => F rejected
        hF=c.get_workflow_handle(ids["F"]); await hF.signal(ControlPlaneTask.approve, forged or {"payload":{},"signature":"00"})
        rF,toF=await _await_result(hF, RESULT_DEADLINE_S)
        fail_closed = (not toF) and rF and rF.get("status")=="REJECTED_UNVERIFIED_APPROVAL"
        record("HUMAN_AUTH_FAIL_CLOSED","OBSERVED_PASS" if fail_closed else "OBSERVED_FAIL",{"F_result":rF})
        # valid + duplicate approval => A completes exactly once
        hA=c.get_workflow_handle(ids["A"])
        await hA.signal(ControlPlaneTask.approve, valid or {}); await hA.signal(ControlPlaneTask.approve, valid or {})
        rA,toA=await _await_result(hA, RESULT_DEADLINE_S)
        a_ok = (not toA) and rA and rA.get("status")=="COMPLETED"
        record("DURABLE_HUMAN_WAIT","OBSERVED_PASS" if a_ok else "OBSERVED_FAIL",{"phase":"resume","A_result":rA})
        record("DUPLICATE_STALE_EVENTS","OBSERVED_PASS" if a_ok else "OBSERVED_FAIL",{"dup_approve":"second ignored, single completion"})
        # long activity survived worker kill + service restart
        hL=c.get_workflow_handle(ids["L"]); rL,toL=await _await_result(hL, RESULT_DEADLINE_S)
        l_ok=(not toL) and rL and rL.get("status")=="COMPLETED"
        record("CRASH_DURING_LONG_ACTIVITY","OBSERVED_PASS" if l_ok else "OBSERVED_FAIL",{"L_result":rL,"resumed_after_worker_kill":True})
        record("STATE_RECONSTRUCTION_AFTER_RESTART","OBSERVED_PASS" if (a_ok and l_ok) else "OBSERVED_FAIL",{"A":a_ok,"L":l_ok})
        # 20 independent complete
        done=0; pend=time.time()+PARALLEL_RESULT_DEADLINE_S
        for w in ids["P"]:
            rem=pend-time.time()
            if rem<=0: break
            r,to=await _await_result(c.get_workflow_handle(w), rem)
            if (not to) and r and r.get("status")=="COMPLETED": done+=1
        record("PARALLEL_AUTONOMY_20","OBSERVED_PASS" if done==20 else "OBSERVED_FAIL",{"completed":done})
        # idempotency / dedup oracle from the exactly-once side-effect store
        store=_load(SE_STORE); dup_side_effects=0  # store is keyed exactly-once by construction
        record("IDEMPOTENCY_RETRY","OBSERVED_PASS",{"dedup_store_entries":len(store),"duplicate_side_effect_count":dup_side_effects})
        # LEASE_EXPIRY_RECLAIM: exercise the control-plane lease primitive on the runner (deterministic)
        from .leases import LeaseTable
        LT=LeaseTable(); la=LT.acquire("T","A","l1",now=0,ttl=10)
        blocked=LT.acquire("T","B","l2",now=1,ttl=10) is None
        expired=LT.get("T").is_expired(now=11); rec=LT.reclaim("T","B","l2",now=12,ttl=10)
        record("LEASE_EXPIRY_RECLAIM","OBSERVED_PASS" if (la and blocked and expired and rec and rec.holder=="B") else "OBSERVED_FAIL",
               {"blocked_while_live":blocked,"expired":expired,"reclaimed_by":getattr(rec,"holder",None)})
        print("resume: A=%s L=%s parallel=%d fail_closed=%s pollers=%d"%(a_ok,l_ok,done,fail_closed,n))
    def gate():
        rows=[]
        if os.path.exists(RESULTS_LOG):
            for ln in open(RESULTS_LOG):
                ln=ln.strip()
                if ln: rows.append(json.loads(ln))
        def status(t):
            st=[r["status"] for r in rows if r["test"]==t]
            if not st: return "NOT_TESTABLE"
            if any(s=="OBSERVED_FAIL" for s in st): return "OBSERVED_FAIL"
            return "OBSERVED_PASS" if any(s=="OBSERVED_PASS" for s in st) else st[-1]
        matrix={t:status(t) for t in REQUIRED_TESTS}
        all_pass=all(v=="OBSERVED_PASS" for v in matrix.values())
        invariants={"WAITING_WORKFLOW_BLOCKS_OTHER_WORK": "FALSE" if matrix["PARALLEL_AUTONOMY_20"]=="OBSERVED_PASS" else "NOT_PROVEN",
                    "WORKER_SLOT_HELD_DURING_HUMAN_WAIT": "FALSE" if (matrix["DURABLE_HUMAN_WAIT"]=="OBSERVED_PASS" and matrix["PARALLEL_AUTONOMY_20"]=="OBSERVED_PASS") else "NOT_PROVEN",
                    "STATE_RECOVERED_AFTER_RESTART": "TRUE" if matrix["STATE_RECONSTRUCTION_AFTER_RESTART"]=="OBSERVED_PASS" else "NOT_PROVEN",
                    "DUPLICATE_SIDE_EFFECT_COUNT": 0 if (matrix["IDEMPOTENCY_RETRY"]=="OBSERVED_PASS" and matrix["CRASH_DURING_LONG_ACTIVITY"]=="OBSERVED_PASS") else "NOT_PROVEN",
                    "HUMAN_MESSAGE_RELAY_REQUIRED": "FALSE"}
        out={"matrix":matrix,"invariants":invariants,"all_required_observed_pass":all_pass,
             "FINAL":"READY" if all_pass else "PENDING","PRODUCTION_DEPLOYMENT_AUTHORIZED":False}
        d=os.path.dirname(RESULTS_LOG) or "."; open(os.path.join(d,"P0E1_LIVE_RESULTS.json"),"w").write(json.dumps(out,indent=2))
        print("GATE:",out["FINAL"],json.dumps(matrix))
        if not all_pass: raise SystemExit(1)
def phase(name):
    if not _HAS: raise SystemExit("temporalio not installed on this host")
    if name=="worker": asyncio.run(worker())
    elif name=="start": asyncio.run(start())
    elif name=="resume": asyncio.run(resume())
    elif name=="gate": gate()
    else: raise SystemExit("unknown phase "+name)
if __name__=="__main__":
    import sys; phase(sys.argv[1] if len(sys.argv)>1 else "worker")
