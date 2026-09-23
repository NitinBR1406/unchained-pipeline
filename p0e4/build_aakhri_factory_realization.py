#!/usr/bin/env python3
"""Build the bounded, private Aakhri Ishq factory-realization evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "p0e4/evidence/aakhri_factory_realization_v01"
LOCAL = ROOT / ".local/aakhri-factory-realization-v01"
PRIVATE = ROOT / ".local/private-real-media-v01"
CREATED = "2026-09-24T00:00:00+02:00"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def assert_binding(path: Path, expected: str) -> dict:
    assert path.is_file(), path
    actual = sha(path)
    assert actual == expected, (path, actual, expected)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": actual}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state = json.loads((ROOT / "p0e4/MASTER_STATE_LATEST.json").read_text())
    master = json.loads((ROOT / state["path"]).read_text())
    assert state["master_state_version"] == "V16.3"
    assert state["state_version"] >= 29
    assert master["authorizations"]["PRODUCTION_DEPLOYMENT_AUTHORIZED"] is False
    assert master["authorizations"]["PUBLICATION_AUTHORIZED"] is False

    raw = assert_binding(
        PRIVATE / "bound-inputs/AKI_SOURCE_0902_V01.mov",
        "50144b7d4754355cdfa69a2be626709116e5aead1faa566bbb4e1ab361ea8790",
    )
    audio = assert_binding(
        PRIVATE / "bound-inputs/AAKHRI ISHQ MASTER 2.wav",
        "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2",
    )
    run4 = assert_binding(
        PRIVATE / "UNCHAINED_AKI_PRIVATE_V01_RUN4.mp4",
        "7f5b96e8a42377263ba9b0953d7c8edf92f4d9cb5447fc80e2527e33a02da501",
    )
    run1 = json.loads((LOCAL / "UNCHAINED_AAKHRI_FACTORY_V01_RUN1.json").read_text())
    run2 = json.loads((LOCAL / "UNCHAINED_AAKHRI_FACTORY_V01_RUN2.json").read_text())
    decode = json.loads((LOCAL / "TECHNICAL_DECODE_QC_RUN2_V01.json").read_text())
    assert run1["status"] == run2["status"] == "RENDER_COMPLETE_PRIVATE_ONLY"
    assert decode["status"] == "FULL_DECODE_COMPLETE"
    assert len(run2["outputs"]) == 5
    assert all(row["decode_status"] == "COMPLETE" for row in decode["outputs"])

    authorization = {
        "schema": "AAKHRI_BOUNDED_REALIZATION_AUTHORIZATION_V01",
        "authorized_by": "Nitin",
        "authorized_scope": "LOCAL_PRIVATE_NON_PUBLISHING_AAKHRI_ONLY",
        "authorized_actions": ["realize_bound_workload", "render", "derive", "technical_qc", "independent_qc", "bounded_repair"],
        "production_deployment_authorized": False,
        "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN",
        "rights_clearance_granted": False,
        "created_at": CREATED,
    }
    write_json("NITIN_AUTHORIZATION.json", authorization)
    write_json("RECONCILIATION.json", {
        "schema": "AAKHRI_FACTORY_RECONCILIATION_V01",
        "authoritative_master_state_version": state["master_state_version"],
        "authoritative_state_version": state["state_version"],
        "reused_evidence": {"raw": raw, "authoritative_audio": audio, "accepted_private_run4": run4},
        "duplicate_authoritative_run_dispatched": False,
        "completed_work_repeated": False,
        "status": "RECONCILED",
    })
    write_json("INGEST_RECEIPT.json", {
        "schema": "AAKHRI_REAL_MEDIA_INGEST_RECEIPT_V01",
        "workload_id": "AAKHRI_ISHQ_BOUND_RAW_MASTER2_V01",
        "raw": raw,
        "authoritative_audio": audio,
        "accepted_private_master_reused_for_intelligence": run4,
        "identity_or_rights_inferred": False,
        "status": "HASH_BOUND",
    })

    creative = {
        "schema": "GEMINI_CREATIVE_INTELLIGENCE_V01",
        "media_filename": "UNCHAINED_AKI_PRIVATE_V01_RUN4.mp4",
        "observed_duration": "03:35",
        "review_scope": "Full video analysis from 00:00 to 03:35",
        "creative_arc": "Intimate opening, increasing emotional intensity and gestures, a third-minute peak, then a quiet personal resolution.",
        "measured_or_observed_facts": [
            {"timecode": "00:00-03:35", "fact": "Portrait 9:16; one male performer in a black shirt at a studio microphone and pop filter; vertical wood/acoustic slats behind him.", "confidence": "high"},
            {"timecode": "00:35", "fact": "Performer points directly toward the camera.", "confidence": "high"},
            {"timecode": "03:28", "fact": "Performer maintains direct camera eye contact during the final phrase.", "confidence": "high"},
        ],
        "recommended_master_treatment": {
            "opening": "Cold open on performer face.",
            "title_timing": "Delay title until after 00:10.",
            "color_motion_rules": "Preserve natural palette and portrait framing; subtle slow push-ins only.",
            "impact_windows": ["00:41-01:07", "02:24-02:50", "03:02-03:20"],
            "protected_vocal_windows": ["00:03-00:15", "03:25-03:35"],
            "outro": "Retain the final emotional settling window.",
        },
        "derivative_candidates": [
            {"id": "DC_01_ChorusEnergy", "start_time": "00:41", "end_time": "00:56", "duration_s": 15, "hook_basis": "Observed rise in vocal intensity and facial expression.", "confidence": "high"},
            {"id": "DC_02_DirectEngagement", "start_time": "01:58", "end_time": "02:13", "duration_s": 15, "hook_basis": "Observed direct eye contact and camera-directed gesture.", "confidence": "high"},
            {"id": "DC_03_ClimacticBuild", "start_time": "02:30", "end_time": "02:45", "duration_s": 15, "hook_basis": "Observed emotional peak and expansive gestures.", "confidence": "high"},
            {"id": "DC_04_IntimateConclusion", "start_time": "03:15", "end_time": "03:30", "duration_s": 15, "hook_basis": "Observed emotional resolution and final look.", "confidence": "high"},
        ],
        "still_candidates": [
            {"timecode": "00:35", "rationale": "Direct point toward camera", "title_safe_area": "top 20% and bottom 30%"},
            {"timecode": "01:56", "rationale": "Direct intense gaze", "title_safe_area": "upper third"},
            {"timecode": "03:28", "rationale": "Soft concluding expression", "title_safe_area": "bottom half"},
        ],
        "caption_strategy": "Lyrics and translations unavailable; do not invent lyric captions.",
        "metadata_positioning": "Private studio vocal performance; solo male performer; portrait frame; raw emotional delivery.",
        "risks": ["Hand gestures cross lower-middle frame.", "Horizontal crops would remove microphone and context."],
        "uncertainties": ["Language and lyrical meaning unverified.", "Platform safe zones not in scope."],
        "no_causation_claim": True,
        "no_rights_or_approval_claim": True,
    }
    write_json("GEMINI_CREATIVE_INTELLIGENCE_RESULT.json", creative)
    write_json("GEMINI_CREATIVE_INTELLIGENCE_RECEIPT.json", {
        "schema": "GEMINI_CREATIVE_INTELLIGENCE_RECEIPT_V01",
        "surface": "Gemini web authenticated as nitinramdaras23@gmail.com",
        "conversation_url": "https://gemini.google.com/app/db14b325064aab1b",
        "input_sha256": run4["sha256"],
        "blind_to_claude_and_chatgpt_conclusions": True,
        "status": "FROZEN",
    })
    write_json("GEMINI_ATTEMPT_01_REJECTED.json", {
        "schema": "GEMINI_ATTEMPT_REJECTION_V01",
        "surface": "Google AI Studio",
        "reason": "Response described a different 28-second female-performer clip and therefore did not evidence the hash-bound workload.",
        "accepted_as_evidence": False,
        "replacement": "Gemini web conversation db14b325064aab1b using the exact existing RUN4 candidate",
    })
    (OUT / "GEMINI_CREATIVE_INTELLIGENCE_REQUEST.txt").write_text(
        "Analyze the exact attached 3:35 real-media video in a fresh context. Return observed facts, creative arc, master treatment, four derivative windows, still candidates, caption/metadata strategy, risks and uncertainties. Do not invent lyrics, rights, approval or causation.\n"
    )

    claude_path = OUT / "CLAUDE_PRODUCTION_TRANSLATION_V01.json"
    claude = json.loads(claude_path.read_text())
    assert claude["schema"] == "CLAUDE_AAKHRI_PRODUCTION_TRANSLATION_V01"
    write_json("CLAUDE_RECEIPT.json", {
        "schema": "CLAUDE_PRODUCTION_TRANSLATION_RECEIPT_V01",
        "surface": "Claude desktop",
        "conversation_url": "https://claude.ai/cowork/cse_01Priw1oSDZ96Lgn8sz1mYE5",
        "model_displayed": "Opus 5.5 Medium",
        "input_bindings": {"raw_sha256": raw["sha256"], "audio_sha256": audio["sha256"], "run4_sha256": run4["sha256"]},
        "execution_performed_by_claude": False,
        "status": "FROZEN_PRODUCTION_TRANSLATION",
    })
    (OUT / "CLAUDE_PRODUCTION_TRANSLATION_REQUEST.txt").write_text(
        "Translate the exact hash-bound Aakhri Ishq inputs and frozen Gemini timing intelligence into a machine-readable Resolve/Fusion plan. No execution, publication, rights inference, lyrics invention or external mutation.\n"
    )
    write_json("ORCHESTRATION_VALIDATION.json", {
        "schema": "AAKHRI_ORCHESTRATION_VALIDATION_V01",
        "ordered_stages": ["INGEST", "GEMINI_CREATIVE_INTELLIGENCE", "ORCHESTRATION_VALIDATION", "CLAUDE_PRODUCTION_TRANSLATION", "RESOLVE_FUSION_PRODUCTION", "DERIVATIVES", "STILLS_THUMBNAILS", "CAPTIONS_METADATA", "TECHNICAL_QC", "INDEPENDENT_GEMINI_QC", "RIGHTS_ROUTING", "POST_READY_MANIFEST", "WAITING_FOR_NITIN"],
        "single_workload_only": True,
        "input_hashes_match": True,
        "no_live_make_or_distribution_step": True,
        "no_publication_step": True,
        "status": "PASS",
    })

    write_json("RESOLVE_RUN1_RECEIPT.json", run1)
    write_json("RESOLVE_RUN2_RECEIPT.json", run2)
    write_json("TECHNICAL_QC_V01.json", decode)
    run1_qc = {
        "schema": "GEMINI_INDEPENDENT_FACTORY_OUTPUT_QC_V01",
        "conversation_url": "https://gemini.google.com/app/1052032ea8dde9ed",
        "reviewed_files": [
            {"file_name": "source_1_master", "observed_duration": "03:34", "blocking_defects": ["Title/artist text competes with face/eyes."], "verdict": "REPAIR_REQUIRED", "confidence": "HIGH"},
            {"file_name": "source_2_derivative_chorus", "observed_duration": "00:15", "blocking_defects": ["Title/artist text competes with face/eyes.", "Abrupt tail."], "verdict": "REPAIR_REQUIRED", "confidence": "HIGH"},
            {"file_name": "source_3_derivative_eye_contact", "observed_duration": "00:15", "blocking_defects": ["Title/artist text competes with face/eyes."], "verdict": "REPAIR_REQUIRED", "confidence": "HIGH"},
            {"file_name": "source_4_derivative_climax", "observed_duration": "00:15", "blocking_defects": ["Title/artist text competes with face/eyes."], "verdict": "REPAIR_REQUIRED", "confidence": "HIGH"},
            {"file_name": "source_5_derivative_intimate", "observed_duration": "00:15", "blocking_defects": ["Title/artist text competes with face/eyes.", "Abrupt tail."], "verdict": "REPAIR_REQUIRED", "confidence": "HIGH"},
        ],
        "package_verdict": "REPAIR_REQUIRED",
        "no_rights_or_approval_claim": True,
        "no_publication_claim": True,
    }
    write_json("INDEPENDENT_GEMINI_QC_RUN1.json", run1_qc)
    write_json("BOUNDED_REPAIR_RECEIPT.json", {
        "schema": "AAKHRI_BOUNDED_REPAIR_RECEIPT_V01",
        "trigger": "Independent Gemini RUN1 QC",
        "repairs": [
            "Reduced and moved non-lyric title/artist label to a lower face-safe area.",
            "Extended D1 and D4 by 15 frames.",
            "Created source-bound PCM24 derivative audio with 200 ms fade-in and 300 ms fade-out.",
            "Added brief derivative visual fades.",
        ],
        "scope_expanded": False,
        "rerender": "UNCHAINED_AAKHRI_FACTORY_V01_RUN2",
        "status": "COMPLETED",
    })
    run2_qc = {
        "schema": "GEMINI_INDEPENDENT_FACTORY_REQC_V01",
        "conversation_url": "https://gemini.google.com/app/b3c18a928d96dfce",
        "reviewed_files": [
            {"file": run2["outputs"][0]["name"], "observed_duration": "03:34", "observations": "Full playback; stable portrait; clean audio; apparent sync; label on shirt away from face; natural fade.", "blocking_defects": [], "verdict": "PASS", "confidence": "HIGH"},
            {"file": run2["outputs"][1]["name"], "observed_duration": "00:16", "observations": "Full playback; portrait; clean synchronized audio; face-safe label; brief intentional fade.", "blocking_defects": [], "verdict": "PASS", "confidence": "HIGH"},
            {"file": run2["outputs"][2]["name"], "observed_duration": "00:15", "observations": "Full playback; portrait; clean synchronized audio; face-safe label; intentional fade.", "blocking_defects": [], "verdict": "PASS", "confidence": "HIGH"},
            {"file": run2["outputs"][3]["name"], "observed_duration": "00:15", "observations": "Full playback; stable portrait; no glitches; clean synchronized audio; face-safe label; clean fade.", "blocking_defects": [], "verdict": "PASS", "confidence": "HIGH"},
            {"file": run2["outputs"][4]["name"], "observed_duration": "00:16", "observations": "Full playback; portrait maintained; no visual errors or audio dropouts; face-safe label; natural fade.", "blocking_defects": [], "verdict": "PASS", "confidence": "HIGH"},
        ],
        "package_verdict": "ACCEPT_PRIVATE_POST_READY",
        "limitations": [],
        "no_rights_or_approval_claim": True,
        "no_publication_claim": True,
    }
    write_json("INDEPENDENT_GEMINI_QC_RUN2.json", run2_qc)

    still_specs = [
        ("AAKHRI_S1_DIRECT_POINT_V01.png", "00:35", "7cfb439f33666f0721f1dc54a1b3ccaf9dcf5829b038808ad4cd5ec453e4e693"),
        ("AAKHRI_S2_MID_EXPRESSION_V01.png", "01:56", "d6bb5aa027b1360d42a30609d241559ee5a8547e0cd29e476e7818aba99ad460"),
        ("AAKHRI_S3_FINAL_EYE_CONTACT_V01.png", "03:28", "6a690aeff80b9ff5ef10d98c24b8073057a3a3ffa019e1020718b139796eeefc"),
    ]
    stills = []
    for filename, timecode, expected in still_specs:
        binding = assert_binding(LOCAL / filename, expected)
        binding.update(timecode=timecode, source="RUN1 master; reused because RUN2 repair did not alter these source frames")
        stills.append(binding)
    write_json("STILLS_MANIFEST.json", {"schema": "AAKHRI_STILLS_MANIFEST_V01", "items": stills, "status": "COMPLETE_PRIVATE_ONLY"})
    write_json("CAPTIONS_METADATA_V01.json", {
        "schema": "AAKHRI_CAPTIONS_METADATA_V01",
        "title": "Aakhri Ishq",
        "artist_label": "Unchained Nitin",
        "review_description": "Private review package for the Aakhri Ishq portrait studio performance.",
        "release_caption": None,
        "lyrics_caption_status": "NOT_PRODUCED_SOURCE_UNAVAILABLE",
        "translation_status": "NOT_PRODUCED_SOURCE_UNAVAILABLE",
        "cta_status": "OMITTED_NON_PUBLISHING_SCOPE",
        "publication_metadata_status": "NOT_CREATED",
        "rights_claim": None,
        "status": "PRIVATE_FACTUAL_METADATA_ONLY",
    })
    write_json("RIGHTS_ROUTING.json", {
        "schema": "AAKHRI_RIGHTS_ROUTING_V01",
        "route": "RIGHTS_HOLD",
        "rights_clearance": "NOT_GRANTED",
        "evidence": "No new rights evidence supplied in this authorization.",
        "effect": "Package may be reviewed privately but cannot be published or distributed.",
        "human_owner": "NITIN",
    })

    output_bindings = []
    for item in run2["outputs"]:
        verified = assert_binding(Path(item["path"]), item["sha256"])
        output_bindings.append({
            "name": item["name"], "path": verified["path"],
            "bytes": verified["bytes"], "sha256": verified["sha256"], "source_frames": item["source_frames"]
        })
    resolve_project_archive = assert_binding(
        LOCAL / "UNCHAINED_AAKHRI_FACTORY_V01_RUN2.drp",
        "6be8fde869e14375539e7fc98d2a285c93a6dbceaf54251a08139602a018b313",
    )
    post_ready = {
        "schema": "AAKHRI_POST_READY_MANIFEST_V01",
        "workload_id": "AAKHRI_ISHQ_BOUND_RAW_MASTER2_V01",
        "status": "POST_READY_WAITING_FOR_NITIN",
        "scope": "PRIVATE_NON_PUBLISHING_ONLY",
        "inputs": {"raw": raw, "authoritative_audio": audio},
        "outputs": output_bindings,
        "resolve_project_archive": resolve_project_archive,
        "stills": stills,
        "stage_outcomes": {
            "INGEST": "GREEN_HASH_BOUND", "GEMINI_CREATIVE_INTELLIGENCE": "GREEN_FROZEN",
            "ORCHESTRATION_VALIDATION": "GREEN", "CLAUDE_PRODUCTION_TRANSLATION": "GREEN_FROZEN",
            "RESOLVE_FUSION_PRODUCTION": "GREEN_RUN2", "DERIVATIVES": "GREEN_4",
            "STILLS_THUMBNAILS": "GREEN_3_STILLS", "CAPTIONS_METADATA": "GREEN_PRIVATE_METADATA_LYRICS_UNAVAILABLE",
            "TECHNICAL_QC": "GREEN_FULL_DECODE", "INDEPENDENT_GEMINI_QC": "GREEN_ACCEPT_PRIVATE_POST_READY",
            "RIGHTS_ROUTING": "RIGHTS_HOLD", "POST_READY_MANIFEST": "GREEN_PRIVATE_ONLY",
        },
        "human_gates": ["RIGHTS_CLEARANCE", "NITIN_CREATIVE_APPROVAL", "NITIN_FINAL_ASSET_APPROVAL", "NITIN_PUBLISH_APPROVAL"],
        "production_deployment_authorized": False,
        "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN",
        "publish_ready": False,
    }
    write_json("POST_READY_MANIFEST.json", post_ready)
    write_json("STATE_REDUCER_OUTCOME.json", {
        "schema": "AAKHRI_FACTORY_STATE_REDUCER_OUTCOME_V01",
        "parent_master_state_version": state["master_state_version"],
        "parent_state_version": state["state_version"],
        "workload_state": "POST_READY_WAITING_FOR_NITIN",
        "global_master_state_mutated": False,
        "reason": "Workload-scoped additive evidence does not change global deployment, publication, approval or rights state.",
        "closed_gates": {"PRODUCTION_DEPLOYMENT_AUTHORIZED": False, "PUBLICATION_AUTHORIZED": False, "FIRST_REAL_POSTER": "PAUSED_BY_NITIN"},
    })
    write_json("NEXT_READY.json", {
        "schema": "AAKHRI_FACTORY_NEXT_READY_V01",
        "status": "WAITING_FOR_NITIN",
        "smallest_human_questions": [
            {"gate": "NITIN_CREATIVE_APPROVAL", "question": "Approve or reject the RUN2 private master, four derivatives and three stills as the creative package?"},
            {"gate": "RIGHTS_CLEARANCE", "question": "Provide verified rights clearance before any publication route is considered."},
        ],
        "publish_approval_requested": False,
        "independent_ready_work_remaining": [],
    })

    event = {
        "schema": "AAKHRI_FACTORY_EVENT_V01",
        "event_type": "PRIVATE_FACTORY_REALIZATION_POST_READY",
        "workload_id": post_ready["workload_id"],
        "event_time": CREATED,
        "outcome": post_ready["status"],
        "input_hashes": [raw["sha256"], audio["sha256"]],
        "output_hashes": [row["sha256"] for row in output_bindings],
        "rights_route": "RIGHTS_HOLD",
        "publication_authorized": False,
    }
    (OUT / "ENGINEERING_EVENT_LEDGER.jsonl").write_text(json.dumps(event, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
