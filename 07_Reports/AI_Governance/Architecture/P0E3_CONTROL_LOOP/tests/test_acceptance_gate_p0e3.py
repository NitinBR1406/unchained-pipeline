"""P0-E3 acceptance gate: FINAL=PASS on real evidence; strict + fail-closed on any broken criterion."""
from _harness import Counter
import acceptance_p0e3 as G
from control_loop import scenarios as S
c = Counter("AG3")

v = G.verify()
c.ok("FINAL_PASS", v["FINAL"] == "PASS")
c.ok("no_failed_criteria", v["failed_criteria"] == [])
c.ok("all_criteria_true", all(bool(x) for x in v["criteria"].values()))
c.ok("14_criteria_present", len(v["criteria"]) == 14)
c.ok("crash_matrix_6_cells", len(v["crash_recovery_matrix"]) == 6)
c.ok("crash_matrix_all_pass", all(cell["PASS"] for cell in v["crash_recovery_matrix"].values()))
c.ok("production_deploy_false", v["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is False)
c.ok("publication_false", v["PUBLICATION_AUTHORIZED"] is False)

# invariant vocabulary echoed correctly
inv = v["invariants"]
c.ok("inv_double_claim_zero", inv["CONCURRENT_DOUBLE_CLAIM_COUNT"] == 0)
c.ok("inv_dup_side_effect_zero", inv["DUPLICATE_SIDE_EFFECT_COUNT"] == 0)
c.ok("inv_stale_lease_pass", inv["STALE_LEASE_RECLAIM"] == "PASS")
c.ok("inv_waiting_false", inv["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"] is False)
c.ok("inv_relay_false", inv["HUMAN_MESSAGE_RELAY_REQUIRED"] is False)
c.ok("inv_crash_pass", inv["CRASH_RECOVERY_MATRIX"] == "PASS")

# strictness helpers reject null / non-bool
c.ok("is_true_rejects_null", not G._is_true(None) and not G._is_true("true") and G._is_true(True))
c.ok("is_false_rejects_null", not G._is_false(None) and G._is_false(False))
c.ok("is_zero_rejects_bool", not G._is_zero(True) and not G._is_zero(None) and G._is_zero(0))

# FAIL-CLOSED: if a scenario regresses (double claim allowed), the gate FAILS
orig = S.concurrent_double_claim
S.concurrent_double_claim = lambda: {"concurrent_double_claim_count": 1, "task_a_side_effect_count": 1,
                                     "outcome_worker2": "COMPLETED", "worker1_holds_live_lease": True}
try:
    v2 = G.verify()
    c.ok("regression_forces_FAIL", v2["FINAL"] == "FAIL"
         and "CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO" in v2["failed_criteria"])
finally:
    S.concurrent_double_claim = orig

# FAIL-CLOSED: if replay is broken, the gate FAILS
orig2 = S.happy_path
def broken_hp(workdir=None):
    hp = orig2(workdir)
    hp["persisted"] = dict(hp["persisted"]); hp["persisted"]["state_version"] += 99
    return hp
S.happy_path = broken_hp
try:
    v3 = G.verify()
    c.ok("broken_replay_forces_FAIL", v3["FINAL"] == "FAIL"
         and "STATE_REPLAY_MATCHES_MASTER" in v3["failed_criteria"])
finally:
    S.happy_path = orig2

c.done()
