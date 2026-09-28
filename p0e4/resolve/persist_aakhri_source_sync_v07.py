"""Build and non-destructively persist the Aakhri V07 private review package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local/aakhri-integrated-preview-lipsync-v07"
EVIDENCE = ROOT / "p0e4/evidence/first_publish_ready_clip_fasttrack_v01_execution/integrated_preview_source_sync_v07"
TEMPLATE = ROOT / "p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01"
DRIVE = Path.home() / "Library/CloudStorage/GoogleDrive-nitin@unchainednitin.com/Gedeelde drives/Unchained Nitin — Master"
DEST = DRIVE / "P0E4_PRODUCTION_INTEGRATION/PRIVATE_REVIEW_OUTPUT/Aakhri-Ishq/FIRST_PUBLISH_READY_CLIP_FASTTRACK_V01/INTEGRATED_PREVIEW_SOURCE_SYNC_V07_20260928"
OBSERVED = "2026-09-28T08:23:34Z"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


candidate = LOCAL / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC_HLG.mp4"
prores = LOCAL / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC_HLG_PRORES.mov"
project = LOCAL / "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V07_SOURCE_TAKE_SYNC.drp"
comparison = LOCAL / "V05_VS_V07_LIPSYNC_BEFORE_AFTER_00_09.mp4"
slow = LOCAL / "V05_VS_V07_LIPSYNC_SLOW_00_04.mp4"
cover = LOCAL / "AAKHRI_V07_COVER_FRAME_06_50.png"
for required in (candidate, prores, project, comparison, slow, cover):
    if not required.is_file() or required.stat().st_size == 0:
        raise RuntimeError(f"missing or empty artifact: {required}")

candidate_sha = sha256(candidate)
if candidate_sha != "71c3f904f667c6b6f6dd83465e93820db22e85951292c84f611c3080a0e561c1":
    raise RuntimeError("candidate SHA drift")

EVIDENCE.mkdir(parents=True, exist_ok=True)

write_json(EVIDENCE / "NITIN_V05_REJECTION_V01.json", {
    "schema": "NITIN_V05_REJECTION_V01",
    "recorded_utc": OBSERVED,
    "supplied_by": "Nitin",
    "authoritative_fact": "On 2026-09-28 Nitin explicitly reported that visible lipsync in the first seconds of V05 remained incorrect.",
    "candidate": {"filename": "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V05_LIPSYNC_HLG.mp4", "sha256": "a02be56cde51c4fd566b404eb4fc9c3db4dfa07dbae44232d477bd9e9115137a"},
    "prior_qc_disposition": "RETAINED_AS_HISTORICAL_BUT_INSUFFICIENT_FOR_HUMAN_ACCEPTANCE",
    "v05_status": "REJECTED_FOR_LIPSYNC_NOT_ACCEPTED_VIDEO",
})

write_json(EVIDENCE / "SOURCE_LEVEL_DIAGNOSIS_V01.json", {
    "schema": "AAKHRI_SOURCE_LEVEL_LIPSYNC_DIAGNOSIS_V01",
    "status": "CAUSE_LOCALIZED_AND_BOUNDED_REPAIR_SELECTED",
    "programme_audio": {"name": "AAKHRI ISHQ MASTER 2.wav", "sha256": "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2", "shift_ms": 0, "time_stretch": False},
    "sources": [
        {"name": "IMG_5739.MOV", "sha256": "8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971", "guide_offset_ms": 526, "diagnostic_result": "visibly closest and most consistent against final vocal; source comparison estimated about 40 ms lead at guide baseline"},
        {"name": "IMG_5741.MOV", "sha256": "8043ab5faac4e5ce768c98268234c9d28eac992ee17b90e063acae02707f8313", "guide_offset_ms": -2044, "diagnostic_result": "variable visible lag estimated 80-120 ms against final vocal"},
    ],
    "diagnosis": "Per-take performance-to-final-vocal timing differs. V05 used IMG_5741 in the opening; a one-frame source slip was too small and the wrong direction/take for the visible performance mismatch. V06 per-take corrections still left cut-dependent lead/lag in independent exact-output QC.",
    "blinded_source_comparison": {"context_url": "https://gemini.google.com/app/7a9b4d5cd99ae1fa", "two_take_result": "IMG_5739 safer opening", "offset_triplet_result": "one-frame delayed IMG_5739 initially preferred with moderate confidence"},
    "v07_choice": "Use contiguous IMG_5739 guide-baseline source frames for the full 20.7-second candidate. The V06 one-frame delay produced a residual visible lag, so V07 uses the baseline midpoint and eliminates cross-take performance mismatch.",
    "limits": ["Guide-audio correlation does not prove visible final-vocal lipsync.", "Browser QC cannot certify sub-frame phase.", "No synthetic mouth correction was used."],
})

resolve_receipt = json.loads((LOCAL / "RESOLVE_LIPSYNC_V07.json").read_text())
write_json(EVIDENCE / "RESOLVE_EXECUTION_RECEIPT_V01.json", resolve_receipt)

write_json(EVIDENCE / "LIPSYNC_BEFORE_AFTER_V01.json", {
    "schema": "AAKHRI_LIPSYNC_BEFORE_AFTER_V01",
    "same_programme_audio": True,
    "normal_speed": {"filename": comparison.name, "sha256": sha256(comparison), "window_s": [0, 9]},
    "half_speed_supporting_view": {"filename": slow.name, "sha256": sha256(slow), "source_window_s": [0, 4]},
    "candidate": {"filename": candidate.name, "sha256": candidate_sha},
    "review_rule": "Normal-speed perception is primary; half-speed view is supporting evidence only.",
})

write_json(EVIDENCE / "RHYTHM_RENDER_VALIDATION_V01.json", {
    "schema": "AAKHRI_RHYTHM_RENDER_VALIDATION_V01",
    "status": "UNCHANGED_FROM_V04_RENDER_EVIDENCE_AND_REGRESSION_PRESERVED",
    "master2_sha256": "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2",
    "cuts_frames": [89, 204, 335, 491, 623],
    "zoom_peaks_frames": [23, 155, 282, 419, 588],
    "shake_peaks_frames": [36, 311, 395, 563],
    "counts": {"cuts": 5, "zooms": 5, "shakes": 4},
    "v07_changes": "No cut, Fusion motion, intensity, attack, recovery, caption, brand, colour, audio-tail or endpoint changes.",
    "event_semantics": "Low/high-band events remain unclassified; no kick/snare or downbeat claim is inferred.",
    "ending": {"master_endpoint_s": 92.7, "candidate_duration_s": 20.7, "fade_s": [20.5, 20.7], "preserved": True},
})

write_json(EVIDENCE / "TECHNICAL_QC_V01.json", {
    "schema": "AAKHRI_SOURCE_SYNC_V07_TECHNICAL_QC_V01",
    "candidate_sha256": candidate_sha,
    "status": "GREEN_PRIVATE_REVIEW",
    "full_video_decode": "PASS",
    "full_audio_decode": "PASS",
    "black_segments": 0,
    "properties": {"resolution": "1080x1920", "fps": "30/1", "frames": 621, "duration_s": 20.7, "video": "HEVC Main 10 yuv420p10le", "color_primaries": "bt2020", "color_transfer": "arib-std-b67", "color_space": "bt2020nc", "audio": "AAC LC 48000Hz stereo"},
    "timeline_regression": {"programme_audio_shift_ms": 0, "audio_time_stretch": False, "cuts_changed": False, "motion_changed": False, "captions_branding_colour_ending_changed": False},
    "visual_checks": {"logo_covers_eyes_nose_mouth": False, "logo_evidence_frames_s": [18.0, 19.3, 20.0], "mouth_crop": "not clipped; Gemini flags tight margin 00:07-00:11"},
    "limits": ["Not a calibrated HDR display certification.", "Technical decode does not replace human visible-lipsync review."],
})

write_json(EVIDENCE / "GEMINI_INDEPENDENT_QC_V01.json", {
    "schema": "GEMINI_INDEPENDENT_AAKHRI_SOURCE_SYNC_V07_QC_V01",
    "context_url": "https://gemini.google.com/app/26595a9b1861e4df",
    "new_independent_context": True,
    "attachment_fully_available": True,
    "attachment_duration_s": 21,
    "candidate_sha256": candidate_sha,
    "verdict": "PASS",
    "lipsync": [
        {"interval": "00:00-00:03", "observation_timecode": "00:01.50", "status": "ALIGNED", "confidence": "MODERATE"},
        {"interval": "cut 00:02.97", "status": "ALIGNED", "confidence": "MODERATE"},
        {"interval": "cut 00:06.80", "status": "ALIGNED", "confidence": "MODERATE"},
        {"interval": "cut 00:11.17", "status": "ALIGNED", "confidence": "MODERATE"},
        {"interval": "cut 00:16.37", "status": "ALIGNED", "confidence": "MODERATE"},
    ],
    "other_findings": {"timing_motion": "continuous; shakes and zooms recover smoothly", "captions_logo": "clear and visible", "black_gaps_jump_artifacts": "none", "ending": "coherent through 20.7s fade", "concrete_defect": "mouth approaches bottom boundary tightly from 00:07-00:11; no clipping reported", "compression": "minor"},
    "limitations": ["Browser playback cannot certify sub-frame sync or calibrated HDR.", "Technical audio correlation alone does not prove visual lipsync.", "AI QC does not replace Nitin approval."],
})

template_instance = {
    "schema": "UNCHAINED_SOCIAL_TEMPLATE_INTEGRATED_PREVIEW_SOURCE_SYNC_V07",
    "inherits": "integrated_preview_repair_v04.json",
    "candidate_sha256": candidate_sha,
    "source_window_s": [72.0, 92.7],
    "selected_take": {"name": "IMG_5739.MOV", "sha256": "8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971", "source_frame_ranges": [[2144,2233],[2233,2348],[2348,2479],[2479,2635],[2635,2767],[2767,2864]]},
    "programme_audio": {"name": "AAKHRI ISHQ MASTER 2.wav", "sha256": "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2", "shift_ms": 0},
    "unchanged": ["cut_positions", "rhythm_motion", "V06_colour", "R2_captions", "brand_lockup", "92.70s_endpoint", "0.20s_end_fade"],
    "cache_invalidation_additions": ["selected_take_sha256", "per_segment_source_frames", "programme_audio_sha256", "visible_lipsync_qc_context"],
}
write_json(TEMPLATE / "integrated_preview_source_sync_v07.json", template_instance)

write_json(EVIDENCE / "TEMPLATE_REUSE_PROOF_V01.json", {
    "schema": "UNCHAINED_SOCIAL_TEMPLATE_SOURCE_SYNC_REUSE_PROOF_V01",
    "status": "COMPACT_DRY_RUN_GREEN_NO_EXTRA_CREATIVE_RENDER",
    "template": "integrated_preview_source_sync_v07.json",
    "second_fragment": {"master_window_s": [88, 92], "programme_audio_sha256": "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2", "take": "IMG_5739.MOV", "take_sha256": "8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971", "derived_contiguous_source_frames": [2624, 2744], "duration_frames": 120},
    "validated_variables": ["source_window", "programme_audio", "selected_take", "source_frames", "text", "timing", "style", "logo", "safe_zone", "rhythm_events", "effect_strength"],
    "note": "This proves deterministic rebinding/configuration on a second in-scope fragment; it is not an additional creative montage or human approval.",
})

write_json(EVIDENCE / "COVER_COPY_ASSET_STATUS_V01.json", {
    "schema": "AAKHRI_V07_COVER_COPY_ASSET_STATUS_V01",
    "cover": {"filename": cover.name, "sha256": sha256(cover), "status": "PRIVATE_REVIEW_CANDIDATE_NOT_ASSET_APPROVED"},
    "concept_copy": {
        "instagram_facebook": "AAKHRI ISHQ — UNCHAINED NITIN. Some love stories never really end. A private first look at the performance.",
        "tiktok": "AAKHRI ISHQ. Some love stories never really end. — UNCHAINED NITIN",
        "youtube_shorts": "AAKHRI ISHQ | UNCHAINED NITIN — Performance Preview",
        "hashtags": ["#AakhriIshq", "#UnchainedNitin", "#TheIndestructibleVoice", "#HindiMusic", "#MusicPerformance"],
        "status": "DRAFT_NOT_APPROVED_NOT_PUBLISHED",
    },
    "assets": [
        {"asset": candidate.name, "state": "READY_FOR_PRIVATE_NITIN_REVIEW", "approval": "OPEN"},
        {"asset": comparison.name, "state": "READY_LIPSYNC_EVIDENCE"},
        {"asset": slow.name, "state": "READY_SUPPORTING_LIPSYNC_EVIDENCE"},
        {"asset": cover.name, "state": "READY_PRIVATE_COVER_REVIEW", "approval": "OPEN"},
        {"asset": project.name, "state": "READY_REUSABLE_RESOLVE_PROJECT"},
        {"asset": "integrated_preview_source_sync_v07.json", "state": "READY_REUSABLE_CONFIGURATION"},
        {"asset": "full-song master and derivatives", "state": "OUT_OF_SCOPE_NOT_RENDERED"},
        {"asset": "platform publication package", "state": "BLOCKED_BY_RIGHTS_CREDITS_FINAL_VIDEO_AND_PUBLISH_APPROVAL"},
    ],
    "rights_and_credits_open": ["Composition/publishing permission remains undocumented in current evidence.", "Synchronization/publication permission remains undocumented in current evidence.", "Required contributor credits remain unresolved."],
})

write_json(EVIDENCE / "MASTER_STATE_UPDATE_STATUS_V01.json", {
    "schema": "MASTER_STATE_UPDATE_STATUS_V01",
    "observed_utc": OBSERVED,
    "branch_head_before_execution": "34bb487380dca001645a3bfef5350fbf20e15c55",
    "registered_master": {"version": "V16.19", "state_version": 45},
    "promotion": "BLOCKED_NOT_ATTEMPTED",
    "reasons": ["MASTER_STATE_LATEST.sha256 does not match the current pointer bytes.", "Authoritative ledger replay fails tamper verification at zero-based seq 31.", "Ledger record at zero-based index 34 is malformed."],
    "history_rewritten": False,
    "new_execution_evidence_persisted": True,
})

write_json(EVIDENCE / "NEXT_READY.json", {
    "schema": "NEXT_READY_V01",
    "status": "WAITING_FOR_NITIN_V07_EXACT_VIDEO_REVIEW",
    "candidate_sha256": candidate_sha,
    "smallest_human_action": "Nitin reviews the exact V07 candidate and normal-speed V05-versus-V07 comparison, then accepts or rejects visible lipsync and overall private preview.",
    "not_implied": ["NITIN_FINAL_VIDEO_APPROVAL", "NITIN_FINAL_ASSET_APPROVAL", "RIGHTS_CLEARANCE", "NITIN_PUBLISH_APPROVAL", "PRODUCTION_DEPLOYMENT_AUTHORIZATION"],
})

DEST.mkdir(parents=True, exist_ok=True)
(DEST / "EVIDENCE").mkdir(exist_ok=True)
(DEST / "TEMPLATE").mkdir(exist_ok=True)

def copy_without_overwriting_difference(source: Path, destination: Path) -> None:
    if destination.exists():
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"refusing to overwrite differing artifact: {destination}")
        return
    shutil.copy2(source, destination)

top_assets = [candidate, prores, project, comparison, slow, cover]
for source in top_assets:
    copy_without_overwriting_difference(source, DEST / source.name)
for source in sorted(EVIDENCE.glob("*.json")):
    copy_without_overwriting_difference(source, DEST / "EVIDENCE" / source.name)
for source in (TEMPLATE / "config.json", TEMPLATE / "integrated_preview_v01.json", TEMPLATE / "integrated_preview_repair_v04.json", TEMPLATE / "integrated_preview_source_sync_v07.json"):
    copy_without_overwriting_difference(source, DEST / "TEMPLATE" / source.name)

mapping = []
for source in top_assets:
    destination = DEST / source.name
    mapping.append({"source": str(source), "destination": str(destination), "source_sha256": sha256(source), "destination_sha256": sha256(destination), "equal": sha256(source) == sha256(destination)})
if not all(item["equal"] for item in mapping):
    raise RuntimeError("Drive readback mismatch")

folder_id = None
for _ in range(30):
    try:
        folder_id = subprocess.check_output(["xattr", "-p", "com.google.drivefs.item-id#S", str(DEST)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        time.sleep(2)
        continue
    if folder_id:
        break

receipt = {
    "schema": "PERSISTENCE_HANDOFF_RECEIPT_V01",
    "status": "COPIED_NON_DESTRUCTIVELY_READBACK_SHA256_GREEN" if folder_id else "COPIED_NON_DESTRUCTIVELY_READBACK_SHA256_GREEN_FOLDER_ID_PENDING_SYNC",
    "destination": {"drive": "Unchained Nitin — Master", "path": str(DEST.relative_to(DRIVE)), "folder_id": folder_id, "url": f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else None},
    "mapping": mapping,
    "source_staging_untouched": True,
    "prior_versions_preserved": True,
    "publication_authorized": False,
}
write_json(EVIDENCE / "PERSISTENCE_HANDOFF_RECEIPT_V01.json", receipt)
copy_without_overwriting_difference(EVIDENCE / "PERSISTENCE_HANDOFF_RECEIPT_V01.json", DEST / "EVIDENCE/PERSISTENCE_HANDOFF_RECEIPT_V01.json")

review = {
    "schema": "AAKHRI_SOURCE_SYNC_V07_REVIEW_PACKAGE_V01",
    "status": "PRIVATE_REVIEW_TECHNICAL_GREEN_GEMINI_PASS_WAITING_NITIN",
    "review_folder_url": receipt["destination"]["url"],
    "candidate": {"filename": candidate.name, "sha256": candidate_sha},
    "before_after": {"normal_speed": comparison.name, "half_speed_support": slow.name},
    "correction": "All video segments use contiguous guide-baseline frames from SHA-bound IMG_5739; programme audio and montage timing are unchanged.",
    "technical_qc": "GREEN",
    "independent_gemini_qc": "PASS_MODERATE_VISIBLE_LIPSYNC_CONFIDENCE",
    "human_gate": "NITIN_V07_EXACT_VIDEO_REVIEW",
    "governance": {"NITIN_FINAL_VIDEO_APPROVAL": False, "NITIN_FINAL_ASSET_APPROVAL": False, "NITIN_PUBLISH_APPROVAL": False, "PUBLICATION_AUTHORIZED": False, "PRODUCTION_DEPLOYMENT_AUTHORIZED": False, "FIRST_REAL_POSTER": "PAUSED_BY_NITIN"},
}
write_json(EVIDENCE / "REVIEW_PACKAGE_V01.json", review)
copy_without_overwriting_difference(EVIDENCE / "REVIEW_PACKAGE_V01.json", DEST / "EVIDENCE/REVIEW_PACKAGE_V01.json")

manifest_lines = []
for path in sorted(EVIDENCE.glob("*.json")):
    manifest_lines.append(f"{sha256(path)}  {path.name}")
(EVIDENCE / "SHA256SUMS.txt").write_text("\n".join(manifest_lines) + "\n")
copy_without_overwriting_difference(EVIDENCE / "SHA256SUMS.txt", DEST / "EVIDENCE/SHA256SUMS.txt")

readback_lines = []
for path in sorted(DEST.rglob("*")):
    if path.is_file():
        readback_lines.append(f"{sha256(path)}  {path.relative_to(DEST)}")
(DEST / "READBACK_SHA256.txt").write_text("\n".join(readback_lines) + "\n")
print(json.dumps({"review": review, "persistence": receipt}, indent=2))
