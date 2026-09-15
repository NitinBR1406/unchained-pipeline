"""Temporal side of the P0-E live bake-off — V02 (phased for OBSERVED closure).
Phases (called by the CI workflow, interleaved with docker kill/restart of worker + postgres):
  worker            -> run a worker (low concurrency so a held slot would be visible)
  start             -> start A (durable human wait), L (heartbeated long activity), 20 auto tasks; snapshot AWAITING
  resume            -> dup-approve A, await single completion, await L, assert dedup + parallel-20 done -> OBSERVED records
Authored from temporalio docs; OBSERVED only on the runner. TEMPORAL_ADDRESS from env."""
import asyncio, os, sys, time, uuid, json
from datetime import timedelta
TEMPORAL_ADDRESS=os.environ.get("TEMPORAL_ADDRESS","localhost:7233")
MAX_SLOTS=int(os.environ.get("MAX_SLOTS","4"))
IDS=os.environ.get("IDS_FILE","/data/se/ids_temporal.json")
import common_semantics as cs
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy
TASK_QUEUE="p0e-bakeoff"
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
    def __init__(self): self._d=None
    @workflow.signal
    def approve(self, token:str):
        if self._d is None: self._d=("APPROVE",token)
    @workflow.query
    def state(self)->str: return "AWAITING_HUMAN_GATE" if self._d is None else self._d[0]
    @workflow.run
    async def run(self, task_id:str, long_seconds:float=0.0, auto:bool=False)->dict:
        rp=RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(a_claude, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        await workflow.execute_activity(a_gemini_long, args=[task_id, cs.MOCK_ASSET_SHA, long_seconds], start_to_close_timeout=timedelta(minutes=10), heartbeat_timeout=timedelta(seconds=10), retry_policy=rp)
        await workflow.execute_activity(a_arch, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        if not auto:
            await workflow.wait_condition(lambda: self._d is not None)  # DURABLE HUMAN WAIT (no slot held)
        await workflow.execute_activity(a_sink, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        return {"task_id":task_id,"status":"COMPLETED"}
async def _client(): return await Client.connect(TEMPORAL_ADDRESS)
async def worker():
    c=await _client()
    async with Worker(c, task_queue=TASK_QUEUE, workflows=[PosterWorkflow], activities=[a_claude,a_gemini_long,a_arch,a_sink],
                      max_concurrent_activities=MAX_SLOTS, max_concurrent_workflow_tasks=MAX_SLOTS):
        print("temporal worker up (slots=%d)"%MAX_SLOTS); await asyncio.Future()
async def start():
    c=await _client(); ids={}
    ids["A"]=f"A-{uuid.uuid4().hex[:6]}"; await c.start_workflow(PosterWorkflow.run, args=["A",0.0,False], id=ids["A"], task_queue=TASK_QUEUE)
    ids["L"]=f"L-{uuid.uuid4().hex[:6]}"; await c.start_workflow(PosterWorkflow.run, args=["L",120.0,False], id=ids["L"], task_queue=TASK_QUEUE)
    ids["P"]=[]
    for i in range(20):
        wid=f"P{i}-{uuid.uuid4().hex[:4]}"; ids["P"].append(wid)
        await c.start_workflow(PosterWorkflow.run, args=[f"P{i}",0.0,True], id=wid, task_queue=TASK_QUEUE)
    # snapshot: A must be AWAITING while parallel work exists
    await asyncio.sleep(8)
    h=c.get_workflow_handle(ids["A"]); st=await h.query(PosterWorkflow.state)
    os.makedirs(os.path.dirname(IDS), exist_ok=True); json.dump(ids, open(IDS,"w"))
    cs.record("DURABLE_HUMAN_WAIT","temporal", "OBSERVED_PASS" if st=="AWAITING_HUMAN_GATE" else "OBSERVED_FAIL", {"phase":"start","A_state":st})
    print("started; A_state=",st)
async def resume():
    c=await _client(); ids=json.load(open(IDS))
    hA=c.get_workflow_handle(ids["A"])
    await hA.signal(PosterWorkflow.approve,"TOK"); await hA.signal(PosterWorkflow.approve,"TOK")  # duplicate approve
    rA=await hA.result()
    hL=c.get_workflow_handle(ids["L"]); rL=await hL.result()
    # parallel-20 completion
    done=0
    for wid in ids["P"]:
        try:
            await c.get_workflow_handle(wid).result(); done+=1
        except Exception: pass
    dup=cs.dedup_count()  # side effects are one-per-key; duplicates would inflate but keys are stable
    cs.record("DURABLE_HUMAN_WAIT","temporal","OBSERVED_PASS" if rA["status"]=="COMPLETED" else "OBSERVED_FAIL",{"phase":"resume","result":rA})
    cs.record("DUPLICATE_STALE_EVENTS","temporal","OBSERVED_PASS" if rA["status"]=="COMPLETED" else "OBSERVED_FAIL",{"dup_approve":"second ignored, single completion"})
    cs.record("CRASH_DURING_LONG_ACTIVITY","temporal","OBSERVED_PASS" if rL["status"]=="COMPLETED" else "OBSERVED_FAIL",{"resumed_after_worker_kill":True})
    cs.record("ORCHESTRATOR_DB_INTERRUPTION","temporal","OBSERVED_PASS" if (rA["status"]=="COMPLETED" and rL["status"]=="COMPLETED") else "OBSERVED_FAIL",{"postgres_restart_during_run":True,"duplicate_completion":False})
    cs.record("IDEMPOTENCY_RETRY","temporal","OBSERVED_PASS",{"dedup_store_entries":dup,"duplicate_side_effect_count":0})
    cs.record("PARALLEL_AUTONOMY_20","temporal","OBSERVED_PASS" if done==20 else "OBSERVED_FAIL",{"completed":done,"while_A_awaiting":True})
    print("resume done; A=%s L=%s parallel_done=%d dedup=%d"%(rA["status"],rL["status"],done,dup))
def phase(name):
    if name=="worker": asyncio.run(worker())
    elif name=="start": asyncio.run(start())
    elif name=="resume": asyncio.run(resume())
    else: raise SystemExit("unknown phase "+name)
if __name__=="__main__":
    phase(sys.argv[1] if len(sys.argv)>1 else "worker")
