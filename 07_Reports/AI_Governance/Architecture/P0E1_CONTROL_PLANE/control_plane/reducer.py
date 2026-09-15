"""Deterministic State Reducer: ordered events -> Master State.
Pure function of the event stream: no wall clock, no randomness. Replayable + idempotent + fail-closed.
Human gates grant ONLY when agent=='nitin'. Idempotency prevents duplicate side effects."""
from .events import SCHEMA_VERSION, AUTHORITATIVE, is_wellformed, HUMAN_GATES
class ReducerError(Exception): pass
MASTER_SCHEMA_VERSION = 1
def _empty_state():
    return {
      "schema_version":MASTER_SCHEMA_VERSION,"state_version":0,"updated_at":None,"updated_by":None,
      "project":"UNCHAINED NITIN — MASTER","phase":"P0-E1","milestone":"TEMPORAL CONTROL PLANE FOUNDATION",
      "production_state":{"p1_scenario":"9627055","first_real_poster":"PAUSED_BY_NITIN","mutated":False},
      "scenario_ids":{},"datastore_ids":{},
      "git":{"repository":None,"branch":None,"commit_sha":None},
      "deployments":[],
      "architecture_locks":{"selected_control_plane":None,"architecture_bakeoff":None,"winner":None,
                            "production_deployment_authorized":False,"adr_ref":None},
      "approvals":{},"grants":{},
      "proven_tests":[],
      "issue_classes":{"must_fix":[],"material":[],"nice_to_have":[]},
      "current_release":None,"current_content":None,
      "autonomous_execution":{"current_task":None,"active_tasks":[],"waiting_for_nitin":[]},
      "backlog_summary":{"ready":0,"running":0,"blocked":0,"waiting_for_nitin":0,"completed":0},
      "runner_health":{},"evidence_refs":[],"provenance":[],
      "invariants":{"WAITING_WORKFLOW_BLOCKS_OTHER_WORK":None,"WORKER_SLOT_HELD_DURING_HUMAN_WAIT":None,
                    "STATE_RECOVERED_AFTER_RESTART":None,"DUPLICATE_SIDE_EFFECT_COUNT":0,
                    "HUMAN_MESSAGE_RELAY_REQUIRED":False},
      "duplicate_side_effect_count":0,
      "_applied_idempotency_keys":[], "_rejected_events":[],
    }
def _validate_auth(e):
    if not is_wellformed(e): raise ReducerError("malformed authoritative event (fail-closed)")
    if e["schema_version"]!=SCHEMA_VERSION: raise ReducerError("unknown schema_version %r (fail-closed)"%e.get("schema_version"))
def reduce(events, state=None):
    s = state or _empty_state()
    tasks = { }  # task_id -> status (local view for order/idempotency checks)
    for t in s["autonomous_execution"]["active_tasks"]: tasks[t]="RUNNING"
    for e in events:
        et = e.get("event_type")
        if et in AUTHORITATIVE:
            _validate_auth(e)  # fail-closed: raises on malformed / unknown schema
        else:
            if not is_wellformed(e):  # non-authoritative but junk -> ignore safely
                s["_rejected_events"].append({"reason":"malformed_nonauth","event_id":e.get("event_id")}); continue
        applied = _apply(s, e, tasks)
        if applied:
            s["state_version"] += 1
            s["updated_at"] = e["timestamp"]; s["updated_by"] = e["agent"]
    return s
def _apply(s, e, tasks):
    et=e["event_type"]; tid=e.get("task_id")
    if et=="ARCH_DECISION":
        d=e.get("decision") or {}
        s["architecture_locks"].update({
            "selected_control_plane":d.get("selected_control_plane"),
            "architecture_bakeoff":d.get("architecture_bakeoff"),
            "winner":d.get("winner"),
            "production_deployment_authorized":bool(d.get("production_deployment_authorized",False)),
            "adr_ref":d.get("adr_ref")})
        s["provenance"].append({"arch_decision":e.get("event_id"),"ts":e["timestamp"]}); return True
    if et=="HUMAN_GATE_REQUEST":
        s["autonomous_execution"]["waiting_for_nitin"].append({"task_id":tid,"gate":e.get("gate")}); return True
    if et=="HUMAN_GATE_GRANTED":
        gate=e.get("gate")
        if e.get("agent")!="nitin" or gate not in HUMAN_GATES:
            # FAIL-CLOSED: no AI may create/infer/impersonate a Nitin gate
            s["_rejected_events"].append({"reason":"unauthorized_human_gate","event_id":e.get("event_id"),
                                          "agent":e.get("agent"),"gate":gate}); return False
        s["approvals"][gate]={"task_id":tid,"granted_by":"nitin","ts":e["timestamp"]}
        s["autonomous_execution"]["waiting_for_nitin"]=[w for w in s["autonomous_execution"]["waiting_for_nitin"]
                                                        if not (w.get("task_id")==tid and w.get("gate")==gate)]
        return True
    if et=="HUMAN_GATE_REJECTED":
        s["approvals"].pop(e.get("gate"),None); return True
    if et=="LEASE_ACQUIRED":
        tasks[tid]="CLAIMED"; return True
    if et in ("LEASE_EXPIRED","LEASE_RELEASED"):
        if tasks.get(tid) in ("CLAIMED","RUNNING"): tasks[tid]="READY"; return True
        return True
    if et=="TASK_STARTED":
        tasks[tid]="RUNNING"
        if tid not in s["autonomous_execution"]["active_tasks"]: s["autonomous_execution"]["active_tasks"].append(tid)
        s["autonomous_execution"]["current_task"]=tid; return True
    if et in ("TASK_RESULT","TASK_FAILED"):
        # ORDER-SENSITIVE: a result before the task ran is out-of-order -> fail-closed reject
        if tasks.get(tid) not in ("RUNNING","CLAIMED"):
            s["_rejected_events"].append({"reason":"out_of_order_result","event_id":e.get("event_id"),"task_id":tid}); return False
        key=e.get("idempotency_key")
        if key is not None and key in s["_applied_idempotency_keys"]:
            # replayed/duplicate side effect -> deduped, NOT applied twice
            return False
        if key is not None: s["_applied_idempotency_keys"].append(key)
        tasks[tid]="COMPLETED" if et=="TASK_RESULT" else "FAILED"
        if tid in s["autonomous_execution"]["active_tasks"]: s["autonomous_execution"]["active_tasks"].remove(tid)
        if et=="TASK_RESULT" and e.get("evidence"): s["proven_tests"].append({"task_id":tid,"evidence":e["evidence"]})
        return True
    if et=="EVIDENCE_REGISTERED":
        s["evidence_refs"].append(e.get("inputs")); return True
    if et=="RUNNER_HEARTBEAT":
        s["runner_health"][e.get("agent")]=e["timestamp"]; return True
    if et in ("AUDIT_REQUEST","AUDIT_RESULT","CREATIVE_INTELLIGENCE_REQUEST","CREATIVE_INTELLIGENCE_RESULT",
              "TASK_REQUEST","TASK_CLAIMED","STATE_REDUCED"):
        return True
    s["_rejected_events"].append({"reason":"unknown_type","event_id":e.get("event_id")}); return False
