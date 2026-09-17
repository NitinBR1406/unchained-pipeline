"""P0-E3 Slice-2 STRICT, FAIL-CLOSED live acceptance reducer (authoritative).

Independently derives EVERY mandatory criterion from the underlying live evidence — re-opening the live
Event Ledger, re-deriving Master State, and re-reading the central store to recompute read-back SHAs. It
NEVER lets an aggregate boolean stand in for missing decision-critical evidence: if the ledger, central
store, workflow ids, crash evidence or checkout proof is absent / null / malformed, the criterion FAILS.

Writes P0E3_LIVE_ACCEPTANCE_VERDICT.json and exits nonzero unless FINAL == PASS.
PRODUCTION_DEPLOYMENT_AUTHORIZED and PUBLICATION_AUTHORIZED are pinned FALSE.
"""
import os, sys, json, hashlib, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))

from control_loop import live_evidence as LE
from control_loop import state_model
from control_plane.ledger import EventLedger
from control_loop.persistence import CentralPersistence
from control_loop.live_backend import SharedVolumeBackend

def open_ledger(path):
    return EventLedger(path)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
TASKS = ("TASK_A", "TASK_B", "TASK_C", "TASK_D")


def _is_true(v): return v is True
def _is_false(v): return v is False
def _is_zero(v): return isinstance(v, int) and not isinstance(v, bool) and v == 0


def _load(evidence_dir, name):
    p = os.path.join(evidence_dir, name)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def verify(evidence_dir):
    crit = {}
    notes = {}

    ledger_path = os.path.join(evidence_dir, LE.LEDGER)
    central_dir = os.path.join(evidence_dir, LE.CENTRAL_DIR)

    checkout = _load(evidence_dir, LE.F_CHECKOUT)
    workflows = _load(evidence_dir, LE.F_WORKFLOWS)
    central = _load(evidence_dir, LE.F_CENTRAL)
    replay = _load(evidence_dir, LE.F_REPLAY)
    autonomy = _load(evidence_dir, LE.F_AUTONOMY)
    concurrency = _load(evidence_dir, LE.F_CONCURRENCY)
    crash = _load(evidence_dir, LE.F_CRASH)
    poc = _load(evidence_dir, LE.F_POC)
    drive = _load(evidence_dir, LE.F_DRIVE)
    agg = _load(evidence_dir, LE.F_AGG)

    # ---- SHA pinning: requested == checked-out, both 40-hex ----
    if not checkout:
        crit["CHECKED_OUT_SHA_MATCHES_REQUEST"] = False
        notes["checkout"] = "MISSING"
    else:
        req = checkout.get("requested", ""); got = checkout.get("CHECKED_OUT_SHA", "")
        crit["CHECKED_OUT_SHA_MATCHES_REQUEST"] = bool(SHA40.match(req or "") and req == got)
        notes["checkout"] = {"requested": req, "CHECKED_OUT_SHA": got}

    # ---- ledger append-only + chain valid (re-derived from the live ledger itself) ----
    if not os.path.exists(ledger_path):
        crit["EVENT_LEDGER_APPEND_ONLY"] = False
        crit["EVENT_LEDGER_CHAIN_VALID"] = False
        notes["ledger"] = "MISSING"
        lg = None
    else:
        lg = open_ledger(ledger_path)
        recs = lg.read_all()
        crit["EVENT_LEDGER_APPEND_ONLY"] = bool(len(recs) > 0
                                                and all(r.get("ledger_seq") == i for i, r in enumerate(recs))
                                                and all("prev_ledger_hash" in r and "ledger_hash" in r for r in recs))
        try:
            crit["EVENT_LEDGER_CHAIN_VALID"] = bool(lg.verify_chain())
        except Exception as e:
            crit["EVENT_LEDGER_CHAIN_VALID"] = False
            notes["chain"] = repr(e)

    # ---- central store: independently re-read HEAD file and recompute SHA (no trust in booleans) ----
    head = None
    if os.path.isdir(central_dir):
        cp = CentralPersistence(SharedVolumeBackend(central_dir))
        head = cp.read_head()
        if head:
            raw = cp.backend.get_bytes(head["file"])
            recomputed = hashlib.sha256(raw).hexdigest()
            crit["CENTRAL_WRITE_READBACK_VERIFIED"] = bool(recomputed == head.get("sha256"))
            crit["CENTRAL_READBACK_SHA_MATCH"] = bool(recomputed == head.get("sha256") and len(head.get("sha256", "")) == 64)
            crit["REAL_CENTRAL_PERSISTENCE_OBSERVED"] = bool(recomputed == head.get("sha256"))
            notes["central_head"] = {"file": head.get("file"), "sha256": head.get("sha256")}
        else:
            crit["CENTRAL_WRITE_READBACK_VERIFIED"] = False
            crit["CENTRAL_READBACK_SHA_MATCH"] = False
            crit["REAL_CENTRAL_PERSISTENCE_OBSERVED"] = False
            notes["central_head"] = "NO_HEAD"
    else:
        crit["CENTRAL_WRITE_READBACK_VERIFIED"] = False
        crit["CENTRAL_READBACK_SHA_MATCH"] = False
        crit["REAL_CENTRAL_PERSISTENCE_OBSERVED"] = False
        notes["central_head"] = "NO_CENTRAL_DIR"

    # ---- replay == master, re-derived from the live ledger vs the persisted central HEAD ----
    if lg is not None and head is not None:
        cp = CentralPersistence(SharedVolumeBackend(central_dir))
        persisted = cp.read_current()
        try:
            ok, detail = state_model.verify_replay(lg, persisted) if persisted else (False, "NO_PERSISTED")
        except Exception as e:
            ok, detail = False, "DERIVE_FAILED:%r" % e   # tampered/broken ledger -> fail closed
        crit["STATE_REPLAY_MATCHES_MASTER"] = bool(ok)
        crit["STATE_VERSION_MONOTONIC"] = bool(persisted and persisted.get("state_version", 0) > 0
                                               and head.get("state_version") == persisted.get("state_version"))
        notes["replay"] = detail
    else:
        crit["STATE_REPLAY_MATCHES_MASTER"] = False
        crit["STATE_VERSION_MONOTONIC"] = False

    # ---- stale write rejected (from central evidence, must be explicit true) ----
    crit["STALE_WRITE_REJECTED"] = bool(central and _is_true(central.get("STALE_WRITE_REJECTED")))

    # ---- REAL Google Shared Drive persistence (a shared volume can NEVER satisfy this) ----
    crit["REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"] = bool(LE.drive_persistence_observed(drive))
    if not crit["REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"]:
        notes["drive"] = {"present": bool(drive),
                          "backend_type": (drive or {}).get("backend_type"),
                          "drive_id": (drive or {}).get("drive_id")}

    # ---- concurrency: double-claim 0, loser refused with no side effect; stale-lease reclaim PASS ----
    if not concurrency:
        crit["CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO"] = False
        crit["STALE_LEASE_RECLAIM"] = False
        notes["concurrency"] = "MISSING"
    else:
        crit["CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO"] = bool(
            _is_zero(concurrency.get("CONCURRENT_DOUBLE_CLAIM_COUNT"))
            and concurrency.get("loser_outcome") == "NOT_CLAIMED"
            and concurrency.get("loser_side_effects") == 0)
        crit["STALE_LEASE_RECLAIM"] = bool(concurrency.get("STALE_LEASE_RECLAIM") == "PASS")

    # ---- autonomy / gating / relay / fabricated-approval ----
    if not autonomy:
        for k in ("AUTONOMOUS_NEXT_TASK", "WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE",
                  "HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE", "NO_APPROVAL_FABRICATED"):
            crit[k] = False
        notes["autonomy"] = "MISSING"
    else:
        crit["AUTONOMOUS_NEXT_TASK"] = bool(autonomy.get("AUTONOMOUS_NEXT_TASK") == "PASS")
        crit["WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE"] = bool(_is_false(autonomy.get("WAITING_WORKFLOW_BLOCKS_OTHER_WORK")))
        crit["HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE"] = bool(_is_false(autonomy.get("HUMAN_MESSAGE_RELAY_REQUIRED")))
        crit["NO_APPROVAL_FABRICATED"] = bool(_is_true(autonomy.get("NO_APPROVAL_FABRICATED")))

    # ---- real Temporal workflows observed: nonempty workflow_id AND run_id for every task ----
    crit["REAL_TEMPORAL_WORKFLOWS_OBSERVED"] = bool(
        workflows and all(isinstance(workflows.get(t), dict)
                          and workflows[t].get("workflow_id") and workflows[t].get("run_id")
                          for t in TASKS))
    if not crit["REAL_TEMPORAL_WORKFLOWS_OBSERVED"]:
        notes["workflows"] = "MISSING_OR_INCOMPLETE"

    # ---- duplicate side effects across all live activity (crash matrix cells) ----
    if not crash:
        crit["DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO"] = False
        notes["crash"] = "MISSING"
    else:
        dup = max([c.get("DUPLICATE_SIDE_EFFECT_COUNT", 1) for c in crash.values()] + [0])
        crit["DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO"] = bool(_is_zero(dup))
        notes["duplicate_side_effect_max"] = dup

    # ---- crash/recovery matrix: all six cases present and each proves the five sub-facts ----
    matrix = {}
    matrix_ok = bool(crash)
    for case in LE.CRASH_CASES:
        cell = (crash or {}).get(case)
        if not isinstance(cell, dict):
            matrix[case] = {"present": False, "PASS": False}
            matrix_ok = False
            continue
        cpass = (_is_true(cell.get("RECOVERY_OBSERVED")) and _is_true(cell.get("STATE_RECONCILED"))
                 and _is_true(cell.get("NO_LOST_COMPLETED_WORK")) and _is_zero(cell.get("DUPLICATE_SIDE_EFFECT_COUNT"))
                 and _is_true(cell.get("NO_APPROVAL_FABRICATED")))
        matrix[case] = {"present": True, "PASS": bool(cpass)}
        matrix_ok = matrix_ok and cpass
    crit["CRASH_RECOVERY_MATRIX"] = bool(matrix_ok)

    # ---- teardown: all three fields must be boolean false (temporal infra + drive artifacts + combined) ----
    crit["TEMPORAL_POC_INFRA_REMAINING_IS_FALSE"] = bool(poc and _is_false(poc.get("TEMPORAL_POC_INFRA_REMAINING")))
    crit["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING_IS_FALSE"] = bool(poc and _is_false(poc.get("SHARED_DRIVE_TEST_ARTIFACTS_REMAINING")))
    crit["POC_INFRA_REMAINING_IS_FALSE"] = bool(poc and _is_false(poc.get("POC_INFRA_REMAINING")))

    # ---- NB-001: aggregate POC normalized to boolean false when teardown proves false ----
    nb001_closed = bool(agg and _is_false(agg.get("POC_INFRA_REMAINING"))
                        and crit["POC_INFRA_REMAINING_IS_FALSE"])
    crit["P0E2_NB_001_CLOSED"] = nb001_closed

    mandatory_all = all(bool(v) for v in crit.values())
    final = "PASS" if mandatory_all else "FAIL"
    failed = [k for k, v in crit.items() if not v]

    return {
        "gate": "P0E3_SLICE_2_LIVE_ACCEPTANCE",
        "criteria": crit,
        "crash_recovery_matrix": matrix,
        "notes": notes,
        "FINAL": final,
        "failed_criteria": failed,
        "P0E2_NB_001": "CLOSED" if nb001_closed else "OPEN",
        "PRODUCTION_DEPLOYMENT_AUTHORIZED": False,
        "PUBLICATION_AUTHORIZED": False,
        "FIRST_REAL_POSTER": "PAUSED_BY_NITIN",
    }


def main():
    ap_dir = None
    args = sys.argv[1:]
    if "--evidence" in args:
        ap_dir = args[args.index("--evidence") + 1]
    if not ap_dir:
        raise SystemExit("usage: live_acceptance_p0e3.py --evidence DIR")
    v = verify(ap_dir)
    out = os.path.join(ap_dir, "P0E3_LIVE_ACCEPTANCE_VERDICT.json")
    json.dump(v, open(out, "w"), indent=2, sort_keys=True)
    print(json.dumps({"FINAL": v["FINAL"], "failed_criteria": v["failed_criteria"]}, indent=2))
    print("wrote", out)
    sys.exit(0 if v["FINAL"] == "PASS" else 1)


if __name__ == "__main__":
    main()
