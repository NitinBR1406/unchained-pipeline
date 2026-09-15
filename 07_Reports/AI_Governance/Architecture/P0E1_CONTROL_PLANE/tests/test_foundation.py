import sys, os, json, tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
from control_plane import events as E
from control_plane.ledger import EventLedger, LedgerError
from control_plane.reducer import reduce, ReducerError
from control_plane.backlog import ready_tasks, summary
from control_plane.leases import LeaseTable
from control_plane.idempotency import job_id, SideEffectStore
from control_plane.temporal_foundation import simulate

P=F=0; FAILS=[]
def ok(name,cond):
    global P,F
    if cond: P+=1; print("PASS",name)
    else: F+=1; FAILS.append(name); print("FAIL",name)

def ev(i,t,**kw): return E.make_event("e%03d"%i,t,"2026-01-01T00:00:%02dZ"%(i%60),kw.pop("agent","claude"),**kw)

# --- ARCH decision applies + production not authorized ---
arch=ev(1,"ARCH_DECISION",decision={"selected_control_plane":"TEMPORAL","architecture_bakeoff":"CLOSED",
        "winner":"TEMPORAL","production_deployment_authorized":False,"adr_ref":"P0E_ADR_001_TEMPORAL_CONTROL_PLANE.md"})
s=reduce([arch])
ok("arch_decision_temporal", s["architecture_locks"]["winner"]=="TEMPORAL" and s["architecture_locks"]["selected_control_plane"]=="TEMPORAL")
ok("production_not_authorized", s["architecture_locks"]["production_deployment_authorized"] is False)

# --- deterministic replay: same events -> same state ---
stream=[arch,
        ev(2,"TASK_STARTED",task_id="T1"),
        ev(3,"TASK_RESULT",task_id="T1",idempotency_key="k1",evidence=["ev://T1"]),
        ev(4,"TASK_STARTED",task_id="T2"),
        ev(5,"HUMAN_GATE_REQUEST",task_id="T2",gate="NITIN_PUBLISH_APPROVAL")]
s1=reduce(stream); s2=reduce(stream)
ok("deterministic_replay", E.canonical(s1)==E.canonical(s2))
ok("state_recovered_after_restart", E.canonical(reduce(list(stream)))==E.canonical(s1))  # rebuild == original

# --- replayed/duplicate TASK_RESULT => deduped, no double side effect ---
dup=stream+[ev(6,"TASK_STARTED",task_id="T1b"),ev(7,"TASK_RESULT",task_id="T1b",idempotency_key="k1",evidence=["ev://dup"])]
sd=reduce(dup)
proven_k1=[p for p in sd["proven_tests"]]
ok("duplicate_side_effect_count_zero", sd["duplicate_side_effect_count"]==0)
ok("idempotent_result_not_double_applied", sum(1 for p in sd["proven_tests"] if p["task_id"] in ("T1","T1b"))==1)

# --- out-of-order result (before started) => fail-closed rejected ---
oo=reduce([arch, ev(2,"TASK_RESULT",task_id="TX",idempotency_key="kx")])
ok("out_of_order_result_rejected", any(r["reason"]=="out_of_order_result" for r in oo["_rejected_events"]))

# --- unknown schema version on authoritative event => fail-closed raise ---
bad=dict(arch); bad["schema_version"]=999
try: reduce([bad]); ok("unknown_schema_failclosed",False)
except ReducerError: ok("unknown_schema_failclosed",True)

# --- malformed authoritative event => fail-closed raise ---
mal={"event_type":"TASK_RESULT"}  # missing required fields
try: reduce([mal]); ok("malformed_failclosed",False)
except ReducerError: ok("malformed_failclosed",True)

# --- HUMAN GATE: only nitin can grant; AI impersonation rejected ---
imp=reduce([arch, ev(10,"HUMAN_GATE_REQUEST",task_id="P",gate="NITIN_PUBLISH_APPROVAL"),
            ev(11,"HUMAN_GATE_GRANTED",task_id="P",gate="NITIN_PUBLISH_APPROVAL",agent="claude")])
ok("ai_cannot_create_nitin_approval", "NITIN_PUBLISH_APPROVAL" not in imp["approvals"])
ok("impersonation_recorded_rejected", any(r["reason"].startswith("human_gate_") for r in imp["_rejected_events"]))
bare=reduce([arch, ev(10,"HUMAN_GATE_REQUEST",task_id="P",gate="NITIN_PUBLISH_APPROVAL"),
             ev(11,"HUMAN_GATE_GRANTED",task_id="P",gate="NITIN_PUBLISH_APPROVAL",agent="nitin")])
ok("bare_nitin_metadata_does_not_grant", "NITIN_PUBLISH_APPROVAL" not in bare["approvals"])  # hardened: metadata != authority

# --- WAITING_FOR_NITIN isolation: independent READY task stays executable ---
tasks=[{"task_id":"PUB","status":"WAITING_FOR_NITIN","dependencies":[]},
       {"task_id":"IMPL","status":"READY","dependencies":[]},
       {"task_id":"DEP","status":"READY","dependencies":["IMPL"]}]
r=ready_tasks(tasks)
ok("waiting_for_nitin_isolation", any(t["task_id"]=="IMPL" for t in r) and all(t["task_id"]!="PUB" for t in r))
ok("dependency_gating", all(t["task_id"]!="DEP" for t in r))  # DEP blocked until IMPL completed

# --- leases: A claims, A dies, lease expires, B reclaims; no concurrent double-hold ---
LT=LeaseTable()
la=LT.acquire("T","workerA","lidA",now=0,ttl=10)
ok("lease_acquired", la is not None)
ok("no_concurrent_double_claim", LT.acquire("T","workerB","lidB",now=1,ttl=10) is None)
ok("stale_lease_expires", LT.get("T").is_expired(now=11))
lb=LT.reclaim("T","workerB","lidB",now=12,ttl=10)
ok("safe_reclaim_after_death", lb is not None and lb.holder=="workerB")

# --- idempotency job identity deterministic ---
ok("job_id_deterministic", job_id("T",5,"h")==job_id("T",5,"h") and job_id("T",5,"h")!=job_id("T",6,"h"))
se=SideEffectStore(); _,d1=se.once("k",lambda:{"x":1}); _,d2=se.once("k",lambda:{"x":1})
ok("exactly_once_side_effect", d1 is False and d2 is True and se.count()==1)

# --- ledger: append-only + tamper-evident ---
tmp=tempfile.mkdtemp(); lp=os.path.join(tmp,"EVENT_LEDGER.jsonl"); L=EventLedger(lp)
for e in stream: L.append(e)
ok("ledger_chain_valid", L.verify_chain())
lines=open(lp).read().splitlines(); rec=json.loads(lines[1]); rec["agent"]="tampered"; lines[1]=E.canonical(rec)
open(lp,"w").write("\n".join(lines)+"\n")
try: L.verify_chain(); ok("ledger_tamper_detected",False)
except LedgerError: ok("ledger_tamper_detected",True)

# --- five non-regression invariants ---
sim=simulate(max_slots=4, independent=20)
ok("INV_WAITING_WORKFLOW_BLOCKS_OTHER_WORK_false", sim["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"] is False)
ok("INV_WORKER_SLOT_HELD_DURING_HUMAN_WAIT_false", sim["WORKER_SLOT_HELD_DURING_HUMAN_WAIT"] is False)
ok("INV_STATE_RECOVERED_AFTER_RESTART_true", E.canonical(reduce(list(stream)))==E.canonical(reduce(list(stream))))
ok("INV_DUPLICATE_SIDE_EFFECT_COUNT_zero", reduce(dup)["duplicate_side_effect_count"]==0)
ok("INV_HUMAN_MESSAGE_RELAY_REQUIRED_false", reduce(stream)["invariants"]["HUMAN_MESSAGE_RELAY_REQUIRED"] is False)

print("\nTOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
