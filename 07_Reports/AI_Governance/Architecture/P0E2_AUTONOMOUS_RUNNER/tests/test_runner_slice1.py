import os, sys, json, tempfile, shutil, copy
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
sys.path.insert(0, os.path.join(ROOT,"..","P0E1_CONTROL_PLANE"))
from runner import Runner
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
from control_plane.backlog import ready_tasks
from control_plane.leases import LeaseTable
from control_plane.idempotency import SideEffectStore
from control_plane import events as E
SEED=os.path.join(ROOT,"seed","backlog_slice1.json")
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)
def fresh():
    d=tempfile.mkdtemp(); bl=os.path.join(d,"BACKLOG.json"); shutil.copy(SEED,bl)
    return Runner(bl, os.path.join(d,"EVENT_LEDGER.jsonl"), os.path.join(d,"se.json"), os.path.join(d,"evidence"))

# ===== ACCEPTANCE: A->B chain, C waiting, D independent continues =====
r=fresh(); st=r.run_to_quiescence()
status={t["task_id"]:t["status"] for t in r._tasklist()}
ok("A_completed", status["TASK_A"]=="COMPLETED")
ok("B_completed_after_A", status["TASK_B"]=="COMPLETED")
ok("C_waiting_for_nitin", status["TASK_C"]=="WAITING_FOR_NITIN")
ok("D_completed_while_C_waits", status["TASK_D"]=="COMPLETED")
ok("AUTONOMOUS_CHAIN_A_TO_B", status["TASK_A"]=="COMPLETED" and status["TASK_B"]=="COMPLETED")
ok("INDEPENDENT_D_CONTINUES", status["TASK_D"]=="COMPLETED" and status["TASK_C"]=="WAITING_FOR_NITIN")
ok("WAITING_WORKFLOW_BLOCKS_OTHER_WORK_false", status["TASK_B"]=="COMPLETED" and status["TASK_D"]=="COMPLETED")
ok("no_approval_fabricated", "NITIN_PUBLISH_APPROVAL" not in st.get("approvals",{}))
ok("HUMAN_MESSAGE_RELAY_REQUIRED_false", st["invariants"]["HUMAN_MESSAGE_RELAY_REQUIRED"] is False)
# exactly-once side effects: A,B,D executed => 3 distinct; no duplicates
ok("DUPLICATE_SIDE_EFFECT_COUNT_zero", r.se.count()==3 and r.se.duplicate_attempts==0)
# state reconstruction: reduce twice identical
evs=r.ledger.read_all()
ok("STATE_RECONSTRUCTION", E.canonical(reduce(evs))==E.canonical(reduce(evs)))
# next ready after quiescence is None (only C waiting)
ok("no_next_ready_only_C_waiting", r.next_ready() is None)

# ===== FAILURE TESTS =====
# 1) stale lease reclaim
LT=LeaseTable(); la=LT.acquire("T","A","l1",now=0,ttl=10)
ok("stale_lease_blocks_live", LT.acquire("T","B","l2",now=1,ttl=10) is None)
ok("stale_lease_reclaim_after_expiry", (LT.get("T").is_expired(now=11)) and LT.reclaim("T","B","l2",now=12,ttl=10).holder=="B")
# 2) duplicate dispatch => no duplicate side effect
se=SideEffectStore(); _,d1=se.once("k",lambda:{"x":1}); _,d2=se.once("k",lambda:{"x":1})
ok("duplicate_dispatch_no_double", d1 is False and d2 is True and se.count()==1)
# replayed TASK_RESULT same idempotency_key not double-applied by reducer
ev=[E.make_event("x1","TASK_STARTED","t","claude",task_id="Z"),
    E.make_event("x2","TASK_RESULT","t","claude",task_id="Z",idempotency_key="kz",evidence=["e"]),
    E.make_event("x3","TASK_STARTED","t","claude",task_id="Z2"),
    E.make_event("x4","TASK_RESULT","t","claude",task_id="Z2",idempotency_key="kz",evidence=["dup"])]
sr=reduce(ev); ok("reducer_dedup_replayed_result", sum(1 for p in sr["proven_tests"] if p["task_id"] in ("Z","Z2"))==1 and sr["duplicate_side_effect_count"]==0)
# 3) worker interruption resume (pinned job_id => exactly-once across crash)
r2=fresh(); ta=r2.tasks["TASK_A"]
r2.execute_task(ta, simulate_crash_before_result=True)   # side effect done, no result, lease held
before=r2.se.count()
# resume: reclaim + re-execute reuses pinned _job_id
r2.leases._by_task.pop("TASK_A",None)                    # simulate lease expiry/reclaim window
res=r2.execute_task(ta)
ok("worker_interruption_resume_exactly_once", res=="COMPLETED" and r2.se.count()==before and r2.se.duplicate_attempts>=1)
# 4) invalid transition fail-closed (result before start)
inv=reduce([E.make_event("i1","TASK_RESULT","t","claude",task_id="NOPE",idempotency_key="k")])
ok("invalid_transition_failclosed", any(x["reason"]=="out_of_order_result" for x in inv["_rejected_events"]))
# 5) dependency violation cannot execute (B not ready before A)
r3=fresh(); rd=[t["task_id"] for t in ready_tasks(r3._tasklist())]
ok("dependency_violation_blocks_B", "TASK_B" not in rd and "TASK_A" in rd)
# 6) human-gated cannot self-approve / AI metadata cannot impersonate Nitin
imp=reduce([E.make_event("h1","HUMAN_GATE_REQUEST","t","claude",task_id="TASK_C",gate="NITIN_PUBLISH_APPROVAL"),
            E.make_event("h2","HUMAN_GATE_GRANTED","t","claude",task_id="TASK_C",gate="NITIN_PUBLISH_APPROVAL")])
ok("ai_cannot_self_approve", "NITIN_PUBLISH_APPROVAL" not in imp["approvals"] and any("human_gate" in x["reason"] for x in imp["_rejected_events"]))

print("\nSLICE1_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
