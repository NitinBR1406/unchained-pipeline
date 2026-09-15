"""Control Room V02 — READ-ONLY, extends V01 with LIVE Temporal + runner runtime fields derived from the
canonical EVENT_LEDGER + reduced MASTER STATE + backlog + (optional) live results. No new truth store."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE,"..","P0E1_CONTROL_PLANE"))
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
def build_v02(ledger_path, backlog_path, live_results_path=None, temporal_health=None, tests=None, keyring=None):
    events=EventLedger(ledger_path).read_all(); state=reduce(events, keyring=keyring or {"keys":{},"revoked":[]})
    tasks=json.load(open(backlog_path))["tasks"]; bys={}
    for t in tasks: bys.setdefault(t["status"],[]).append(t["task_id"])
    results=json.load(open(live_results_path)) if (live_results_path and os.path.exists(live_results_path)) else {}
    def evs(et): return [e for e in events if e.get("event_type")==et]
    active=[e["task_id"] for e in evs("LEASE_ACQUIRED") if not any(x.get("task_id")==e["task_id"] and x.get("event_type") in ("LEASE_RELEASED","LEASE_EXPIRED") for x in events)]
    wf=[e.get("inputs",{}).get("workflow_id") for e in evs("TASK_RESULT") if e.get("inputs",{}).get("workflow_id")]
    return {
      "title":"UNCHAINED NITIN — CONTROL ROOM V02","read_only":True,
      "SYSTEM_HEALTH":{"P0E1_FOUNDATION":"GREEN (VERIFIED)","AUTONOMOUS_ENGINEERING":"ACTIVE",
                       "PRODUCTION_DEPLOYMENT_AUTHORIZED":state["architecture_locks"].get("production_deployment_authorized")},
      "TEMPORAL_HEALTH":temporal_health or {"status":"see live run","control_plane":state["architecture_locks"].get("temporal_control_plane")},
      "RUNNER_HEALTH":{"LAST_HEARTBEAT":state.get("updated_at"),"ACTIVE_LEASES":active,
                       "STALE_LEASES":[e["task_id"] for e in evs("LEASE_EXPIRED")],
                       "LAST_TEMPORAL_WORKFLOW": wf[-1] if wf else None,
                       "LAST_RECOVERY_EVENT": (evs("LEASE_EXPIRED")[-1]["task_id"] if evs("LEASE_EXPIRED") else None)},
      "QUEUES":{k:bys.get(k,[]) for k in ("READY","CLAIMED","RUNNING","VERIFYING","WAITING_FOR_NITIN","BLOCKED","COMPLETED")},
      "CURRENT_EXECUTOR_TASK":state["autonomous_execution"].get("current_task"),
      "LAST_COMPLETED_TASK": (evs("TASK_RESULT")[-1]["task_id"] if evs("TASK_RESULT") else None),
      "NEXT_READY_TASK": (bys.get("READY",[None])[0] if bys.get("READY") else None),
      "LAST_24H":{"TASKS_COMPLETED":len(evs("TASK_RESULT")),"TESTS_PASSED":(tests or {}).get("passed"),
                  "FAILURES":(tests or {}).get("failed"),
                  "UNAUTHORIZED_ACTIONS":len([r for r in state.get("_rejected_events",[]) if "human_gate" in r.get("reason","")])},
      "LIVE_RESULTS": results or None,
      "NEXT_NITIN_ACTION": ("Provision Nitin Ed25519 PUBLIC key + grant "+",".join(w.get("gate","") for w in state["autonomous_execution"].get("waiting_for_nitin",[])) if state["autonomous_execution"].get("waiting_for_nitin") else "NONE"),
    }
if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",required=True); ap.add_argument("--backlog",required=True)
    ap.add_argument("--live-results"); ap.add_argument("--out-json"); a=ap.parse_args()
    v=build_v02(a.ledger,a.backlog,a.live_results)
    if a.out_json: open(a.out_json,"w").write(json.dumps(v,indent=2,sort_keys=True))
    print(json.dumps({k:v[k] for k in ("QUEUES","CURRENT_EXECUTOR_TASK","LAST_COMPLETED_TASK","NEXT_NITIN_ACTION")},indent=2))
