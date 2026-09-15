"""Deterministic State Reducer: ordered events -> Master State.
Pure function of (events, keyring): no wall clock, no randomness. Replayable + idempotent + fail-closed.
Human gates grant ONLY on an independently verifiable Ed25519 approval (see human_auth); the event `agent`
field is provenance and grants nothing. Idempotency prevents duplicate side effects."""
from .events import SCHEMA_VERSION, AUTHORITATIVE, is_wellformed
from . import human_auth
class ReducerError(Exception): pass
MASTER_SCHEMA_VERSION = 1
def _empty_state():
    return {
      "schema_version":MASTER_SCHEMA_VERSION,"state_version":0,"updated_at":None,"updated_by":None,
      "project":"UNCHAINED NITIN — MASTER","phase":"P0-E1","milestone":"TEMPORAL CONTROL PLANE FOUNDATION",
      "production_state":{"p1_scenario":"9627055","first_real_poster":"PAUSED_BY_NITIN","mutated":False},
      "scenario_ids":{},"datastore_ids":{},
      "git":{"repository":None,"branch":None,"commit_sha":None},"deployments":[],
      "architecture_locks":{"selected_control_plane":None,"architecture_bakeoff":None,"winner":None,
                            "production_deployment_authorized":False,"adr_ref":None},
      "approvals":{},"grants":{},"proven_tests":[],
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
      "_pending_gates":{}, "_consumed_approvals":[], "_revoked_approvals":[],
    }
def _validate_auth(e):
    if not is_wellformed(e): raise ReducerError("malformed authoritative event (fail-closed)")
    if e["schema_version"]!=SCHEMA_VERSION: raise ReducerError("unknown schema_version %r (fail-closed)"%e.get("schema_version"))
def reduce(events, state=None, keyring=None):
    s = state or _empty_state()
    if keyring is None: keyring = human_auth.load_keyring()
    tasks = {t:"RUNNING" for t in s["autonomous_execution"]["active_tasks"]}
    for e in events:
        et = e.get("event_type")
        if et in AUTHORITATIVE: _validate_auth(e)
        elif not is_wellformed(e):
            s["_rejected_events"].append({"reason":"malformed_nonauth","event_id":e.get("event_id")}); continue
        if _apply(s, e, tasks, keyring):
            s["state_version"] += 1; s["updated_at"]=e["timestamp"]; s["updated_by"]=e["agent"]
    return s
def _apply(s, e, tasks, keyring):
    et=e["event_type"]; tid=e.get("task_id")
    if et=="ARCH_DECISION":
        d=e.get("decision") or {}
        s["architecture_locks"].update({"selected_control_plane":d.get("selected_control_plane"),
            "architecture_bakeoff":d.get("architecture_bakeoff"),"winner":d.get("winner"),
            "production_deployment_authorized":bool(d.get("production_deployment_authorized",False)),
            "adr_ref":d.get("adr_ref")})
        s["provenance"].append({"arch_decision":e.get("event_id"),"ts":e["timestamp"]}); return True
    if et=="HUMAN_GATE_REQUEST":
        gate=e.get("gate")
        fp=(e.get("inputs") or {}).get("content_fingerprint")
        if fp is None and (e.get("inputs") or {}).get("content") is not None:
            fp=human_auth.content_fingerprint(e["inputs"]["content"])
        s["_pending_gates"]["%s|%s"%(tid,gate)]=fp
        s["autonomous_execution"]["waiting_for_nitin"].append({"task_id":tid,"gate":gate}); return True
    if et=="HUMAN_GATE_GRANTED":
        gate=e.get("gate"); pend_key="%s|%s"%(tid,gate)
        expected_fp=s["_pending_gates"].get(pend_key)
        ok,reason=human_auth.verify_approval(e, keyring=keyring, now=e["timestamp"], expected_gate=gate,
                    expected_task_id=tid, expected_fingerprint=expected_fp,
                    consumed_ids=s["_consumed_approvals"], revoked_ids=s["_revoked_approvals"])
        if not ok:
            # FAIL-CLOSED: metadata (agent) never grants; only a verified signature does
            s["_rejected_events"].append({"reason":"human_gate_"+reason,"event_id":e.get("event_id"),
                                          "agent":e.get("agent"),"gate":gate}); return False
        aid=e["approval"]["payload"]["approval_id"]; nonce=e["approval"]["payload"]["nonce"]
        s["_consumed_approvals"].extend([aid,nonce])
        s["approvals"][gate]={"task_id":tid,"approval_id":aid,"content_fingerprint":expected_fp,
                              "authority":"ed25519_verified","ts":e["timestamp"]}
        s["autonomous_execution"]["waiting_for_nitin"]=[w for w in s["autonomous_execution"]["waiting_for_nitin"]
                                                        if not (w.get("task_id")==tid and w.get("gate")==gate)]
        s["_pending_gates"].pop(pend_key,None); return True
    if et=="HUMAN_GATE_REJECTED":
        aid=(e.get("inputs") or {}).get("approval_id")
        if aid: s["_revoked_approvals"].append(aid)
        s["approvals"].pop(e.get("gate"),None); return True
    if et=="LEASE_ACQUIRED": tasks[tid]="CLAIMED"; return True
    if et in ("LEASE_EXPIRED","LEASE_RELEASED"):
        if tasks.get(tid) in ("CLAIMED","RUNNING"): tasks[tid]="READY"
        return True
    if et=="TASK_STARTED":
        tasks[tid]="RUNNING"
        if tid not in s["autonomous_execution"]["active_tasks"]: s["autonomous_execution"]["active_tasks"].append(tid)
        s["autonomous_execution"]["current_task"]=tid; return True
    if et in ("TASK_RESULT","TASK_FAILED"):
        if tasks.get(tid) not in ("RUNNING","CLAIMED"):
            s["_rejected_events"].append({"reason":"out_of_order_result","event_id":e.get("event_id"),"task_id":tid}); return False
        key=e.get("idempotency_key")
        if key is not None and key in s["_applied_idempotency_keys"]: return False  # deduped, no double side effect
        if key is not None: s["_applied_idempotency_keys"].append(key)
        tasks[tid]="COMPLETED" if et=="TASK_RESULT" else "FAILED"
        if tid in s["autonomous_execution"]["active_tasks"]: s["autonomous_execution"]["active_tasks"].remove(tid)
        if et=="TASK_RESULT" and e.get("evidence"): s["proven_tests"].append({"task_id":tid,"evidence":e["evidence"]})
        return True
    if et=="EVIDENCE_REGISTERED": s["evidence_refs"].append(e.get("inputs")); return True
    if et=="RUNNER_HEARTBEAT": s["runner_health"][e.get("agent")]=e["timestamp"]; return True
    if et in ("AUDIT_REQUEST","AUDIT_RESULT","CREATIVE_INTELLIGENCE_REQUEST","CREATIVE_INTELLIGENCE_RESULT",
              "TASK_REQUEST","TASK_CLAIMED","STATE_REDUCED"): return True
    s["_rejected_events"].append({"reason":"unknown_type","event_id":e.get("event_id")}); return False
