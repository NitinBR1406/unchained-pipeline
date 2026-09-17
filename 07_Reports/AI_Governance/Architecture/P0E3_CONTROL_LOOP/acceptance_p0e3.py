"""P0-E3 Slice-1 STRICT, FAIL-CLOSED acceptance gate.

Every mandatory criterion must be EXPLICITLY satisfied by evidence independently derived here (from the
ledger, the central store, the durable side-effect store and the invocation log). null / absent / malformed
=> FAIL. No criterion is ever inferred PASS. Writes P0E3_SLICE1_ACCEPTANCE.json and exits nonzero unless
FINAL == PASS.

This gate NEVER authorizes production deployment or publication; those verdicts are pinned FALSE.
"""
import os, sys, json, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))

from control_loop import scenarios as S
from control_loop import state_model
from control_loop.persistence import CONFLICT


def _is_true(v):
    return v is True


def _is_false(v):
    return v is False


def _is_zero(v):
    return isinstance(v, int) and not isinstance(v, bool) and v == 0


def verify():
    crit = {}
    notes = {}

    # ---- happy path (drives A->B chain, C park, D independent) ----
    hp = S.happy_path()
    loop = hp["loop"]
    ledger = loop.ledger
    persisted = hp["persisted"]
    status = hp["status"]

    # 1. EVENT_LEDGER_APPEND_ONLY — seqs are contiguous 0..n-1 and each record carries prev/hash envelope
    recs = ledger.read_all()
    seqs_ok = all(r.get("ledger_seq") == i for i, r in enumerate(recs)) and len(recs) > 0
    env_ok = all(("prev_ledger_hash" in r and "ledger_hash" in r) for r in recs)
    crit["EVENT_LEDGER_APPEND_ONLY"] = bool(seqs_ok and env_ok)

    # 2. EVENT_LEDGER_CHAIN_VALID — cryptographic chain verifies
    try:
        crit["EVENT_LEDGER_CHAIN_VALID"] = bool(ledger.verify_chain())
    except Exception as e:
        crit["EVENT_LEDGER_CHAIN_VALID"] = False
        notes["EVENT_LEDGER_CHAIN_VALID"] = repr(e)

    # 3. STATE_REPLAY_MATCHES_MASTER — REPLAY(ledger) == persisted MASTER STATE
    if not persisted:
        crit["STATE_REPLAY_MATCHES_MASTER"] = False
        notes["STATE_REPLAY_MATCHES_MASTER"] = "NO_PERSISTED_STATE"
    else:
        ok, detail = state_model.verify_replay(ledger, persisted)
        crit["STATE_REPLAY_MATCHES_MASTER"] = bool(ok)
        notes["STATE_REPLAY_MATCHES_MASTER"] = detail

    # 4. STATE_VERSION_MONOTONIC — HEAD version == derived version and strictly increased from genesis
    head = loop.persistence.read_head()
    derived_v = state_model.derive(ledger)["state_version"]
    crit["STATE_VERSION_MONOTONIC"] = bool(head and head["state_version"] == derived_v and derived_v > 0)

    # 5. CENTRAL_WRITE_READBACK_VERIFIED — re-read committed file, sha256 must match HEAD's recorded sha
    rb = False
    if head:
        raw = loop.persistence.backend.get_bytes(head["file"])
        rb = hashlib.sha256(raw).hexdigest() == head["sha256"]
    crit["CENTRAL_WRITE_READBACK_VERIFIED"] = bool(rb)

    # 6. STALE_WRITE_REJECTED — optimistic concurrency rejects a stale writer; HEAD untouched
    sw = S.stale_write_rejected()
    crit["STALE_WRITE_REJECTED"] = bool(sw["result"]["status"] == CONFLICT and sw["head_unchanged"])

    # 7. CONCURRENT_DOUBLE_CLAIM_COUNT == 0
    cc = S.concurrent_double_claim()
    crit["CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO"] = bool(
        _is_zero(cc["concurrent_double_claim_count"]) and cc["task_a_side_effect_count"] == 0
        and cc["outcome_worker2"] == "NOT_CLAIMED")
    notes["CONCURRENT_DOUBLE_CLAIM_COUNT"] = cc["concurrent_double_claim_count"]

    # 8. STALE_LEASE_RECLAIM == PASS — live lease not reclaimable; expired lease reclaimed by a DIFFERENT holder
    sl = S.stale_lease_reclaim()
    crit["STALE_LEASE_RECLAIM"] = bool(sl["live_acquired"] and sl["reclaim_while_live_blocked"]
                                       and sl["reclaim_after_expiry_ok"] and sl["reclaim_different_holder"])

    # 9. DUPLICATE_SIDE_EFFECT_COUNT == 0 (happy path: one invocation per distinct job_id)
    from collections import Counter
    per_job = Counter(i["job_id"] for i in hp["invocations"])
    dup_hp = sum(c - 1 for c in per_job.values())
    crit["DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO"] = bool(_is_zero(dup_hp))
    notes["DUPLICATE_SIDE_EFFECT_COUNT_happy"] = dup_hp

    # 10. AUTONOMOUS_NEXT_TASK == PASS — A and B both completed automatically (dependency chain advanced)
    crit["AUTONOMOUS_NEXT_TASK"] = bool(status.get("TASK_A") == "COMPLETED"
                                        and status.get("TASK_B") == "COMPLETED")

    # 11. WAITING_WORKFLOW_BLOCKS_OTHER_WORK == FALSE — C parked, D still completed
    blocks = not (status.get("TASK_C") == "WAITING_FOR_NITIN" and status.get("TASK_D") == "COMPLETED")
    crit["WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE"] = bool(_is_false(blocks))
    notes["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"] = blocks

    # 12. HUMAN_MESSAGE_RELAY_REQUIRED == FALSE
    crit["HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE"] = bool(
        _is_false(hp["result"]["human_message_relay_required"]))

    # 13. NO_APPROVAL_FABRICATED == TRUE — gated gate never granted without an Ed25519-verified approval
    approvals = (persisted or {}).get("approvals", {})
    crit["NO_APPROVAL_FABRICATED"] = bool("NITIN_PUBLISH_APPROVAL" not in approvals
                                          and status.get("TASK_C") == "WAITING_FOR_NITIN")

    # 14. CRASH_RECOVERY_MATRIX == PASS — all six boundaries recover deterministically
    matrix = {}
    matrix_pass = True
    for name, boundary in S.BOUNDARY_MAP.items():
        r = S.crash_and_recover(boundary)
        cell = {
            "crashed": r["crashed"],
            "no_duplicate_side_effect": _is_zero(r["duplicate_side_effects"]),
            "no_lost_completed_work": bool(r["a_done"] and r["b_done"] and r["d_done"]),
            "independent_continues": bool(r["d_done"]),
            "c_waits": bool(r["c_waiting"]),
            "no_fabricated_approval": bool(r["no_fabricated_approval"]),
            "replay_matches": bool(r["replay_matches"]),
        }
        cell["PASS"] = all([cell["crashed"], cell["no_duplicate_side_effect"], cell["no_lost_completed_work"],
                            cell["independent_continues"], cell["c_waits"], cell["no_fabricated_approval"],
                            cell["replay_matches"]])
        matrix[name] = cell
        matrix_pass = matrix_pass and cell["PASS"]
    crit["CRASH_RECOVERY_MATRIX"] = bool(matrix_pass)

    mandatory_all = all(bool(v) for v in crit.values())
    final = "PASS" if mandatory_all else "FAIL"
    failed = [k for k, v in crit.items() if not v]

    verdict = {
        "gate": "P0E3_SLICE_1_ACCEPTANCE",
        "criteria": crit,
        "crash_recovery_matrix": matrix,
        "notes": notes,
        "FINAL": final,
        "failed_criteria": failed,
        # invariants echoed in the required vocabulary
        "invariants": {
            "EVENT_LEDGER_APPEND_ONLY": crit["EVENT_LEDGER_APPEND_ONLY"],
            "EVENT_LEDGER_CHAIN_VALID": crit["EVENT_LEDGER_CHAIN_VALID"],
            "STATE_REPLAY_MATCHES_MASTER": crit["STATE_REPLAY_MATCHES_MASTER"],
            "STATE_VERSION_MONOTONIC": crit["STATE_VERSION_MONOTONIC"],
            "CENTRAL_WRITE_READBACK_VERIFIED": crit["CENTRAL_WRITE_READBACK_VERIFIED"],
            "STALE_WRITE_REJECTED": crit["STALE_WRITE_REJECTED"],
            "CONCURRENT_DOUBLE_CLAIM_COUNT": 0 if crit["CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO"] else "NONZERO",
            "STALE_LEASE_RECLAIM": "PASS" if crit["STALE_LEASE_RECLAIM"] else "FAIL",
            "DUPLICATE_SIDE_EFFECT_COUNT": 0 if crit["DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO"] else "NONZERO",
            "AUTONOMOUS_NEXT_TASK": "PASS" if crit["AUTONOMOUS_NEXT_TASK"] else "FAIL",
            "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": False if crit["WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE"] else "TRUE",
            "HUMAN_MESSAGE_RELAY_REQUIRED": False if crit["HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE"] else "TRUE",
            "NO_APPROVAL_FABRICATED": crit["NO_APPROVAL_FABRICATED"],
            "CRASH_RECOVERY_MATRIX": "PASS" if crit["CRASH_RECOVERY_MATRIX"] else "FAIL",
        },
        "PRODUCTION_DEPLOYMENT_AUTHORIZED": False,
        "PUBLICATION_AUTHORIZED": False,
    }
    return verdict


def main():
    v = verify()
    out = os.path.join(HERE, "evidence", "P0E3_SLICE1_ACCEPTANCE.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(v, open(out, "w"), indent=2, sort_keys=True)
    print(json.dumps({"FINAL": v["FINAL"], "failed_criteria": v["failed_criteria"]}, indent=2))
    print("wrote", out)
    sys.exit(0 if v["FINAL"] == "PASS" else 1)


if __name__ == "__main__":
    main()
