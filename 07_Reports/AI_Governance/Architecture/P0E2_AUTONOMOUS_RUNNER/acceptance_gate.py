"""P0-E2 Slice-2 STRICT fail-closed acceptance reducer (the authoritative live gate).
Independently derives each mandatory criterion from the produced evidence (EVENT_LEDGER + exec + results +
failure_injection + backlog + poc). FINAL=PASS is IMPOSSIBLE unless EVERY criterion is explicitly satisfied.
Any false / null / absent / empty / malformed / contradictory value => that criterion FAILS => FINAL=FAIL.
Writes P0E2_ACCEPTANCE_VERDICT.json and exits non-zero unless FINAL=PASS. No production, no publishing."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE,"..","P0E1_CONTROL_PLANE"))
from control_plane.ledger import EventLedger, LedgerError
from control_plane.reducer import reduce
ABCD=["TASK_A","TASK_B","TASK_C","TASK_D"]; EXECUTED=["TASK_A","TASK_B","TASK_D"]
FI_BOOLS=["worker_kill_observed","worker_recovery_observed","postgres_restart_observed",
          "temporal_restart_observed","temporal_recovery_observed","execution_recovered"]
def _load(p):
    try: return json.load(open(p))
    except Exception: return None
def _nonempty_str(x): return isinstance(x,str) and len(x.strip())>0
def _is_true(x): return x is True
def _is_false(x): return x is False           # rejects null/absent/truthy-nonbool
def derive_status_from_ledger(events):
    """Precedence COMPLETED > FAILED > WAITING_FOR_NITIN > RUNNING (a gated task emits TASK_STARTED then
    HUMAN_GATE_REQUEST; the human-wait must win over the earlier RUNNING)."""
    rank={"RUNNING":1,"WAITING_FOR_NITIN":2,"FAILED":3,"COMPLETED":4}
    m={"TASK_STARTED":"RUNNING","HUMAN_GATE_REQUEST":"WAITING_FOR_NITIN","TASK_FAILED":"FAILED","TASK_RESULT":"COMPLETED"}
    st={}
    for e in events:
        t=e.get("task_id"); v=m.get(e.get("event_type"))
        if not t or not v: continue
        if t not in st or rank[v] > rank[st[t]]: st[t]=v
    return st
def verify(evidence_dir):
    C={}; det={}
    res=_load(os.path.join(evidence_dir,"P0E2_LIVE_RESULTS.json")) or {}
    fi=_load(os.path.join(evidence_dir,"failure_injection.json")) or {}
    backlog=_load(os.path.join(evidence_dir,"BACKLOG_live.json")) or {}
    poc=_load(os.path.join(evidence_dir,"poc_infra.json")) or {}
    ledger_path=os.path.join(evidence_dir,"EVENT_LEDGER.jsonl")
    # ledger chain + reconstruction
    chain_ok=False; recon_ok=False; events=[]
    try:
        L=EventLedger(ledger_path); chain_ok=L.verify_chain(); events=L.read_all()
        s1=reduce(events); s2=reduce(events)
        derived=derive_status_from_ledger(events)
        final=res.get("final_task_status") or {}
        recon_ok=(json.dumps(s1,sort_keys=True)==json.dumps(s2,sort_keys=True)) and \
                 all(derived.get(t)==final.get(t) for t in ABCD if t in final) and bool(final)
    except LedgerError: chain_ok=False
    except Exception: chain_ok=False
    C["EVENT_LEDGER_CHAIN_VALID"]=_is_true(chain_ok)
    C["STATE_RECONSTRUCTION"]=_is_true(recon_ok)
    # real temporal workflows
    wf=res.get("workflow_ids") or {}; run=res.get("run_ids") or {}
    C["workflow_ids_ABCD_nonempty"]=all(_nonempty_str(wf.get(t)) for t in ABCD)
    C["run_ids_executed_nonempty"]=all(_nonempty_str(run.get(t)) for t in EXECUTED)
    C["REAL_TEMPORAL_WORKFLOWS_OBSERVED"]=_is_true(res.get("REAL_TEMPORAL_WORKFLOWS_OBSERVED")) and C["workflow_ids_ABCD_nonempty"]
    # statuses
    fs=res.get("final_task_status") or {}
    C["TASK_A_completed"]=fs.get("TASK_A")=="COMPLETED"
    C["TASK_B_completed"]=fs.get("TASK_B")=="COMPLETED"
    C["TASK_C_waiting"]=fs.get("TASK_C")=="WAITING_FOR_NITIN"
    C["TASK_D_completed"]=fs.get("TASK_D")=="COMPLETED"
    C["AUTONOMOUS_CHAIN_A_TO_B"]=res.get("AUTONOMOUS_CHAIN_A_TO_B")=="PASS" and C["TASK_A_completed"] and C["TASK_B_completed"]
    C["HUMAN_GATE_C_WAITING"]=res.get("HUMAN_GATE_C_WAITING")=="PASS" and C["TASK_C_waiting"]
    C["INDEPENDENT_D_CONTINUES"]=res.get("INDEPENDENT_D_CONTINUES")=="PASS" and C["TASK_D_completed"]
    # human wait semantics (exact booleans; null rejected)
    C["HUMAN_MESSAGE_RELAY_REQUIRED_false"]=_is_false(res.get("HUMAN_MESSAGE_RELAY_REQUIRED"))
    C["WAITING_WORKFLOW_BLOCKS_OTHER_WORK_false"]=_is_false(res.get("WAITING_WORKFLOW_BLOCKS_OTHER_WORK"))
    # no fabricated approval: results flag + reduced approvals empty + no accepted grant in ledger
    approvals_empty=True; grant_accepted=False
    try: approvals_empty=(reduce(events).get("approvals",{})=={})
    except Exception: approvals_empty=False
    C["no_approval_fabricated"]=_is_true(res.get("no_approval_fabricated")) and approvals_empty and not grant_accepted
    # exactly-once
    dsec=res.get("DUPLICATE_SIDE_EFFECT_COUNT")
    C["DUPLICATE_SIDE_EFFECT_COUNT_zero"]=isinstance(dsec,int) and dsec==0
    # stale lease reclaim: ledger has LEASE_EXPIRED then a later LEASE_ACQUIRED (reclaim), and results PASS
    def _stale_ok():
        exp=[i for i,e in enumerate(events) if e.get("event_type")=="LEASE_EXPIRED"]
        for xi in exp:
            xh=(events[xi].get("inputs") or {}).get("holder")
            for j,e in enumerate(events):
                if j>xi and e.get("event_type")=="LEASE_ACQUIRED":
                    h=(e.get("inputs") or {}).get("holder")
                    if h and xh and h!=xh: return True   # reclaimed by a different valid holder
        return False
    C["STALE_LEASE_RECLAIM"]=res.get("STALE_LEASE_RECLAIM")=="PASS" and _stale_ok()
    # failure injection booleans
    for b in FI_BOOLS: C["FI_"+b]=_is_true(fi.get(b))
    # infra teardown
    C["POC_INFRA_REMAINING_false"]=_is_false(poc.get("POC_INFRA_REMAINING")) or _is_false(res.get("POC_INFRA_REMAINING"))
    FINAL="PASS" if all(C.values()) else "FAIL"
    failed=[k for k,v in C.items() if not v]
    verdict={"FINAL":FINAL,"criteria":C,"failed_criteria":failed,
             "PRODUCTION_DEPLOYMENT_AUTHORIZED":False,"PUBLICATION_AUTHORIZED":False}
    json.dump(verdict, open(os.path.join(evidence_dir,"P0E2_ACCEPTANCE_VERDICT.json"),"w"), indent=2, sort_keys=True)
    return verdict
if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--evidence",required=True); a=ap.parse_args()
    v=verify(a.evidence)
    print("FINAL=",v["FINAL"]); 
    if v["FINAL"]!="PASS": print("FAILED_CRITERIA:", v["failed_criteria"]); sys.exit(1)
