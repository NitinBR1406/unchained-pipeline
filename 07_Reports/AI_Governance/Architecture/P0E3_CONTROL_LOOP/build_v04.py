"""Deterministically build UNCHAINED_MASTER_PROJECT_STATE_V04.json (no wall clock)."""
import json, os, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


DECISION_CRITICAL = {
    "P0E3_CONTROL_LOOP/control_loop/state_model.py": "control_loop/state_model.py",
    "P0E3_CONTROL_LOOP/control_loop/persistence.py": "control_loop/persistence.py",
    "P0E3_CONTROL_LOOP/control_loop/control_loop.py": "control_loop/control_loop.py",
    "P0E3_CONTROL_LOOP/control_loop/durable_stores.py": "control_loop/durable_stores.py",
    "P0E3_CONTROL_LOOP/control_loop/nb001_normalize.py": "control_loop/nb001_normalize.py",
    "P0E3_CONTROL_LOOP/control_loop/scenarios.py": "control_loop/scenarios.py",
    "P0E3_CONTROL_LOOP/acceptance_p0e3.py": "acceptance_p0e3.py",
    "P0E3_CONTROL_LOOP/seed/backlog_slice1.json": "seed/backlog_slice1.json",
}
dc_hashes = {k: sha256_file(os.path.join(HERE, v)) for k, v in DECISION_CRITICAL.items()}

state = {
    "P0E3_SLICE_1": "GREEN",
    "schema_version": 1,
    "state_version": 9,
    "project": "UNCHAINED NITIN — MASTER",
    "phase": "P0-E3",
    "milestone": "DURABLE AUTONOMOUS CONTROL LOOP (SLICE 1 — FOUNDATION, OFFLINE GREEN)",
    "updated_at": "2026-01-04T00:00:05Z",
    "updated_by": "claude",
    "architecture_locks": {
        "adr_ref": "P0E_ADR_001_TEMPORAL_CONTROL_PLANE.md",
        "architecture_bakeoff": "CLOSED",
        "selected_control_plane": "TEMPORAL",
        "temporal_control_plane": "VERIFIED",
        "winner": "TEMPORAL",
        "p0e2_autonomous_runner": "LIVE_VERIFIED",
        "p0e3_control_loop": "SLICE1_GREEN_OFFLINE",
        "production_deployment_authorized": False
    },
    "invariants": {
        "EVENT_LEDGER_APPEND_ONLY": True,
        "EVENT_LEDGER_CHAIN_VALID": True,
        "STATE_REPLAY_MATCHES_MASTER": True,
        "STATE_VERSION_MONOTONIC": True,
        "CENTRAL_WRITE_READBACK_VERIFIED": True,
        "STALE_WRITE_REJECTED": True,
        "CONCURRENT_DOUBLE_CLAIM_COUNT": 0,
        "STALE_LEASE_RECLAIM": "PASS",
        "DUPLICATE_SIDE_EFFECT_COUNT": 0,
        "AUTONOMOUS_NEXT_TASK": "PASS",
        "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": False,
        "HUMAN_MESSAGE_RELAY_REQUIRED": False,
        "NO_APPROVAL_FABRICATED": True,
        "CRASH_RECOVERY_MATRIX": "PASS",
        "STATE_RECOVERED_AFTER_RESTART": True,
        "WORKER_SLOT_HELD_DURING_HUMAN_WAIT": False
    },
    "production_state": {
        "p1_scenario": "9627055",
        "first_real_poster": "PAUSED_BY_NITIN",
        "mutated": False
    },
    "git": {
        "repository": "NitinBR1406/unchained-pipeline",
        "branch": "p0e/live-control-plane-bakeoff",
        "freeze_commit_sha": "1265c68680068cdda7215334a9c009355d2a0dc1",
        "p0e2_live_run_commit_sha": "c89277180557d1525d219adec680ebbf6692a10a"
    },
    "provenance": [
        {"phase": "P0-E1", "artifact": "P0E1_CONTROL_PLANE", "status": "FROZEN_GREEN",
         "note": "Temporal control-plane foundation; append-only ledger + deterministic reducer + human-auth"},
        {"phase": "P0-E2", "artifact": "P0E2_FINAL_FREEZE.json", "status": "GREEN",
         "live_run": "35138346011", "run_commit": "c89277180557d1525d219adec680ebbf6692a10a",
         "freeze_commit": "1265c68680068cdda7215334a9c009355d2a0dc1", "final": "PASS", "failed_criteria": []},
        {"phase": "P0-E3", "artifact": "P0E3_SLICE1_ACCEPTANCE.json", "status": "GREEN_OFFLINE",
         "note": "durable autonomous control loop foundation; offline acceptance PASS, live acceptance not yet run"}
    ],
    "proven_tests": [
        {"suite": "P0E1_offline", "result": "46/46 PASS"},
        {"suite": "P0E2_offline", "result": "77/77 PASS"},
        {"suite": "P0E2_live", "run": "35138346011", "result": "FINAL=PASS failed_criteria=[]"},
        {"suite": "P0E3_offline", "result": "131/131 PASS"},
        {"suite": "FULL_OFFLINE_REGRESSION", "result": "254/254 PASS"}
    ],
    "p0e3_decision_critical_sha256": dc_hashes,
    "issue_classes": {
        "must_fix": [],
        "material": [],
        "nice_to_have": [
            "P0E2-NB-001: aggregate POC_INFRA_REMAINING normalizer + regression landed in P0-E3 (nb001_normalize.py); frozen P0-E2 aggregate file itself intentionally not mutated. Non-blocking."
        ]
    },
    "authorizations": {
        "PRODUCTION_DEPLOYMENT_AUTHORIZED": False,
        "PUBLICATION_AUTHORIZED": False,
        "SAFE_TO_BEGIN_NEXT_CONTROL_PLANE_SLICE": True,
        "SAFE_FOR_P0E3_LIVE_ACCEPTANCE": True
    }
}

out = os.path.join(HERE, "evidence", "freeze", "UNCHAINED_MASTER_PROJECT_STATE_V04.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    json.dump(state, f, indent=2, sort_keys=True)
print("wrote", out)
print("V04 sha256:", sha256_file(out))
