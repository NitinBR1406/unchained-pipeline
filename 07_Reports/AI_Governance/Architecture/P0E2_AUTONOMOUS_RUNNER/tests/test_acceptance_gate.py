"""Acceptance-SECURITY tests for the strict fail-closed reducer (acceptance_gate.verify).
Positive: fully-valid synthetic evidence => FINAL=PASS. Negatives: each flips ONE mandatory item and MUST
force FINAL=FAIL with the expected failed criterion. Deterministic; no live infra."""
import os, sys, json, tempfile, copy
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
sys.path.insert(0, os.path.join(ROOT,"..","P0E1_CONTROL_PLANE"))
import acceptance_gate as AG
from control_plane.ledger import EventLedger
from control_plane import events as E
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)
def build_valid():
    d=tempfile.mkdtemp()
    L=EventLedger(os.path.join(d,"EVENT_LEDGER.jsonl")); n=[0]
    def ev(et,**k):
        n[0]+=1; L.append(E.make_event("e%03d"%n[0],et,"2026-03-01T00:00:%02dZ"%(n[0]%60),"claude",**k))
    for t in ("TASK_A","TASK_B","TASK_D"):
        ev("TASK_STARTED",task_id=t); ev("TASK_RESULT",task_id=t,idempotency_key="k-"+t,evidence=["ev"])
    ev("HUMAN_GATE_REQUEST",task_id="TASK_C",gate="NITIN_PUBLISH_APPROVAL")
    ev("LEASE_ACQUIRED",task_id="STALE",lease_id="l1"); ev("LEASE_EXPIRED",task_id="STALE",lease_id="l1"); ev("LEASE_ACQUIRED",task_id="STALE",lease_id="l2")
    res={"final_task_status":{"TASK_A":"COMPLETED","TASK_B":"COMPLETED","TASK_C":"WAITING_FOR_NITIN","TASK_D":"COMPLETED"},
         "REAL_TEMPORAL_WORKFLOWS_OBSERVED":True,
         "workflow_ids":{"TASK_A":"p0e2-a","TASK_B":"p0e2-b","TASK_C":"p0e2-c","TASK_D":"p0e2-d"},
         "run_ids":{"TASK_A":"run-a","TASK_B":"run-b","TASK_D":"run-d"},
         "AUTONOMOUS_CHAIN_A_TO_B":"PASS","HUMAN_GATE_C_WAITING":"PASS","INDEPENDENT_D_CONTINUES":"PASS",
         "HUMAN_MESSAGE_RELAY_REQUIRED":False,"WAITING_WORKFLOW_BLOCKS_OTHER_WORK":False,
         "no_approval_fabricated":True,"DUPLICATE_SIDE_EFFECT_COUNT":0,"STALE_LEASE_RECLAIM":"PASS",
         "EVENT_LEDGER_CHAIN_VALID":True,"STATE_RECONSTRUCTION":"PASS"}
    json.dump(res, open(os.path.join(d,"P0E2_LIVE_RESULTS.json"),"w"))
    json.dump({b:True for b in AG.FI_BOOLS}, open(os.path.join(d,"failure_injection.json"),"w"))
    json.dump({"POC_INFRA_REMAINING":False}, open(os.path.join(d,"poc_infra.json"),"w"))
    json.dump({"tasks":[{"task_id":k,"status":v} for k,v in res["final_task_status"].items()]}, open(os.path.join(d,"BACKLOG_live.json"),"w"))
    return d
def R_(d): 
    with open(os.path.join(d,"P0E2_LIVE_RESULTS.json")) as f: return json.load(f)
def W_(d,r): json.dump(r, open(os.path.join(d,"P0E2_LIVE_RESULTS.json"),"w"))

# positive
d=build_valid(); v=AG.verify(d); ok("POSITIVE_valid_evidence_PASS", v["FINAL"]=="PASS" and v["failed_criteria"]==[])

def neg(name, mutate, expect_crit):
    d=build_valid(); mutate(d)
    v=AG.verify(d)
    ok(name, v["FINAL"]=="FAIL" and expect_crit in v["failed_criteria"])

neg("neg_real_workflows_false", lambda d: W_(d,{**R_(d),"REAL_TEMPORAL_WORKFLOWS_OBSERVED":False}), "REAL_TEMPORAL_WORKFLOWS_OBSERVED")
neg("neg_waiting_blocks_null", lambda d: W_(d,{**R_(d),"WAITING_WORKFLOW_BLOCKS_OTHER_WORK":None}), "WAITING_WORKFLOW_BLOCKS_OTHER_WORK_false")
neg("neg_workflow_ids_empty", lambda d: W_(d,{**R_(d),"workflow_ids":{}}), "workflow_ids_ABCD_nonempty")
neg("neg_missing_C_workflow_id", lambda d: W_(d,{**R_(d),"workflow_ids":{"TASK_A":"a","TASK_B":"b","TASK_D":"d"}}), "workflow_ids_ABCD_nonempty")
neg("neg_run_ids_empty", lambda d: W_(d,{**R_(d),"run_ids":{}}), "run_ids_executed_nonempty")
neg("neg_missing_failure_injection", lambda d: os.remove(os.path.join(d,"failure_injection.json")), "FI_worker_kill_observed")
neg("neg_postgres_restart_false", lambda d: json.dump({**{b:True for b in AG.FI_BOOLS},"postgres_restart_observed":False}, open(os.path.join(d,"failure_injection.json"),"w")), "FI_postgres_restart_observed")
neg("neg_temporal_recovery_false", lambda d: json.dump({**{b:True for b in AG.FI_BOOLS},"temporal_recovery_observed":False}, open(os.path.join(d,"failure_injection.json"),"w")), "FI_temporal_recovery_observed")
neg("neg_duplicate_side_effect", lambda d: W_(d,{**R_(d),"DUPLICATE_SIDE_EFFECT_COUNT":1}), "DUPLICATE_SIDE_EFFECT_COUNT_zero")
neg("neg_stale_lease_absent", lambda d: W_(d,{**R_(d),"STALE_LEASE_RECLAIM":"FAIL"}), "STALE_LEASE_RECLAIM")
def _tamper(d):
    p=os.path.join(d,"EVENT_LEDGER.jsonl"); ls=open(p).read().splitlines()
    r=json.loads(ls[1]); r["agent"]="tampered"; ls[1]=json.dumps(r); open(p,"w").write("\n".join(ls)+"\n")
neg("neg_broken_ledger_chain", _tamper, "EVENT_LEDGER_CHAIN_VALID")
neg("neg_state_reconstruction_mismatch", lambda d: W_(d,{**R_(d),"final_task_status":{**R_(d)["final_task_status"],"TASK_C":"COMPLETED"}}), "STATE_RECONSTRUCTION")
neg("neg_no_approval_fabricated_false", lambda d: W_(d,{**R_(d),"no_approval_fabricated":False}), "no_approval_fabricated")
neg("neg_missing_mandatory_key", lambda d: W_(d,{k:v for k,v in R_(d).items() if k!="REAL_TEMPORAL_WORKFLOWS_OBSERVED"}), "REAL_TEMPORAL_WORKFLOWS_OBSERVED")
neg("neg_poc_infra_remaining_true", lambda d: json.dump({"POC_INFRA_REMAINING":True}, open(os.path.join(d,"poc_infra.json"),"w")), "POC_INFRA_REMAINING_false")

print("\nAG_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
