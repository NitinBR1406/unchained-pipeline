"""OFFLINE adapter test for P0-E2 Slice-2 LiveRunner using a FAKE Temporal client. Proves the ORCHESTRATION
logic only (dispatch/lifecycle/dedup/gate). It does NOT prove live Temporal — that requires GitHub
(p0e2-autonomous-live.yml). Never interpret this as LIVE_TEMPORAL_AUTONOMOUS_RUNNER=OBSERVED_PASS."""
import os, sys, json, tempfile, shutil, asyncio
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
sys.path.insert(0, os.path.join(ROOT,"..","P0E1_CONTROL_PLANE"))
from temporal_runner import LiveRunner
SEED=os.path.join(ROOT,"seed","backlog_slice1.json")
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)

class FakeHandle:
    def __init__(self,payload): self.payload=payload
    async def result(self): return {"task_id":self.payload["task_id"],"status":"COMPLETED"}
class FakeClient:
    def __init__(self): self.started={}; self.signals=[]
    async def start_workflow(self, run_ref, payload, id=None, task_queue=None, **k):
        if id in self.started: return self.started[id]      # deterministic id => dedup (reuse existing)
        h=FakeHandle(payload); self.started[id]=h; return h
    async def signal(self,*a,**k): self.signals.append((a,k))   # should never be called for C

def fresh():
    d=tempfile.mkdtemp(); bl=os.path.join(d,"BACKLOG.json"); shutil.copy(SEED,bl)
    fc=FakeClient()
    async def factory(): return fc
    return LiveRunner(bl, os.path.join(d,"LEDGER.jsonl"), os.path.join(d,"evidence"), client_factory=factory), fc

r,fc=fresh(); st=asyncio.run(r.run_live())
status={t["task_id"]:t["status"] for t in r._tasklist()}
ok("A_completed", status["TASK_A"]=="COMPLETED")
ok("B_completed_after_A", status["TASK_B"]=="COMPLETED")
ok("C_waiting_for_nitin", status["TASK_C"]=="WAITING_FOR_NITIN")
ok("D_completed_while_C_waits", status["TASK_D"]=="COMPLETED")
ok("C_never_signalled_no_fabricated_approval", fc.signals==[] and "NITIN_PUBLISH_APPROVAL" not in st.get("approvals",{}))
ok("real_workflow_dispatch_recorded", set(r.dispatched.keys())>={"TASK_A","TASK_B","TASK_C","TASK_D"})
ok("deterministic_unique_workflow_ids", len(set(r.dispatched.values()))==len(r.dispatched))
ok("waiting_not_blocking", status["TASK_B"]=="COMPLETED" and status["TASK_D"]=="COMPLETED")
# duplicate dispatch of A reuses the same deterministic workflow id (no second workflow)
before=dict(fc.started)
asyncio.run(r.dispatch(fc, r.tasks["TASK_A"]))
ok("duplicate_dispatch_same_wf_id", set(fc.started.keys())==set(before.keys()))
# gate
out,okg=r.gate()
ok("runner_sanity_ok_when_ABCD_correct", okg and out["HUMAN_GATE_C_WAITING"]=="PASS" and out["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"] is False)
ok("gate_reports_no_fabricated_approval", out["no_approval_fabricated"] is True)
# gate fail-closed if C got (wrongly) completed
r.tasks["TASK_C"]["status"]="COMPLETED"; out2,okg2=r.gate()
ok("runner_sanity_incomplete_if_C_not_waiting", not okg2)

print("\nS2OFF_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
