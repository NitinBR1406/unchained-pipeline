"""Additive V16.20 recovery for the malformed V16.19 engineering ledger.

The historical ledger is never edited.  Recovery copies its last valid prefix,
re-appends the three well-formed semantic events with canonical hashes, and
quarantines the trailing non-event by content hash.  A final typed recovery
event makes the repair explicit before a deterministic state projection.
"""
import copy
import hashlib
import json
from pathlib import Path

import handoff as h
from control_plane.events import input_hash, is_wellformed
from control_plane.ledger import EventLedger, LedgerError
from control_loop.state_model import derive
from integration.contracts import digest, require

ROOT = h.ROOT
SOURCE_DIR = ROOT / "p0e4/evidence/continuous_rhythm_claude_reuse_v01_execution"
SOURCE_LEDGER = SOURCE_DIR / "ENGINEERING_EVENT_LEDGER.jsonl"
VALID_PREFIX = ROOT / "p0e4/evidence/resolve_native_rhythm_study_v01_execution/ENGINEERING_EVENT_LEDGER.jsonl"
PARENT = SOURCE_DIR / "UNCHAINED_MASTER_PROJECT_STATE_V16_19.json"
OUT = ROOT / "p0e4/evidence/master_state_integrity_recovery_v1620"
BROKEN_LEDGER_SHA256 = "7c9b1ff4b674ff36e52e721993d54a5967c7a3dc5bb189d8d60c95960a0d8cc7"
PARENT_SHA256 = "e25717a8a74a243c18916d5beadce7c9b72341d7d65af779518bfffc1756d55f"
RECOVERED_EVENT_INDEXES = (31, 32, 33)
RECOVERY_TIMESTAMP = "2026-09-29T19:45:00Z"


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _load_records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _strip_envelope(record):
    return {k: v for k, v in record.items() if k not in ("ledger_seq", "prev_ledger_hash", "ledger_hash")}


def forensic_report():
    source = _load_records(SOURCE_LEDGER)
    prefix = _load_records(VALID_PREFIX)
    require(digest(SOURCE_LEDGER.read_bytes()) == BROKEN_LEDGER_SHA256, "broken ledger drift")
    require(len(prefix) == 31 and source[:31] == prefix, "last valid prefix drift")
    failures = []
    try:
        EventLedger(str(SOURCE_LEDGER)).verify_chain()
    except LedgerError as exc:
        failures.append(str(exc))
    require(failures == ["tamper detected at seq 31"], "unexpected source failure")
    tail = []
    for index in RECOVERED_EVENT_INDEXES:
        record = source[index]
        tail.append({
            "index": index,
            "event_id": record["event_id"],
            "wellformed": is_wellformed(record),
            "input_hash_matches": record.get("input_hash") == input_hash(record.get("inputs")),
            "record_sha256": hashlib.sha256(_canonical_bytes(record)).hexdigest(),
        })
    malformed = source[34]
    return {
        "schema": "MASTER_STATE_LEDGER_FORENSIC_V01",
        "schema_version": 1,
        "source_ledger": str(SOURCE_LEDGER.relative_to(ROOT)),
        "source_ledger_sha256": BROKEN_LEDGER_SHA256,
        "last_valid_index": 30,
        "last_valid_event_id": source[30]["event_id"],
        "last_valid_ledger_hash": source[30]["ledger_hash"],
        "first_failure": "tamper detected at seq 31",
        "tail_records": tail,
        "malformed_index": 34,
        "malformed_record_sha256": hashlib.sha256(_canonical_bytes(malformed)).hexdigest(),
        "malformed_record": malformed,
        "historical_source_mutated": False,
        "pointer_target_sha_matches": digest(PARENT.read_bytes()) == PARENT_SHA256,
        "pointer_sidecar_actual_before_recovery": digest((ROOT / "p0e4/MASTER_STATE_LATEST.json").read_bytes()),
        "pointer_sidecar_recorded_before_recovery": (ROOT / "p0e4/MASTER_STATE_LATEST.sha256").read_text().split()[0],
    }


def build_recovered_ledger(path):
    report = forensic_report()
    source = _load_records(SOURCE_LEDGER)
    prefix_bytes = VALID_PREFIX.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(prefix_bytes)
    require(path.read_bytes().startswith(prefix_bytes), "recovery prefix drift")
    ledger = EventLedger(str(path))
    existing = ledger.read_all()
    if len(existing) == 31:
        for index in RECOVERED_EVENT_INDEXES:
            event = _strip_envelope(source[index])
            event["input_hash"] = input_hash(event.get("inputs"))
            require(is_wellformed(event), "recovered semantic event malformed")
            ledger.append(event)
        recovery_inputs = {
            "status": "ADDITIVE_LEDGER_RECOVERY_ACCEPTED",
            "source_ledger_sha256": BROKEN_LEDGER_SHA256,
            "valid_prefix_records": 31,
            "recovered_event_ids": [source[i]["event_id"] for i in RECOVERED_EVENT_INDEXES],
            "malformed_record_index": 34,
            "malformed_record_sha256": report["malformed_record_sha256"],
            "malformed_record_replayed": False,
            "historical_ledger_mutated": False,
            "production_deployment_authorized": False,
            "publication_authorized": False,
            "first_real_poster": "PAUSED_BY_NITIN",
        }
        ledger.append(h.make_event("p0e4-v1620-master-integrity-recovery", "EVIDENCE_REGISTERED",
                                   RECOVERY_TIMESTAMP, "codex", inputs=recovery_inputs))
    ledger.verify_chain()
    require(len(ledger.read_all()) == 35, "recovery event count")
    return ledger


def project(parent_bytes, ledger):
    require(digest(parent_bytes) == PARENT_SHA256, "V16.19 parent drift")
    reduced = derive(ledger, keyring={})
    require(reduced["state_version"] == 35, "recovery reducer transition count")
    records = ledger.read_all()
    recovery = records[-1]["inputs"]
    state = json.loads(parent_bytes)
    authorizations = copy.deepcopy(state["authorizations"])
    state.update(
        state_version=46,
        updated_at=records[-1]["timestamp"],
        updated_by="codex",
        milestone="P0-E4 autonomous intake control verified; Master State ledger integrity recovered additively",
    )
    state["p0e4"]["master_state_integrity_recovery_v1620"] = copy.deepcopy(recovery)
    state["p0e4"]["autonomous_intake_control"] = {
        "task_id": "EC_CONTROL_INTAKE_RECEIPT_V01",
        "status": "COMPLETED",
        "scope": "NON_PRODUCTION_CONTROLLER_SELF_TEST",
        "always_on_dispatcher_proven": False,
        "stored_request_auto_start_proven": False,
        "publication_authorized": False,
    }
    state["state_lineage"] = {
        "parent_version": 45,
        "parent_sha256": PARENT_SHA256,
        "engineering_ledger_head_hash": reduced["ledger_head_hash"],
        "engineering_transition_count": reduced["state_version"],
        "recovered_from_ledger_sha256": BROKEN_LEDGER_SHA256,
    }
    require(state["authorizations"] == authorizations, "authority changed")
    require(authorizations["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is False, "deployment gate")
    require(authorizations["PUBLICATION_AUTHORIZED"] is False, "publication gate")
    require(state["production_state"]["first_real_poster"] == "PAUSED_BY_NITIN", "poster gate")
    return state


def generate(tested_sha):
    OUT.mkdir(parents=True, exist_ok=True)
    report = forensic_report()
    (OUT / "FORENSIC_REPORT_V01.json").write_bytes(_canonical_bytes(report))
    ledger = build_recovered_ledger(OUT / "ENGINEERING_EVENT_LEDGER.jsonl")
    state = project(PARENT.read_bytes(), ledger)
    state["p0e4"]["master_state_integrity_recovery_v1620"]["tested_sha"] = tested_sha
    state_bytes = json.dumps(state, sort_keys=True, indent=2).encode() + b"\n"
    (OUT / "UNCHAINED_MASTER_PROJECT_STATE_V16_20.json").write_bytes(state_bytes)
    replay = project(PARENT.read_bytes(), ledger)
    replay["p0e4"]["master_state_integrity_recovery_v1620"]["tested_sha"] = tested_sha
    require(json.dumps(replay, sort_keys=True, indent=2).encode() + b"\n" == state_bytes, "non-deterministic replay")
    return report, ledger, state


if __name__ == "__main__":
    import subprocess
    tested = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report, ledger, state = generate(tested)
    print(json.dumps({"status": "RECOVERED", "state_version": state["state_version"],
                      "ledger_head_hash": ledger.read_all()[-1]["ledger_hash"], "tested_sha": tested}))
