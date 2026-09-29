#!/usr/bin/env python3
"""Reproduce the 2026-09-30 no-change Master State checkpoint.

This script extends only the independent daily-audit checkpoint ledger.  It does
not mutate the recovered project ledger or the versioned Master State.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE_COMMIT = "18f9b21e2e31783dd6bbfaac8e245bac7121b327"
PREVIOUS_DAILY_COMMIT = "41d8b14560a7b87161d689bd460ce4b269149b65"
OBSERVED_AT = "2026-09-29T23:06:12Z"
PREVIOUS_DIR = ROOT / "p0e4/evidence/daily_master_audit_20260929"
RECOVERY_DIR = ROOT / "p0e4/evidence/master_state_integrity_recovery_v1620"

sys.path.insert(0, str(ROOT / "p0e4"))
import handoff as h  # noqa: E402
from control_plane.events import is_wellformed  # noqa: E402
from control_plane.ledger import EventLedger  # noqa: E402
from control_loop.state_model import derive  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{SOURCE_COMMIT}:{path}"], cwd=ROOT, text=True
    ).strip()


def source_ref(path: str, include_sha256: bool = True) -> dict:
    result = {"path": path, "git_blob_sha": git_blob(path)}
    if include_sha256:
        result["sha256"] = digest((ROOT / path).read_bytes())
    return result


def main() -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != SOURCE_COMMIT:
        raise RuntimeError(f"source HEAD drift: {head}")

    master_pointer = json.loads((ROOT / "p0e4/MASTER_STATE_LATEST.json").read_text())
    master_target = ROOT / master_pointer["path"]
    target_state = json.loads(master_target.read_text())
    pointer_sha = digest((ROOT / "p0e4/MASTER_STATE_LATEST.json").read_bytes())
    sidecar_expected = (ROOT / "p0e4/MASTER_STATE_LATEST.sha256").read_text().split()[0]
    if pointer_sha != sidecar_expected:
        raise RuntimeError("Master pointer sidecar mismatch")
    if digest(master_target.read_bytes()) != master_pointer["sha256"]:
        raise RuntimeError("Master target mismatch")

    checkpoint = {
        "schema": "DAILY_MASTER_RECONCILIATION_V01",
        "date": "2026-09-30",
        "timezone": "Europe/Amsterdam",
        "observed_at": OBSERVED_AT,
        "branch": "p0e4/slice1-production-handoff",
        "source_commit": SOURCE_COMMIT,
        "previous_daily_checkpoint_commit": PREVIOUS_DAILY_COMMIT,
        "result": "NO_MASTER_TRANSITION_PREMIUM_TRIAL_REPAIR_REQUIRED",
        "registered_master_version": master_pointer["master_state_version"],
        "registered_state_version": master_pointer["state_version"],
        "master_pointer_unchanged": True,
        "master_state_written": False,
        "master_replay_verified": True,
        "milestone_advanced": False,
        "changes_since_previous_daily_checkpoint": [
            "The branch advanced by 14 commits after the 2026-09-29 checkpoint commit and now resolves to 18f9b21e2e31783dd6bbfaac8e245bac7121b327.",
            "V13 was rendered as a 24-second 1080x1920 ProRes 422 HQ, 10-bit BT.2020 HLG private preview. Full audio/video decode passed, Shared Drive readback hashes matched and Gemini returned PASS with explicit HDR/lipsync limitations. Nitin final-video approval remains false.",
            "A bounded six-second premium style A/B sample was executed. The corrected Gemini review recommends B_EDITORIAL_RESTRAINT for Nitin review, but no creative winner or template freeze was recorded and the excerpt does not prove full-clip coverage.",
            "The malformed V16.19 lineage was recovered additively. MASTER_STATE_LATEST now points to V16.20/state_version 46, its pointer sidecar and target hash match, and deterministic replay is recorded as verified.",
            "New C0/C1/C2 and T1/T2/T3 premium trials were rendered and persisted. Independent review then proved two high-severity output defects: C1/C2 leave 131 of 360 comparison frames ungraded, and every caption variant overlaps the chain-logo intro. Strict Fusion import/active-comp/readback proof is also missing.",
            "The defective premium comparisons were not re-rendered, no C/T choice was inferred, and no final candidate was combined."
        ],
        "proven_results": [
            "The recovered central ledger contains 35 valid chained records and replays to state_version 46 through the recorded V16.20 projection.",
            "The Master pointer SHA-256 sidecar now matches the pointer bytes, and the pointer target matches the V16.20 state SHA-256.",
            "All 44 entries across the V16.20 recovery, V13 repair, premium-style sample and premium-QC manifests were verified against repository bytes.",
            "The three focused recovery/executor/state suites ran 19 tests and passed 19/19 on source commit 18f9b21e2e31783dd6bbfaac8e245bac7121b327.",
            "Targeted Shared Drive listings confirm 12 V13 handoff items and 26 premium-QC trial items remain present; no Drive write was performed by this audit."
        ],
        "blockers": [
            "The current C1/C2 comparison is invalid for selection because approximately 36% of each compared segment did not receive the new grade.",
            "All T1/T2/T3 caption candidates collide with the approved gold UN broken-chain intro; the class of defect previously rejected by Nitin is therefore present again.",
            "Caption import/readback does not yet prove that the patched Fusion composition was active in the render.",
            "The existing heartbeat is not proven to invoke engineering.py automatically for newly committed READY tasks; changing that binding still requires explicit Nitin change approval.",
            "Composition/publishing, synchronization/publication permissions and contributor credits remain unresolved.",
            "Final-video, publication and production-deployment approvals remain false."
        ],
        "human_gates": [
            "After bounded repairs and exact-file re-QC, Nitin chooses C0/C1/C2 and T1/T2/T3 or rejects the set; no choice is currently recorded.",
            "NITIN_FINAL_VIDEO_APPROVAL must bind the exact accepted file SHA-256.",
            "Rights/credits clearance and separate NITIN_PUBLISH_APPROVAL remain required; deployment is separately unauthorized.",
            "Any heartbeat/autostart configuration change remains a separate NITIN_CHANGE_APPROVAL."
        ],
        "next_ready_action": {
            "status": "READY_FOR_BOUNDED_PREMIUM_TRIAL_REPAIR_AND_REQC",
            "action": "On the existing Mac Resolve worker, patch only the proven defects: apply the selected C1/C2 grade state across the full comparison range, delay the opening hook until after the chain-logo window, and fail closed on Fusion import, active-comp and exact parameter readback. Re-render only the affected comparisons, persist exact hashes, then repeat local motion review plus Claude code review and Gemini exact-file QC before asking Nitin to choose.",
            "control_plane_parallel_hold": "Autostart binding remains WAITING_FOR_NITIN_CHANGE_APPROVAL; this checkpoint does not modify the heartbeat.",
            "this_run_scope": "Status/evidence reconciliation only; no heavy render, automation restart, publication or deployment."
        },
        "lessons_learned": [
            "Successful decode and correct colour metadata do not prove that a grade was applied to every rendered clip.",
            "A contact sheet and visible fonts do not prove that a replacement Fusion composition became active; API returns, comp identity and parameter readback must be asserted.",
            "Independent moving-video review caught the same logo/text collision that static technical checks had allowed through.",
            "AI preferences are non-promotable when the compared assets contain proven defects.",
            "Restoring ledger integrity permits reliable replay, but does not convert later experimental evidence into a completed creative gate."
        ],
        "governance": {
            "FIRST_REAL_POSTER": "PAUSED_BY_NITIN",
            "PUBLICATION_AUTHORIZED": False,
            "PRODUCTION_DEPLOYMENT_AUTHORIZED": False,
            "NITIN_FINAL_VIDEO_APPROVAL": False,
            "NITIN_PUBLISH_APPROVAL": False,
            "HLG_native_BT2020_minimum_10bit_preserved": True,
            "full_Dolby_Vision_display_identity_claimed": False,
            "frozen_P0_E0_E1_E2_E3_modified": False,
            "publications": 0,
            "deployments": 0,
            "full_master_rendered": False
        },
        "instructions_check": "Recursive 2,056-entry tracked source tree contains no AGENTS.md.",
        "drive_reconciliation_ref": "DRIVE_RECONCILIATION.json",
        "validation_ref": "VALIDATION.json",
        "project_memory": "PROJECT_NOTES_V06.json is a versioned repository handover supplement subordinate to state/evidence; no ChatGPT memory write was available or claimed.",
        "source_refs": [
            source_ref("p0e4/MASTER_STATE_LATEST.json"),
            source_ref("p0e4/MASTER_STATE_LATEST.sha256"),
            source_ref("p0e4/evidence/master_state_integrity_recovery_v1620/UNCHAINED_MASTER_PROJECT_STATE_V16_20.json"),
            source_ref("p0e4/evidence/master_state_integrity_recovery_v1620/ENGINEERING_EVENT_LEDGER.jsonl"),
            source_ref("p0e4/evidence/master_state_integrity_recovery_v1620/REPLAY_V01.json"),
            source_ref("p0e4/evidence/claude_edit_posting_handoff_review_v01_execution/v13_chain_caption_repair/NEXT_READY.json"),
            source_ref("p0e4/evidence/claude_edit_posting_handoff_review_v01_execution/premium_style_sample_v02/BUNDLED_REVIEW_PACKAGE_V02.json"),
            source_ref("p0e4/evidence/premium_qc_research_v01_execution/INDEPENDENT_REVIEW_BUNDLE_V01.json"),
            source_ref("p0e4/evidence/premium_qc_research_v01_execution/CLAUDE_TECHNICAL_REVIEW_V01.json"),
            source_ref("p0e4/evidence/premium_qc_research_v01_execution/GEMINI_INDEPENDENT_QC_V01.json"),
            source_ref("p0e4/evidence/daily_master_audit_20260929/DAILY_CHECKPOINT.json")
        ]
    }
    write_json(OUT / "DAILY_CHECKPOINT.json", checkpoint)

    drive = {
        "schema": "TARGETED_DRIVE_RECONCILIATION_V01",
        "observed_at": OBSERVED_AT,
        "drive": {"id": "0AG0CqqUZ6YuXUk9PVA", "name": "Unchained Nitin — Master"},
        "v13_chain_caption_repair": {
            "folder_id": "1OzXRrQZa2bHBAOf65alXOT7ouPL3WiDb",
            "folder_url": "https://drive.google.com/drive/folders/1OzXRrQZa2bHBAOf65alXOT7ouPL3WiDb",
            "item_count": 12,
            "master": {"id": "1b0HB-g2eqzbrmtxjEjxWM6ejap7kXcHF", "name": "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR_HLG_PRORES.mov", "size_bytes": 610459894, "sha256_from_repository_receipt": "7266506b3d9e5262ded0c579d664c2d6444e6c35c173cf00c062290810ffe088"},
            "review": {"id": "1uMtCO100ltM0mDK6brgVsO_0qMvWcVYj", "name": "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR_HLG.mp4", "size_bytes": 22053571, "sha256_from_repository_receipt": "b436eda79eadb289d4bbf7e5763eb2858c5eeef0ee13c7cb60f308c372664590"},
            "repository_receipt_reports_readback_hash_match": True,
            "nitin_approval": False
        },
        "premium_style_sample": {
            "review_file_id": "15HYhzTeTx99WmA5I8VTA3HV-FhseHDl-",
            "review_name": "AAKHRI_PREMIUM_STYLE_COMPARISON_V13_A_B_HLG.mp4",
            "size_bytes": 18847410,
            "modified_time": "2026-09-29T16:56:37.466Z",
            "folder_id": "1X36j_C3DmsFMo-jt4KytvEpfwnVbl1RP",
            "creative_winner_selected": False
        },
        "premium_qc_trials": {
            "folder_id": "15K2VTOzQpXQ3CZlJ4JeFNJyg9sFqZ-Ok",
            "folder_url": "https://drive.google.com/drive/folders/15K2VTOzQpXQ3CZlJ4JeFNJyg9sFqZ-Ok",
            "item_count": 26,
            "colour_r2_review": {"id": "1PoBzTJsIOaGY7LKP6M7neilRHSkAkGOz", "name": "AAKHRI_PREMIUM_COLOUR_COMPARISON_C0_C1_C2_PERFORMANCE_ONLY_R2_HLG_REVIEW.mp4", "size_bytes": 38521211, "modified_time": "2026-09-29T20:38:37.456Z", "sha256_from_repository_receipt": "6bb4fccd4d8c0c9eb7402515375d43afd841500d7c5bcc1928a45522db94c452"},
            "caption_review": {"id": "1fWYSg2gkeL-t3wUjYAPnM0IL08TffRdw", "name": "AAKHRI_PREMIUM_CAPTION_COMPARISON_T1_T2_T3_HLG_REVIEW.mp4", "size_bytes": 19001579, "modified_time": "2026-09-29T20:32:29.468Z", "sha256_from_repository_receipt": "680dde68786b30805d2585b9ff7551c6357872b115087b9bb9e5d63251fec73a"},
            "repository_receipt_reports_readback_hash_match": True,
            "independent_qc": "DEFECTS_FOUND_NO_PASS",
            "selection_valid": False
        },
        "result": "V13 and both premium trial packages are present. V13 is technically and independently reviewed but still awaits Nitin; the newest C/T comparisons are not valid for selection until the proven grade, overlap and readback defects are repaired and rechecked.",
        "scope_limit": "Read-only targeted metadata and folder listings. No media download, calibrated HDR audit, Drive write, publication or deployment."
    }
    write_json(OUT / "DRIVE_RECONCILIATION.json", drive)

    notes = {
        "schema": "PROJECT_NOTES_V06",
        "date": "2026-09-30",
        "source_commit": SOURCE_COMMIT,
        "authority": "Subordinate to versioned state and immutable evidence; supplements prior project notes.",
        "registered_master_state": "V16.20 / state_version 46 remains registered. Ledger integrity and pointer sidecar are recovered; no further promotion because the newest premium comparisons contain proven defects and no human choice was made.",
        "current_operational_status": "V13 exists and passed bounded technical/Gemini review but still awaits Nitin. The newer C/T comparison round is invalid for selection: C1/C2 are partly ungraded and T1/T2/T3 overlap the chain-logo intro.",
        "accepted_facts": [
            "V13 uses the approved gold UN broken-chain identity, preserves 10-bit BT.2020 HLG and has full A/V decode PASS.",
            "V13 exact-file Gemini QC is PASS with explicit browser/HDR/lipsync limitations; this is not Nitin approval.",
            "C1_WARM_CINEMATIC and T3_CINEMATIC_TITLE are provisional non-promotable preferences only.",
            "No corrected premium comparison or combined final candidate exists yet.",
            "Autostart binding remains unproven and unchanged."
        ],
        "do_not_claim": [
            "Do not call V13 final approved or publish ready.",
            "Do not ask Nitin to choose from the defective C/T comparisons.",
            "Do not promote C1 or T3 from provisional recommendation to selection.",
            "Do not claim calibrated HDR approval or sample-accurate lipsync from browser review.",
            "Do not claim ChatGPT memory was updated."
        ],
        "next_handoff": "Repair only the proven premium trial defects on the established Mac Resolve worker, verify exact active grade/comp state, re-render the affected comparisons, and repeat exact-file independent QC before Nitin chooses.",
        "governance": {"PUBLICATION_AUTHORIZED": False, "PRODUCTION_DEPLOYMENT_AUTHORIZED": False, "FIRST_REAL_POSTER": "PAUSED_BY_NITIN"},
        "chatgpt_memory_updated": False,
        "source_refs": "See DAILY_CHECKPOINT.json, VALIDATION.json and DRIVE_RECONCILIATION.json for exact commit, blob, SHA and Drive references."
    }
    write_json(OUT / "PROJECT_NOTES_V06.json", notes)

    validation = {
        "schema": "DAILY_MASTER_VALIDATION_V01",
        "source_commit": SOURCE_COMMIT,
        "branch_head_verified": True,
        "commits_after_previous_daily_checkpoint_commit": 14,
        "agents_md": {"recursive_tracked_entries_checked": 2056, "found": [], "tree_truncated": False},
        "master_pointer": {"path": "p0e4/MASTER_STATE_LATEST.json", "git_blob_sha": git_blob("p0e4/MASTER_STATE_LATEST.json"), "actual_sha256": pointer_sha, "sidecar_git_blob_sha": git_blob("p0e4/MASTER_STATE_LATEST.sha256"), "sidecar_expected_sha256": sidecar_expected, "sidecar_matches": True, "registered_master_version": master_pointer["master_state_version"], "registered_state_version": master_pointer["state_version"]},
        "master_target": {"path": master_pointer["path"], "git_blob_sha": git_blob(master_pointer["path"]), "sha256": digest(master_target.read_bytes()), "pointer_target_matches": True},
        "project_ledger": {"path": "p0e4/evidence/master_state_integrity_recovery_v1620/ENGINEERING_EVENT_LEDGER.jsonl", "git_blob_sha": git_blob("p0e4/evidence/master_state_integrity_recovery_v1620/ENGINEERING_EVENT_LEDGER.jsonl"), "sha256": digest((RECOVERY_DIR / "ENGINEERING_EVENT_LEDGER.jsonl").read_bytes()), "record_count": 35, "head_hash": "906dea5404d43195700a076bf8bb3bcde12e717da4ec8f070fe762c854bd7e23", "replay_verified": True, "projected_state_version": 46},
        "focused_tests": {"passed": 19, "total": 19, "suites": ["p0e4.tests.test_master_recovery_v1620", "p0e4.tests.test_engineering_executor", "p0e4.tests.test_state_update"], "run_on_source_commit": SOURCE_COMMIT},
        "manifests": {"master_state_integrity_recovery_v1620": {"entries_verified": 8, "result": "PASS"}, "v13_chain_caption_repair": {"entries_verified": 8, "result": "PASS"}, "premium_style_sample_v02": {"entries_verified": 12, "result": "PASS"}, "premium_qc_research_v01_execution": {"entries_verified": 16, "result": "PASS", "note": "Manifest mixes directory-relative and repository-relative paths; each entry was resolved according to its recorded path and verified."}, "total_entries_verified": 44},
        "latest_premium_qc": {"independent_review_status": "REVIEW_COMPLETE_DEFECTS_FOUND_NO_PASS", "colour_ungraded_frames": 131, "colour_comparison_frames": 360, "caption_logo_collision_all_variants": True, "strict_active_comp_readback_proven": False, "corrected_rerender_present": False},
        "governance_invariants": {"PUBLICATION_AUTHORIZED": False, "PRODUCTION_DEPLOYMENT_AUTHORIZED": False, "FIRST_REAL_POSTER": "PAUSED_BY_NITIN", "NITIN_FINAL_VIDEO_APPROVAL": False, "frozen_P0_E0_E1_E2_E3_modified": False}
    }
    write_json(OUT / "VALIDATION.json", validation)

    previous_ledger = PREVIOUS_DIR / "CHECKPOINT_EVENT_LEDGER.jsonl"
    ledger_path = OUT / "CHECKPOINT_EVENT_LEDGER.jsonl"
    if not ledger_path.exists():
        ledger_path.write_bytes(previous_ledger.read_bytes())
    if not ledger_path.read_bytes().startswith(previous_ledger.read_bytes()):
        raise RuntimeError("prior checkpoint ledger prefix drift")
    ledger = EventLedger(str(ledger_path))
    records = ledger.read_all()
    event_id = "daily-master-audit-20260930-18f9b21e2e31"
    if len(records) == 4:
        ledger.append(h.make_event(
            event_id,
            "EVIDENCE_REGISTERED",
            OBSERVED_AT,
            "00_MASTER_ORCHESTRATOR",
            inputs={
                "checkpoint_sha256": digest((OUT / "DAILY_CHECKPOINT.json").read_bytes()),
                "master_transition": False,
                "result": checkpoint["result"],
                "scope": "INDEPENDENT_AUDIT_CHECKPOINT_NOT_PROJECT_MASTER_LINEAGE",
                "source_commit": SOURCE_COMMIT,
            },
        ))
    ledger.verify_chain()
    records = ledger.read_all()
    if len(records) != 5 or records[-1]["event_id"] != event_id:
        raise RuntimeError("unexpected checkpoint ledger state")
    if not all(is_wellformed(record) for record in records):
        raise RuntimeError("checkpoint event contract failure")
    reduced = derive(ledger, keyring={})
    write_json(OUT / "CHECKPOINT_REDUCER_STATE.json", reduced)
    replay = {
        "schema": "CHECKPOINT_REPLAY_V01",
        "scope": "Independent audit checkpoint continuation only, NOT project Master State replay.",
        "source_commit": SOURCE_COMMIT,
        "prior_ledger_path": "p0e4/evidence/daily_master_audit_20260929/CHECKPOINT_EVENT_LEDGER.jsonl",
        "prior_ledger_sha256": digest(previous_ledger.read_bytes()),
        "prior_bytes_preserved": ledger_path.read_bytes().startswith(previous_ledger.read_bytes()),
        "event_contracts_and_input_hashes_valid": True,
        "ledger_head_hash": records[-1]["ledger_hash"],
        "reducer_state_version": reduced["state_version"],
        "verified": True,
        "detail": "OK"
    }
    write_json(OUT / "CHECKPOINT_REPLAY.json", replay)

    manifest_names = [
        "CHECKPOINT_EVENT_LEDGER.jsonl",
        "CHECKPOINT_REDUCER_STATE.json",
        "CHECKPOINT_REPLAY.json",
        "DAILY_CHECKPOINT.json",
        "DRIVE_RECONCILIATION.json",
        "PROJECT_NOTES_V06.json",
        "VALIDATION.json",
        "reproduce.py",
    ]
    lines = [f"{digest((OUT / name).read_bytes())}  {name}" for name in manifest_names]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")

    if target_state["authorizations"]["PUBLICATION_AUTHORIZED"] is not False:
        raise RuntimeError("publication gate changed")
    if target_state["authorizations"]["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is not False:
        raise RuntimeError("deployment gate changed")
    if target_state["production_state"]["first_real_poster"] != "PAUSED_BY_NITIN":
        raise RuntimeError("poster gate changed")
    print(json.dumps({"status": "PASS", "checkpoint_state_version": reduced["state_version"], "master_state_version": master_pointer["state_version"]}, sort_keys=True))


if __name__ == "__main__":
    main()
