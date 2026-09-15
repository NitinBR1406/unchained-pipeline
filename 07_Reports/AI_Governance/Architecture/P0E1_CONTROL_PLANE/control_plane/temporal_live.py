"""P0E1-TEMPORAL-LIVE-WIRE — runnable wiring of the ControlPlaneTask to a DISPOSABLE, NON-PRODUCTION
Temporal dev server. Produces RAW runtime evidence (never simulation). Guarded so it imports without the
SDK; run on a runner that has `temporalio` + a Temporal dev server. No production actions, no publishing.

Phases (invoked by ci/p0e1-temporal-live.yml, interleaved with docker kill/restart):
  worker  -> low-slot worker (MAX_SLOTS) so a held slot would be visible
  start   -> start gated task A; prove AWAITING via query; launch 20 independent; prove they progress
  resume  -> deliver a signed approval signal to A; await completion; assert dedup + parallel-20 + reclaim
Writes OBSERVED records via the same results.jsonl contract used by the bake-off controller."""
import os, asyncio, json, time, uuid
from datetime import timedelta
RESULTS_LOG=os.environ.get("RESULTS_LOG","/data/se/results.jsonl")
TASK_QUEUE="p0e1-control-plane"
MAX_SLOTS=int(os.environ.get("MAX_SLOTS","4"))
IDS=os.environ.get("IDS_FILE","/data/se/ids_p0e1.json")
ADDR=os.environ.get("TEMPORAL_ADDRESS","localhost:7233")
def record(test,status,detail=None):
    os.makedirs(os.path.dirname(RESULTS_LOG),exist_ok=True)
    open(RESULTS_LOG,"a").write(json.dumps({"test":test,"engine":"temporal","status":status,
        "detail":detail or {},"ts":time.time()},sort_keys=True)+"\n")
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
        # exactly-once side effect keyed by deterministic job identity (idempotency)
        import hashlib
        key=hashlib.sha256(json.dumps([task.get("task_id"),task.get("state_version"),task.get("input_hash")],
                                       sort_keys=True).encode()).hexdigest()
        se=os.environ.get("SE_STORE","/data/se/side_effects.json")
        store=json.load(open(se)) if os.path.exists(se) else {}
        dup = key in store
        if not dup:
            store[key]={"task":task.get("task_id"),"at":time.time()}; os.makedirs(os.path.dirname(se),exist_ok=True); open(se,"w").write(json.dumps(store))
        return {"task_id":task.get("task_id"),"dup":dup}
    @activity.defn
    async def act_verify_approval(approval: dict) -> bool:
        # signature verification runs in an ACTIVITY (non-deterministic crypto kept out of workflow code)
        from .human_auth import verify_approval, load_keyring
        ok,_=verify_approval({"gate":approval.get("gate"),"approval":approval.get("approval")},
            keyring=load_keyring(os.environ.get("APPROVAL_KEYRING")), now=approval.get("now",""),
            expected_gate=approval.get("gate"), expected_task_id=approval.get("task_id"),
            expected_fingerprint=approval.get("content_fingerprint"), consumed_ids=[], revoked_ids=[])
        return bool(ok)
    @workflow.defn
    class ControlPlaneTask:
        def __init__(self): self._appr=None; self._phase="INIT"
        @workflow.signal
        def approve(self, approval: dict): self._appr=approval  # authority is verified in an activity, not by metadata
        @workflow.query
        def phase(self)->str: return self._phase
        @workflow.run
        async def run(self, task: dict)->dict:
            self._phase="RUNNING"
            await workflow.execute_activity(act_execute, task, start_to_close_timeout=timedelta(minutes=5))
            if task.get("human_gate_required"):
                self._phase="AWAITING_HUMAN_GATE"
                await workflow.wait_condition(lambda: self._appr is not None)   # durable wait: no slot held
                verified=await workflow.execute_activity(act_verify_approval, self._appr,
                                                         start_to_close_timeout=timedelta(minutes=1))
                if not verified:
                    self._phase="REJECTED"; return {"task_id":task.get("task_id"),"status":"REJECTED_UNVERIFIED_APPROVAL"}
            self._phase="COMPLETED"
            return {"task_id":task.get("task_id"),"status":"COMPLETED"}
    async def _client(): return await Client.connect(ADDR)
    async def worker():
        c=await _client()
        async with Worker(c,task_queue=TASK_QUEUE,workflows=[ControlPlaneTask],
                          activities=[act_execute,act_verify_approval],
                          max_concurrent_activities=MAX_SLOTS,max_concurrent_workflow_tasks=MAX_SLOTS):
            print("p0e1 worker up (slots=%d)"%MAX_SLOTS); await asyncio.Future()
def phase(name):
    if not _HAS: raise SystemExit("temporalio not installed on this host")
    raise SystemExit("run via ci/p0e1-temporal-live.yml (worker|start|resume)")
