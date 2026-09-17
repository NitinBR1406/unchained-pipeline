"""P0-E3 Slice-2 live acceptance gate: FINAL=PASS on a live-shaped evidence bundle (hermetic); governance
pinned FALSE; the synthetic offline fixture can NEVER satisfy the real Shared Drive criterion."""
import tempfile
from _harness import Counter, live_shaped_drive_contract
from control_loop import live_evidence as LE
import live_acceptance_p0e3 as G
c = Counter("LA3")

# PASS path uses an EXPLICIT live-shaped drive contract (no recorded artifact, no proof file read)
d = tempfile.mkdtemp()
loop, facts = LE.build_pass_bundle(d, drive=live_shaped_drive_contract())
v = G.verify(d)

c.ok("FINAL_PASS", v["FINAL"] == "PASS")
c.ok("no_failed_criteria", v["failed_criteria"] == [])
c.ok("all_criteria_true", all(bool(x) for x in v["criteria"].values()))
c.ok("gate_is_slice2", v["gate"] == "P0E3_SLICE_2_LIVE_ACCEPTANCE")

# every mandatory live criterion present
required = ["CHECKED_OUT_SHA_MATCHES_REQUEST", "EVENT_LEDGER_APPEND_ONLY", "EVENT_LEDGER_CHAIN_VALID",
            "STATE_REPLAY_MATCHES_MASTER", "STATE_VERSION_MONOTONIC", "CENTRAL_WRITE_READBACK_VERIFIED",
            "CENTRAL_READBACK_SHA_MATCH", "REAL_CENTRAL_PERSISTENCE_OBSERVED",
            "REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED", "STALE_WRITE_REJECTED",
            "CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO", "STALE_LEASE_RECLAIM",
            "DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO", "AUTONOMOUS_NEXT_TASK",
            "WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE", "HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE",
            "NO_APPROVAL_FABRICATED", "REAL_TEMPORAL_WORKFLOWS_OBSERVED", "CRASH_RECOVERY_MATRIX",
            "TEMPORAL_POC_INFRA_REMAINING_IS_FALSE", "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING_IS_FALSE",
            "POC_INFRA_REMAINING_IS_FALSE", "P0E2_NB_001_CLOSED"]
c.ok("all_required_criteria_present", all(k in v["criteria"] for k in required))
c.ok("criteria_count_23", len(v["criteria"]) == 23)
c.ok("real_shared_drive_observed", v["criteria"]["REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"] is True)

# crash matrix has all six live cases, each PASS
c.ok("crash_matrix_six_cases", len(v["crash_recovery_matrix"]) == 6)
c.ok("crash_matrix_all_pass", all(cell["PASS"] for cell in v["crash_recovery_matrix"].values()))

# governance pinned
c.ok("production_deploy_false", v["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is False)
c.ok("publication_false", v["PUBLICATION_AUTHORIZED"] is False)
c.ok("first_real_poster_paused", v["FIRST_REAL_POSTER"] == "PAUSED_BY_NITIN")
c.ok("nb001_closed", v["P0E2_NB_001"] == "CLOSED")

# real central persistence + real temporal observed came from underlying artifacts
c.ok("real_central_observed", v["criteria"]["REAL_CENTRAL_PERSISTENCE_OBSERVED"] is True)
c.ok("real_temporal_observed", v["criteria"]["REAL_TEMPORAL_WORKFLOWS_OBSERVED"] is True)

# ---- SECURITY: the synthetic offline fixture can NEVER satisfy the real Shared Drive criterion ----
d2 = tempfile.mkdtemp()
LE.build_pass_bundle(d2)   # default => synthetic_drive_fixture()
v2 = G.verify(d2)
c.ok("synthetic_fixture_FAILS_gate", v2["FINAL"] == "FAIL")
c.ok("synthetic_only_fails_real_drive",
     v2["failed_criteria"] == ["REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"])
c.ok("synthetic_predicate_false", LE.drive_persistence_observed(LE.synthetic_drive_fixture()) is False)
c.ok("synthetic_source_tag", LE.synthetic_drive_fixture()["source"] == LE.SYNTHETIC_SOURCE)
# every OTHER criterion still passes with the synthetic fixture (only the real-drive gate blocks it)
c.ok("synthetic_all_other_criteria_pass",
     all(x for k, x in v2["criteria"].items() if k != "REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"))

c.done()
