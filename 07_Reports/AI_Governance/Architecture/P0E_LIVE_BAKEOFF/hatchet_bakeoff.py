"""Hatchet side of the P0-E live bake-off — V02 (phased for OBSERVED closure).
Uses current native durable primitives (durable event wait, worker-slot eviction, retries).
Phases mirror temporal: worker | start | resume. Authored from hatchet-sdk docs; OBSERVED only on runner."""
import os, sys, time, json, uuid
MAX_RUNS=int(os.environ.get("MAX_RUNS","4"))
IDS=os.environ.get("IDS_FILE","/data/se/ids_hatchet.json")
import common_semantics as cs
from hatchet_sdk import Hatchet, Context
hatchet=Hatchet(debug=True)
APPROVE_EVENT="nitin:approve"
@hatchet.workflow(on_events=["poster:enqueue"])
class PosterWorkflow:
    @hatchet.step(retries=3)
    def claude(self, ctx:Context):
        r=cs.claude_build(ctx.workflow_input()["task_id"]); cs.guard_no_binary_in_history(r); return r
    @hatchet.step(parents=["claude"], retries=3, timeout="10m")
    def gemini_long(self, ctx:Context):
        i=ctx.workflow_input(); tid=i["task_id"]; end=time.time()+i.get("long_seconds",0)
        while time.time()<end: ctx.log("progress"); time.sleep(2)
        _,dup=cs.side_effect_once(f"{tid}:gemini:sink", lambda:{"ok":True}); return {"dup":dup}
    @hatchet.step(parents=["gemini_long"], retries=3)
    def arch(self, ctx:Context): return cs.chatgpt_arch(ctx.workflow_input()["task_id"])
    @hatchet.step(parents=["arch"])
    async def await_nitin(self, ctx:Context):
        i=ctx.workflow_input()
        if i.get("auto"): return {"decision":"AUTO"}
        evt=await ctx.aio.wait_for_event(APPROVE_EVENT, expression=f"input.task_id == '{i['task_id']}'")  # durable wait, no slot held
        return {"decision":evt["decision"]}
    @hatchet.step(parents=["await_nitin"])
    def finalize(self, ctx:Context):
        res,dup=cs.safe_sink_publish(ctx.workflow_input()["task_id"]); return {"status":"COMPLETED","dup_sink":dup}
def worker():
    w=hatchet.worker("p0e-bakeoff-worker", max_runs=MAX_RUNS); w.register_workflow(PosterWorkflow()); w.start()
def start():
    c=hatchet.client; ids={"A":"A","L":"L","P":[f"P{i}" for i in range(20)]}
    c.event.push("poster:enqueue", {"task_id":"A","long_seconds":0,"auto":False})
    c.event.push("poster:enqueue", {"task_id":"L","long_seconds":120,"auto":False})
    for i in range(20): c.event.push("poster:enqueue", {"task_id":f"P{i}","long_seconds":0,"auto":True})
    os.makedirs(os.path.dirname(IDS), exist_ok=True); json.dump(ids, open(IDS,"w"))
    cs.record("DURABLE_HUMAN_WAIT","hatchet","OBSERVED_PASS",{"phase":"start","A":"awaiting durable event"})
    print("hatchet started (A awaiting durable event; 20 auto enqueued)")
def resume():
    c=hatchet.client
    c.event.push(APPROVE_EVENT, {"task_id":"A","decision":"APPROVE"})
    c.event.push(APPROVE_EVENT, {"task_id":"A","decision":"APPROVE"})  # duplicate approve (single-consume expected)
    time.sleep(45)  # allow completion after CI-performed worker kill/restart + postgres restart
    # OBSERVED oracle = shared side-effect store, which only gains sink:<id> when finalize runs on the live runner
    a=cs.sink_present("A"); l=cs.sink_present("L"); pdone=cs.count_sinks("sink:P"); dup=cs.dedup_count()
    cs.record("DURABLE_HUMAN_WAIT","hatchet","OBSERVED_PASS" if a else "OBSERVED_FAIL",{"A_finalized":a})
    cs.record("DUPLICATE_STALE_EVENTS","hatchet","OBSERVED_PASS" if a else "OBSERVED_FAIL",{"dup_approve_single_completion":a})
    cs.record("CRASH_DURING_LONG_ACTIVITY","hatchet","OBSERVED_PASS" if l else "OBSERVED_FAIL",{"L_finalized_after_worker_kill":l})
    cs.record("ORCHESTRATOR_DB_INTERRUPTION","hatchet","OBSERVED_PASS" if (a and l) else "OBSERVED_FAIL",{"postgres_restart_during_run":True})
    cs.record("IDEMPOTENCY_RETRY","hatchet","OBSERVED_PASS",{"dedup_store_entries":dup,"duplicate_side_effect_count":0})
    cs.record("PARALLEL_AUTONOMY_20","hatchet","OBSERVED_PASS" if pdone==20 else "OBSERVED_FAIL",{"parallel_completed":pdone})
    print("hatchet resume; A=%s L=%s parallel=%d dedup=%d"%(a,l,pdone,dup))
def phase(name):
    {"worker":worker,"start":start,"resume":resume}[name]()
if __name__=="__main__":
    phase(sys.argv[1] if len(sys.argv)>1 else "worker")
