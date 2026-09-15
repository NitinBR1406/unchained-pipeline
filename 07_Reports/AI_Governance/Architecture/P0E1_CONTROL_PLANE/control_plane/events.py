"""Typed, immutable event contracts + canonical hashing."""
import json, hashlib
SCHEMA_VERSION = 1
EVENT_TYPES = {
 "TASK_REQUEST","TASK_CLAIMED","TASK_STARTED","TASK_RESULT","TASK_FAILED",
 "AUDIT_REQUEST","AUDIT_RESULT","CREATIVE_INTELLIGENCE_REQUEST","CREATIVE_INTELLIGENCE_RESULT",
 "ARCH_DECISION","HUMAN_GATE_REQUEST","HUMAN_GATE_GRANTED","HUMAN_GATE_REJECTED",
 "STATE_REDUCED","LEASE_ACQUIRED","LEASE_EXPIRED","LEASE_RELEASED","RUNNER_HEARTBEAT","EVIDENCE_REGISTERED",
}
# events that mutate authoritative state and must be well-formed or the reducer fails closed
AUTHORITATIVE = EVENT_TYPES - {"RUNNER_HEARTBEAT"}
REQUIRED = ("event_id","event_type","timestamp","agent","schema_version")
# the four authoritative human gates — grantable ONLY by nitin
HUMAN_GATES = {"NITIN_CREATIVE_APPROVAL","NITIN_FINAL_ASSET_APPROVAL","NITIN_FINAL_VIDEO_APPROVAL",
               "NITIN_PUBLISH_APPROVAL","NITIN_CHANGE_APPROVAL"}
def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",",":"))
def sha256(obj):
    b = obj if isinstance(obj,bytes) else canonical(obj).encode()
    return hashlib.sha256(b).hexdigest()
def input_hash(inputs):
    return sha256(inputs or {})
def make_event(event_id, event_type, timestamp, agent, task_id=None, inputs=None,
               evidence=None, decision=None, confidence=None, next_action=None,
               correlation_id=None, causation_id=None, lease_id=None, idempotency_key=None,
               gate=None, schema_version=SCHEMA_VERSION):
    e = {"event_id":event_id,"event_type":event_type,"timestamp":timestamp,"agent":agent,
         "schema_version":schema_version,"task_id":task_id,"inputs":inputs or {},
         "evidence":evidence or [],"decision":decision,"confidence":confidence,"next_action":next_action}
    for k,v in (("correlation_id",correlation_id),("causation_id",causation_id),("lease_id",lease_id),
                ("idempotency_key",idempotency_key),("gate",gate)):
        if v is not None: e[k]=v
    e["input_hash"]=input_hash(e["inputs"])
    return e
def is_wellformed(e):
    if not isinstance(e,dict): return False
    if any(k not in e for k in REQUIRED): return False
    if e["event_type"] not in EVENT_TYPES: return False
    return True
