"""P0-E3 durable loop: autonomous next-task, waiting non-blocking, no relay, no fabricated approval, bounded."""
import os, tempfile, shutil
from _harness import Counter
from control_loop import scenarios as S, state_model
from control_loop.control_loop import DurableControlLoop, Clock
from control_loop.durable_stores import BacklogStore, validate_task, SchemaError, TASK_FIELDS
c = Counter("CL")

hp = S.happy_path()
st = hp["status"]
c.ok("A_completed", st["TASK_A"] == "COMPLETED")
c.ok("B_completed_after_A", st["TASK_B"] == "COMPLETED")
c.ok("C_waiting_for_nitin", st["TASK_C"] == "WAITING_FOR_NITIN")
c.ok("D_completed_while_C_waits", st["TASK_D"] == "COMPLETED")
c.ok("AUTONOMOUS_NEXT_TASK", st["TASK_A"] == "COMPLETED" and st["TASK_B"] == "COMPLETED")
c.ok("WAITING_WORKFLOW_BLOCKS_OTHER_WORK_false", st["TASK_B"] == "COMPLETED" and st["TASK_D"] == "COMPLETED")
c.ok("HUMAN_MESSAGE_RELAY_REQUIRED_false", hp["result"]["human_message_relay_required"] is False)
c.ok("no_approval_fabricated", "NITIN_PUBLISH_APPROVAL" not in hp["persisted"].get("approvals", {}))

# exactly one side effect per completed task
inv = hp["invocations"]
tids = [i["task_id"] for i in inv]
c.ok("three_side_effects_total", len(inv) == 3)
c.ok("no_side_effect_for_gated_C", "TASK_C" not in tids)
c.ok("distinct_jobs_equal_invocations", len(set(i["job_id"] for i in inv)) == len(inv))

# dependency gating: B never runs before A completes (B's invocation strictly after A's)
c.ok("B_after_A_ordering", tids.index("TASK_A") < tids.index("TASK_B"))

# re-running the loop after quiescence is a no-op (idempotent; no new side effects)
loop2 = DurableControlLoop(hp["workdir"], clock=Clock(9000))
res2 = loop2.run(max_iterations=50)
inv2 = S._invocations(loop2)
c.ok("rerun_is_noop", len(inv2) == 3)
ok, _ = state_model.verify_replay(loop2.ledger, loop2.persisted_state())
c.ok("replay_still_matches_after_rerun", ok)

# bounded: loop refuses to run unbounded
d = tempfile.mkdtemp(); shutil.copy(S.SEED, os.path.join(d, "BACKLOG.json"))
loopb = DurableControlLoop(d, clock=Clock(1000))
raised = False
try:
    loopb.run(max_iterations=1)   # 4 tasks but only 1 iteration allowed -> must raise, not loop forever
except RuntimeError:
    raised = True
c.ok("bounded_execution_enforced", raised)

# canonical backlog schema present on every seed task
bl = BacklogStore(os.path.join(hp["workdir"], "BACKLOG.json"))
c.ok("schema_all_fields_present", all(all(f in t for f in TASK_FIELDS) for t in bl.tasks))

# schema validation is fail-closed
bad = {f: None for f in TASK_FIELDS}; bad.pop("rollback")
try:
    validate_task(bad); c.ok("schema_missing_field_rejected", False)
except SchemaError:
    c.ok("schema_missing_field_rejected", True)

# deterministic dependency resolution: only A and independents are READY initially (B blocked by A)
d2 = tempfile.mkdtemp(); shutil.copy(S.SEED, os.path.join(d2, "BACKLOG.json"))
bl2 = BacklogStore(os.path.join(d2, "BACKLOG.json"))
ready_ids = [t["task_id"] for t in bl2.ready()]
c.ok("B_not_ready_before_A", "TASK_B" not in ready_ids and "TASK_A" in ready_ids)
c.ok("ready_ordered_by_priority", ready_ids == sorted(ready_ids, key=lambda x: {"TASK_A":10,"TASK_C":30,"TASK_D":40}[x]))

c.done()
