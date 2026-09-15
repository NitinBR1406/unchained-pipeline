"""P0-E2 Control Room V01 — READ-ONLY view over canonical EVENT_LEDGER + reduced MASTER STATE + backlog.
It is NOT a truth store: it derives everything from the ledger/state/backlog and writes only a rendered
view (JSON + static HTML). No canonical mutation."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
from control_plane.backlog import summary
def build(ledger_path, backlog_path, keyring=None, last24_stats=None):
    events=EventLedger(ledger_path).read_all()
    state=reduce(events, keyring=keyring or {"keys":{},"revoked":[]})
    tasks=json.load(open(backlog_path))["tasks"]
    by_status={}
    for t in tasks: by_status.setdefault(t["status"],[]).append(t["task_id"])
    completed=[e for e in events if e.get("event_type")=="TASK_RESULT"]
    last_completed=completed[-1]["task_id"] if completed else None
    ready=[t["task_id"] for t in tasks if t["status"]=="READY"]
    running=by_status.get("RUNNING",[])
    view={
      "title":"UNCHAINED NITIN — CONTROL ROOM",
      "read_only":True,
      "system_health":{"P0E1_FOUNDATION":"GREEN (VERIFIED)","AUTONOMOUS_ENGINEERING":"ACTIVE",
                       "temporal_control_plane":state["architecture_locks"].get("temporal_control_plane"),
                       "production_deployment_authorized":state["architecture_locks"].get("production_deployment_authorized")},
      "queues":{"READY":ready,"RUNNING":running,"WAITING_FOR_NITIN":by_status.get("WAITING_FOR_NITIN",[]),
                "BLOCKED":by_status.get("BLOCKED",[]),"COMPLETED":by_status.get("COMPLETED",[])},
      "current_executor_task":state["autonomous_execution"].get("current_task"),
      "last_completed_task":last_completed,
      "next_ready_task":(ready[0] if ready else None),
      "runner_health":{"last_heartbeat":state.get("updated_at"),
                       "active_leases":[e["task_id"] for e in events if e.get("event_type")=="LEASE_ACQUIRED"
                                        and not any(x.get("event_type") in ("LEASE_RELEASED","LEASE_EXPIRED") and x.get("task_id")==e["task_id"] for x in events)],
                       "stale_leases":[e["task_id"] for e in events if e.get("event_type")=="LEASE_EXPIRED"]},
      "last_24h": last24_stats or {"tasks_completed":len(completed),"tests_passed":None,"failures":None,
                       "unauthorized_actions":len([r for r in state.get("_rejected_events",[]) if "human_gate" in r.get("reason","")])},
      "invariants":state["invariants"],
      "waiting_for_nitin":state["autonomous_execution"].get("waiting_for_nitin",[]),
      "next_nitin_action":("Provision Nitin Ed25519 PUBLIC key + grant "+",".join(w.get("gate","") for w in state["autonomous_execution"].get("waiting_for_nitin",[])) if state["autonomous_execution"].get("waiting_for_nitin") else "NONE"),
    }
    return view
def render_html(v):
    def li(xs): return "".join("<li>%s</li>"%x for x in xs) or "<li><em>none</em></li>"
    q=v["queues"]
    return ("<!doctype html><meta charset=utf-8><title>%s</title>"
            "<style>body{font:14px system-ui;margin:24px;color:#1a1a1a}h1{font-size:20px}"
            "h2{font-size:14px;text-transform:uppercase;color:#666;margin-top:20px}"
            ".g{color:#137333}.w{color:#b06000}.r{color:#a50e0e}code{background:#f1f1f1;padding:1px 4px}</style>"
            "<h1>%s</h1><p class=g>READ-ONLY VIEW · derived from EVENT_LEDGER + MASTER STATE</p>"
            "<h2>System health</h2><div>P0-E1 FOUNDATION: <b class=g>%s</b> · Autonomous engineering: <b>%s</b> · "
            "Temporal control plane: <b>%s</b> · Production deploy authorized: <b class=r>%s</b></div>"
            "<h2>Ready</h2><ul>%s</ul><h2>Running</h2><ul>%s</ul><h2>Waiting for Nitin</h2><ul class=w>%s</ul>"
            "<h2>Blocked</h2><ul>%s</ul><h2>Completed</h2><ul class=g>%s</ul>"
            "<h2>Executor</h2><div>Current: <code>%s</code> · Last completed: <code>%s</code> · Next ready: <code>%s</code></div>"
            "<h2>Runner health</h2><div>Last heartbeat: %s · Active leases: %s · Stale leases: %s</div>"
            "<h2>Last 24h</h2><div>Tasks completed: %s · Tests passed: %s · Failures: %s · Unauthorized actions: %s</div>"
            "<h2>Invariants</h2><pre>%s</pre><h2>Next Nitin action</h2><div class=w>%s</div>"
            ) % (v["title"], v["title"], v["system_health"]["P0E1_FOUNDATION"], v["system_health"]["AUTONOMOUS_ENGINEERING"],
                 v["system_health"]["temporal_control_plane"], v["system_health"]["production_deployment_authorized"],
                 li(q["READY"]), li(q["RUNNING"]), li(q["WAITING_FOR_NITIN"]), li(q["BLOCKED"]), li(q["COMPLETED"]),
                 v["current_executor_task"], v["last_completed_task"], v["next_ready_task"],
                 v["runner_health"]["last_heartbeat"], v["runner_health"]["active_leases"] or "none", v["runner_health"]["stale_leases"] or "none",
                 v["last_24h"]["tasks_completed"], v["last_24h"]["tests_passed"], v["last_24h"]["failures"], v["last_24h"]["unauthorized_actions"],
                 json.dumps(v["invariants"],indent=2), v["next_nitin_action"])
if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",required=True); ap.add_argument("--backlog",required=True)
    ap.add_argument("--out-json"); ap.add_argument("--out-html"); a=ap.parse_args()
    v=build(a.ledger,a.backlog)
    if a.out_json: open(a.out_json,"w").write(json.dumps(v,indent=2,sort_keys=True))
    if a.out_html: open(a.out_html,"w").write(render_html(v))
    print(json.dumps({k:v[k] for k in ("queues","current_executor_task","last_completed_task","next_ready_task","next_nitin_action")},indent=2))
