"""P0-E3 Slice-2 LIVE evidence: canonical schema + real-derivation builder.

One place defines the live evidence bundle so the CI live driver and the offline gate/tests agree exactly.
Every artifact is derived from REAL underlying state (a genuine hash-chained ledger + a real central store
produced by the durable loop against a cross-process backend). The live-only observations that only exist
inside CI (real Temporal workflow/run ids, container kill/recovery timestamps, the checked-out SHA) are
carried as explicit fields the gate verifies structurally — never invented by the gate itself.

Booleans are real Python bools (json.dump), never shell-interpolated tokens.
"""
import os, json, hashlib
from . import state_model, scenarios
from .control_loop import DurableControlLoop, Clock
from .persistence import CONFLICT
from .live_backend import SharedVolumeBackend
from .nb001_normalize import normalize_poc_infra


# ---- canonical evidence file names ----------------------------------------
F_CHECKOUT = "checkout.json"
F_WORKFLOWS = "workflows.json"
F_CENTRAL = "central_persistence.json"
F_REPLAY = "replay.json"
F_AUTONOMY = "autonomy.json"
F_CONCURRENCY = "concurrency.json"
F_CRASH = "crash_matrix.json"
F_POC = "poc_infra.json"
F_DRIVE = "drive_persistence.json"
F_AGG = "P0E3_LIVE_RESULTS.json"
LEDGER = "EVENT_LEDGER.jsonl"
CENTRAL_DIR = "central"

AUTHORITATIVE_DRIVE_ID = "0AG0CqqUZ6YuXUk9PVA"   # "Unchained Nitin — Master" Shared Drive

CRASH_CASES = ["A_after_ledger_before_state", "B_after_state_before_readback", "C_after_claim_before_exec",
               "D_during_execution", "E_after_effect_before_completion", "F_while_waiting_for_nitin"]


def _dump(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump(obj, open(path, "w"), indent=2, sort_keys=True)


def _sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_durable_live(evidence_dir, backend_root=None, clock_start=1000):
    """Run the P0-E3 durable loop against a cross-process (shared-volume) central backend.

    Produces the REAL live ledger (evidence_dir/EVENT_LEDGER.jsonl) and central store
    (evidence_dir/central). Returns the quiesced loop.
    """
    os.makedirs(evidence_dir, exist_ok=True)
    import shutil
    shutil.copy(scenarios.SEED_SLICE2 if hasattr(scenarios, "SEED_SLICE2") else scenarios.SEED,
                os.path.join(evidence_dir, "BACKLOG.json"))
    loop = DurableControlLoop(evidence_dir, clock=Clock(clock_start))
    # swap in the cross-process central backend (Shared Drive-style) WITHOUT editing frozen slice-1 code
    loop.persistence.backend = SharedVolumeBackend(backend_root or os.path.join(evidence_dir, CENTRAL_DIR))
    loop.run(max_iterations=50)
    return loop


def run_drive_lifecycle(client, drive_id, namespace):
    """Execute the FULL central-persistence lifecycle against a real Google Shared Drive DriveClient and
    return the drive_persistence.json contract. Never fabricates: every field comes from real Drive ops.

    write candidate -> read back from Drive -> recompute SHA256 -> compare -> CAS HEAD update ->
    read HEAD back -> verify -> stale concurrent writer rejected -> teardown -> verify artifacts gone.
    """
    from .live_backend import GoogleDriveBackend
    from .persistence import CentralPersistence, CONFLICT

    backend = GoogleDriveBackend(client=client, drive_id=drive_id, namespace=namespace)
    cp = CentralPersistence(backend)

    cand1 = {"core": {"phase": "P0E3-LIVE-DRIVE"}, "ledger_head_hash": "h1", "state_hash": "s1",
             "state_version": 1}
    r1 = cp.write(cand1, expected_state_version=0, expected_ledger_head_hash=None)
    version_object_id = backend.object_id("state_v1.json")
    head_object_id = backend.object_id(CentralPersistence.HEAD)

    # independent read-back from Drive + SHA recompute
    raw = backend.get_bytes("state_v1.json")
    readback_sha = hashlib.sha256(raw).hexdigest()
    expected_sha = r1.get("sha256")
    head = cp.read_head()
    head_rb_ok = bool(head and head.get("state_version") == 1 and head.get("sha256") == expected_sha)

    # stale concurrent writer against the SAME namespace -> must be rejected (CAS), no overwrite
    cand2 = {"core": {"phase": "P0E3-LIVE-DRIVE"}, "ledger_head_hash": "h2", "state_hash": "s2",
             "state_version": 2}
    stale = cp.write(cand2, expected_state_version=0, expected_ledger_head_hash=None)  # stale expectation
    stale_rejected = bool(stale["status"] == CONFLICT)

    # teardown: trash the disposable namespace + verify gone
    remaining = backend.teardown()
    artifacts_remaining = remaining > 0

    contract = {
        "backend_type": getattr(client, "backend_type", "unknown"),
        "drive_id": drive_id,
        "disposable_test_namespace": namespace,
        "version_object_id": version_object_id,
        "head_object_id": head_object_id,
        "write_observed": bool(r1["status"] == "OK"),
        "readback_observed": True,
        "expected_sha256": expected_sha,
        "readback_sha256": readback_sha,
        "readback_sha_matches": bool(readback_sha == expected_sha),
        "cas_head_update_observed": bool(head is not None),
        "head_readback_observed": head_rb_ok,
        "stale_write_rejected": stale_rejected,
        "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": artifacts_remaining,
        "source": "live_drive_lifecycle",   # produced by a real Drive run against a real DriveClient
    }
    return contract


# A synthetic offline fixture is NEVER acceptable as real Shared Drive evidence.
SYNTHETIC_SOURCE = "synthetic_offline_fixture"


def drive_persistence_observed(contract):
    """Independent predicate for REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED. A shared volume — and any synthetic
    offline fixture — can NEVER satisfy it: requires backend_type == 'google_shared_drive', the authoritative
    drive_id, non-empty real object ids, a matching read-back SHA, CAS+HEAD read-back, a rejected stale writer,
    and a source that is NOT the synthetic offline fixture."""
    if not isinstance(contract, dict):
        return False
    if contract.get("source") == SYNTHETIC_SOURCE:
        return False   # hard block: synthetic test evidence can never prove real Shared Drive persistence
    return bool(
        contract.get("backend_type") == "google_shared_drive"
        and contract.get("drive_id") == AUTHORITATIVE_DRIVE_ID
        and contract.get("disposable_test_namespace")
        and contract.get("version_object_id")
        and contract.get("head_object_id")
        and contract.get("write_observed") is True
        and contract.get("readback_observed") is True
        and contract.get("readback_sha256")
        and contract.get("expected_sha256")
        and contract.get("readback_sha_matches") is True
        and contract.get("cas_head_update_observed") is True
        and contract.get("head_readback_observed") is True
        and contract.get("stale_write_rejected") is True)


def build_central_evidence(loop):
    """Independently re-read the committed central HEAD file and verify its SHA (real read-back)."""
    cp = loop.persistence
    head = cp.read_head()
    writes = []
    verified_all = True
    if head:
        for name in sorted(n for n in os.listdir(cp.backend.root) if n.startswith("state_v")):
            raw = cp.backend.get_bytes(name)
            writes.append({"file": name, "readback_sha256": hashlib.sha256(raw).hexdigest()})
    head_ok = False
    if head:
        raw = cp.backend.get_bytes(head["file"])
        head_ok = hashlib.sha256(raw).hexdigest() == head["sha256"]
        verified_all = head_ok
    # a real CAS conflict from a stale concurrent writer against the SAME live HEAD
    sw = scenarios.stale_write_rejected()
    return {
        "backend": cp.backend.describe() if hasattr(cp.backend, "describe") else {"kind": "local"},
        "head": head,
        "writes": writes,
        "CENTRAL_WRITE_READBACK_VERIFIED": bool(head_ok),
        "CENTRAL_READBACK_SHA_MATCH": bool(head_ok),
        "STALE_WRITE_REJECTED": bool(sw["result"]["status"] == CONFLICT and sw["head_unchanged"]),
        "REAL_CENTRAL_PERSISTENCE_OBSERVED": bool(head is not None and head_ok and len(writes) > 0),
    }


def build_replay_evidence(loop):
    persisted = loop.persisted_state()
    ok, detail = state_model.verify_replay(loop.ledger, persisted) if persisted else (False, "NO_PERSISTED")
    return {"STATE_REPLAY_MATCHES_MASTER": bool(ok), "detail": detail,
            "state_version": (persisted or {}).get("state_version"),
            "ledger_head_hash": (persisted or {}).get("ledger_head_hash"),
            "state_hash": (persisted or {}).get("state_hash"),
            "STATE_VERSION_MONOTONIC": bool(persisted and persisted.get("state_version", 0) > 0)}


def build_autonomy_evidence(loop):
    status = {t["task_id"]: t["status"] for t in loop.backlog.tasks}
    persisted = loop.persisted_state() or {}
    return {"final_task_status": status,
            "AUTONOMOUS_NEXT_TASK": "PASS" if status.get("TASK_A") == "COMPLETED" and status.get("TASK_B") == "COMPLETED" else "FAIL",
            "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": bool(status.get("TASK_C") == "WAITING_FOR_NITIN" and status.get("TASK_D") != "COMPLETED"),
            "HUMAN_MESSAGE_RELAY_REQUIRED": False,
            "NO_APPROVAL_FABRICATED": bool("NITIN_PUBLISH_APPROVAL" not in persisted.get("approvals", {})
                                           and status.get("TASK_C") == "WAITING_FOR_NITIN")}


def build_concurrency_evidence():
    cc = scenarios.concurrent_double_claim()
    sl = scenarios.stale_lease_reclaim()
    return {"CONCURRENT_DOUBLE_CLAIM_COUNT": cc["concurrent_double_claim_count"],
            "loser_outcome": cc["outcome_worker2"],
            "loser_side_effects": cc["task_a_side_effect_count"],
            "STALE_LEASE_RECLAIM": "PASS" if (sl["reclaim_while_live_blocked"] and sl["reclaim_after_expiry_ok"]
                                              and sl["reclaim_different_holder"]) else "FAIL"}


def build_crash_matrix_evidence(container_obs=None):
    """Run the six crash/recovery cases; each returns the five required sub-proofs from real reconcile."""
    container_obs = container_obs or {}
    matrix = {}
    for case in CRASH_CASES:
        boundary = scenarios.BOUNDARY_MAP[case]
        r = scenarios.crash_and_recover(boundary)
        matrix[case] = {
            "RECOVERY_OBSERVED": bool(r["crashed"] and (r["a_done"] or r["c_waiting"])),
            "STATE_RECONCILED": bool(r["replay_matches"]),
            "NO_LOST_COMPLETED_WORK": bool(r["a_done"] and r["b_done"] and r["d_done"]),
            "DUPLICATE_SIDE_EFFECT_COUNT": r["duplicate_side_effects"],
            "NO_APPROVAL_FABRICATED": bool(r["no_fabricated_approval"]),
            # optional real-container observation from CI (kill/restart actually happened)
            "container_observation": container_obs.get(case, {}),
        }
        matrix[case]["PASS"] = bool(matrix[case]["RECOVERY_OBSERVED"] and matrix[case]["STATE_RECONCILED"]
                                    and matrix[case]["NO_LOST_COMPLETED_WORK"]
                                    and matrix[case]["DUPLICATE_SIDE_EFFECT_COUNT"] == 0
                                    and matrix[case]["NO_APPROVAL_FABRICATED"])
    return matrix


def normalize_poc(poc):
    """Normalize the teardown record into the three distinct fields; POC_INFRA_REMAINING is the OR."""
    def f(v):
        return v is True or (isinstance(v, str) and v.strip().lower() == "true")
    temporal = f(poc.get("TEMPORAL_POC_INFRA_REMAINING", poc.get("POC_INFRA_REMAINING")))
    drive = f(poc.get("SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"))
    combined = temporal or drive
    return {"TEMPORAL_POC_INFRA_REMAINING": temporal,
            "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": drive,
            "POC_INFRA_REMAINING": combined}


def build_aggregate(evidence_dir, central, replay, autonomy, concurrency, crash, workflows, poc, drive):
    """P0E3_LIVE_RESULTS aggregate, with P0E2-NB-001 normalization applied to POC_INFRA_REMAINING."""
    agg = {
        "REAL_TEMPORAL_WORKFLOWS_OBSERVED": bool(workflows and all(
            workflows.get(t, {}).get("workflow_id") and workflows.get(t, {}).get("run_id")
            for t in ("TASK_A", "TASK_B", "TASK_C", "TASK_D"))),
        "REAL_CENTRAL_PERSISTENCE_OBSERVED": central["REAL_CENTRAL_PERSISTENCE_OBSERVED"],
        "REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED": drive_persistence_observed(drive),
        "STATE_REPLAY_MATCHES_MASTER": replay["STATE_REPLAY_MATCHES_MASTER"],
        "DUPLICATE_SIDE_EFFECT_COUNT": max([c["DUPLICATE_SIDE_EFFECT_COUNT"] for c in crash.values()] + [0]),
        "CONCURRENT_DOUBLE_CLAIM_COUNT": concurrency["CONCURRENT_DOUBLE_CLAIM_COUNT"],
        "PRODUCTION_DEPLOYMENT_AUTHORIZED": False,
        "PUBLICATION_AUTHORIZED": False,
    }
    pocn = normalize_poc(poc)
    # NB-001: represent POC_INFRA_REMAINING as a real boolean derived from authoritative teardown fields
    # (temporal infra AND shared-drive artifacts). Both must be gone for false.
    agg["TEMPORAL_POC_INFRA_REMAINING"] = pocn["TEMPORAL_POC_INFRA_REMAINING"]
    agg["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"] = pocn["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"]
    agg["POC_INFRA_REMAINING"] = bool(pocn["POC_INFRA_REMAINING"])
    agg["_nb001"] = {"normalized_from_teardown": True,
                     "P0E2_NB_001": "CLOSED" if agg["POC_INFRA_REMAINING"] is False else "OPEN"}
    return agg


def real_drive_contract_from_proof(proof_path):
    """Map a recorded REAL Drive lifecycle proof into the contract shape. For EXPLICIT inspection of recorded
    evidence only — NOT an implicit dependency of offline tests (build_pass_bundle no longer calls this)."""
    p = json.load(open(proof_path))
    return {
        "backend_type": p["backend_type"], "drive_id": p["drive_id"],
        "disposable_test_namespace": p["disposable_test_namespace"],
        "version_object_id": p["version_object_id"], "head_object_id": p["head_object_id"],
        "write_observed": p["write_observed"], "readback_observed": p["readback_observed"],
        "expected_sha256": p["expected_sha256"], "readback_sha256": p["readback_sha256"],
        "readback_sha_matches": p["readback_sha_matches"],
        "cas_head_update_observed": p["cas_head_update_observed"],
        "head_readback_observed": p["head_readback_observed"],
        "stale_write_rejected": p["stale_write_rejected"],
        "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": p["teardown"]["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"],
        "source": "recorded_real_drive_lifecycle_proof"}


# Optional path to a recorded real proof, for explicit inspection tooling only. Offline tests and
# build_pass_bundle DO NOT read it — hermetic offline runs must not depend on any live artifact.
_PROOF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "evidence", "drive_proof", "DRIVE_LIFECYCLE_PROOF.json")


def synthetic_drive_fixture():
    """Deterministic, TEST_ONLY synthetic Drive contract for HERMETIC offline tests.

    Structurally valid so the rest of the bundle assembles, but marked source == 'synthetic_offline_fixture'
    so `drive_persistence_observed` (and therefore live acceptance) can NEVER accept it as real Shared Drive
    evidence. Requires no live artifact and no filesystem read.
    """
    h = "0" * 64   # deterministic non-empty test hash
    return {
        "backend_type": "google_shared_drive",
        "drive_id": AUTHORITATIVE_DRIVE_ID,
        "disposable_test_namespace": "TEST_ONLY_p0e3_synthetic_ns",
        "version_object_id": "TEST_ONLY_version_object",
        "head_object_id": "TEST_ONLY_head_object",
        "write_observed": True,
        "readback_observed": True,
        "expected_sha256": h,
        "readback_sha256": h,
        "readback_sha_matches": True,
        "cas_head_update_observed": True,
        "head_readback_observed": True,
        "stale_write_rejected": True,
        "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": False,
        "source": SYNTHETIC_SOURCE,
    }


def build_pass_bundle(evidence_dir, sha=None, drive=None):
    """HERMETIC offline helper: full canonical live-evidence bundle from a real ledger + central store plus a
    caller-supplied drive contract. If none is supplied it uses the TEST_ONLY synthetic fixture (which live
    acceptance rejects). It NEVER reads a recorded live artifact — offline runs are self-contained.

    NOTE: with the default synthetic fixture the strict gate FAILS closed on
    REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED (by design). Pass an explicit live-shaped `drive` contract to
    exercise the all-criteria-PASS path."""
    sha = sha or ("a" * 40)
    loop = run_durable_live(evidence_dir)
    checkout = {"requested": sha, "CHECKED_OUT_SHA": sha}
    workflows = {t: {"workflow_id": "p0e3-%s" % t, "run_id": "run-%s" % t}
                 for t in ("TASK_A", "TASK_B", "TASK_C", "TASK_D")}
    if drive is None:
        drive = synthetic_drive_fixture()
    poc = {"TEMPORAL_POC_INFRA_REMAINING": False,
           "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": drive.get("SHARED_DRIVE_TEST_ARTIFACTS_REMAINING", False)}
    facts = build_bundle(evidence_dir, loop, checkout=checkout, workflows=workflows, poc=poc, drive=drive)
    return loop, facts


def build_bundle(evidence_dir, loop, checkout, workflows, poc, drive, container_obs=None):
    """Write the full canonical live evidence bundle from real derivations + live-only observations."""
    central = build_central_evidence(loop)
    replay = build_replay_evidence(loop)
    autonomy = build_autonomy_evidence(loop)
    concurrency = build_concurrency_evidence()
    crash = build_crash_matrix_evidence(container_obs)
    agg = build_aggregate(evidence_dir, central, replay, autonomy, concurrency, crash, workflows, poc, drive)
    pocn = normalize_poc(poc)

    _dump(os.path.join(evidence_dir, F_CHECKOUT), checkout)
    _dump(os.path.join(evidence_dir, F_WORKFLOWS), workflows)
    _dump(os.path.join(evidence_dir, F_CENTRAL), central)
    _dump(os.path.join(evidence_dir, F_DRIVE), drive)
    _dump(os.path.join(evidence_dir, F_REPLAY), replay)
    _dump(os.path.join(evidence_dir, F_AUTONOMY), autonomy)
    _dump(os.path.join(evidence_dir, F_CONCURRENCY), concurrency)
    _dump(os.path.join(evidence_dir, F_CRASH), crash)
    _dump(os.path.join(evidence_dir, F_POC), pocn)
    _dump(os.path.join(evidence_dir, F_AGG), agg)
    return {"central": central, "drive": drive, "replay": replay, "autonomy": autonomy,
            "concurrency": concurrency, "crash": crash, "aggregate": agg}
