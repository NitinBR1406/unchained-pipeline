"""Rerun-3 closure: reproduces the 5 live failures and proves the producer/consumer fix end-to-end.
- workflow_ids/run_ids/REAL now aggregate from PERSISTED evidence across a separate gate process.
- STALE_LEASE_RECLAIM derives from the ledger (different-holder reclaim).
- STATE_RECONSTRUCTION derives with correct precedence (gated C: TASK_STARTED then HUMAN_GATE_REQUEST => WAITING).
Deterministic; fake Temporal client (handles expose first_execution_run_id). No live infra."""
import os, sys, json, tempfile, shutil, asyncio
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
sys.path.insert(0, os.path.join(ROOT,"..","P0E1_CONTROL_PLANE"))
from temporal_runner import LiveRunner
import acceptance_gate as AG
SEED=os.path.join(ROOT,"seed","backlog_slice2.json")
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)
class FakeHandle:
    def __init__(self,pl): self.payload=pl; self.first_execution_run_id="run-"+pl["task_id"]
    async def result(self): return {"task_id":self.payload["task_id"],"status":"COMPLETED"}
class FakeClient:
    def __init__(self): self.started={}
    async def start_workflow(self, run_ref, payload, id=None, task_queue=None, **k):
        if id in self.started: return self.started[id]
        h=FakeHandle(payload); self.started[id]=h; return h

d=tempfile.mkdtemp(); bl=os.path.join(d,"BACKLOG.json"); shutil.copy(SEED,bl); ev=os.path.join(d,"evidence"); os.makedirs(ev)
async def factory(): return FakeClient()
r=LiveRunner(bl, os.path.join(ev,"EVENT_LEDGER.jsonl"), ev, client_factory=factory)
asyncio.run(r.run_live())
ok("persisted_dispatched_json", os.path.exists(os.path.join(ev,"dispatched.json")))
ok("exec_files_present", all(os.path.exists(os.path.join(ev,"exec_%s.json"%t)) for t in ("TASK_A","TASK_B","TASK_D")))

# SEPARATE gate process (fresh instance, no in-memory dispatched) reads persisted evidence
r2=LiveRunner(bl, os.path.join(ev,"EVENT_LEDGER.jsonl"), ev)
out,_=r2.gate()
ok("R1_workflow_ids_ABCD_nonempty", all(out["workflow_ids"].get(t) for t in ("TASK_A","TASK_B","TASK_C","TASK_D")))
ok("R1_run_ids_executed_nonempty", all(out["run_ids"].get(t) for t in ("TASK_A","TASK_B","TASK_D")))
ok("R1_REAL_TEMPORAL_WORKFLOWS_OBSERVED_true", out["REAL_TEMPORAL_WORKFLOWS_OBSERVED"] is True)
ok("R1_STALE_LEASE_RECLAIM_pass", out["STALE_LEASE_RECLAIM"]=="PASS")
ok("R1_STATE_RECONSTRUCTION_pass", out["STATE_RECONSTRUCTION"]=="PASS")
ok("R1_waiting_blocks_false_not_null", out["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"] is False)

# end-to-end: synthesize valid failure-injection + poc, run STRICT acceptance -> FINAL PASS
json.dump({b:True for b in AG.FI_BOOLS}, open(os.path.join(ev,"failure_injection.json"),"w"))
json.dump({"POC_INFRA_REMAINING":False}, open(os.path.join(ev,"poc_infra.json"),"w"))
json.dump({"tasks":[{"task_id":k,"status":v} for k,v in out["final_task_status"].items()]}, open(os.path.join(ev,"BACKLOG_live.json"),"w"))
v=AG.verify(ev)
ok("END_TO_END_FINAL_PASS", v["FINAL"]=="PASS" and v["failed_criteria"]==[])
import control_room_v02 as CR
cr=CR.build_v02(os.path.join(ev,"EVENT_LEDGER.jsonl"), os.path.join(ev,"BACKLOG_live.json"))
ok("control_room_stale_reclaim_pass", cr["RUNNER_HEALTH"]["STALE_LEASE_RECLAIM"]=="PASS")

# reproduce the OLD producer bug: remove persisted id evidence -> ids empty -> acceptance FAIL (fix is load-bearing)
d2=tempfile.mkdtemp(); ev2=os.path.join(d2,"evidence"); os.makedirs(ev2)
shutil.copy(os.path.join(ev,"EVENT_LEDGER.jsonl"), os.path.join(ev2,"EVENT_LEDGER.jsonl"))
shutil.copy(os.path.join(ev,"failure_injection.json"), os.path.join(ev2,"failure_injection.json"))
shutil.copy(os.path.join(ev,"poc_infra.json"), os.path.join(ev2,"poc_infra.json"))
shutil.copy(os.path.join(ev,"BACKLOG_live.json"), os.path.join(ev2,"BACKLOG_live.json"))
json.dump({**out,"workflow_ids":{},"run_ids":{},"REAL_TEMPORAL_WORKFLOWS_OBSERVED":False}, open(os.path.join(ev2,"P0E2_LIVE_RESULTS.json"),"w"))
v2=AG.verify(ev2)
ok("OLD_BUG_empty_ids_FAILS", v2["FINAL"]=="FAIL" and "REAL_TEMPORAL_WORKFLOWS_OBSERVED" in v2["failed_criteria"] and "workflow_ids_ABCD_nonempty" in v2["failed_criteria"])

print("\nR3_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
