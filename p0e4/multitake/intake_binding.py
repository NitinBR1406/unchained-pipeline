"""Shared Drive binding and pure watcher-readiness evaluation.

The evaluator never reads Drive and never dispatches production. A watcher supplies
two metadata/byte observations; only an explicitly enabled future real-acceptance
adapter may turn an eligible result into a RAW_DROP event.
"""
from __future__ import annotations

from copy import deepcopy

from hardening.raw_drop import digest, require


VIDEO_EXTENSIONS = (".mov", ".mp4", ".mxf", ".m4v")
AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".flac", ".m4a", ".mp3")
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff")


def binding_contract():
    return {
        "schema": "MULTI_TAKE_INTAKE_BINDING_V01",
        "drive_name": "Unchained Nitin — Master",
        "drive_id": "0AG0CqqUZ6YuXUk9PVA",
        "parent_folder_id": "1a0i1SJXd80_iq0StUUvQASDK0IQuiKuR",
        "intake_root_relative": "P0E4_PRODUCTION_INTEGRATION/RAW_INTAKE/MULTI_TAKE",
        "intake_root_folder_id": "1Nc2BoQNqWUARhCnKdtJ7jKXm9hcBhzJc",
        "finder_root": "/Users/nitinramdaras/Library/CloudStorage/GoogleDrive-nitin@unchainednitin.com/Gedeelde drives/Unchained Nitin — Master/P0E4_PRODUCTION_INTEGRATION/RAW_INTAKE/MULTI_TAKE",
        "workload_rule": "ONE_DIRECT_CHILD_FOLDER_PER_SONG",
        "file_rename_or_take_order_required": False,
        "minimum_unique_video_takes": 2,
        "authoritative_master_audio_files": 1,
        "photos_optional": True,
        "stability_required_identical_polls": 2,
        "empty_folder_triggers": False,
        "production_dispatch_enabled": False,
        "real_acceptance_required": True,
        "production_deployment_authorized": False,
        "publication_authorized": False,
        "first_real_poster": "PAUSED_BY_NITIN",
    }


class MultiTakeIntakeEvaluator:
    """Evaluate complete workload-folder snapshots without semantic filename use."""

    def __init__(self, contract=None):
        self.contract = contract or binding_contract()

    @staticmethod
    def _validate_file(item):
        require(set(item) == {"file_id", "name", "size", "sha256", "cloud_bytes_local", "modified_token"}, "file fields")
        require(isinstance(item["file_id"], str) and item["file_id"], "file id")
        require(isinstance(item["name"], str) and item["name"] and "/" not in item["name"], "direct child filename")
        require(isinstance(item["size"], int) and item["size"] >= 0, "file size")
        if item["cloud_bytes_local"]:
            require(item["size"] > 0 and isinstance(item["sha256"], str) and len(item["sha256"]) == 64, "local byte evidence")

    @staticmethod
    def _kind(name):
        lower = name.lower()
        if lower.endswith(VIDEO_EXTENSIONS): return "TAKE"
        if lower.endswith(AUDIO_EXTENSIONS): return "MASTER_AUDIO_CANDIDATE"
        if lower.endswith(PHOTO_EXTENSIONS): return "PHOTO"
        return "UNSUPPORTED"

    def evaluate(self, workload, previous=None, already_emitted=None):
        require(workload.get("schema") == "MULTI_TAKE_WORKLOAD_SNAPSHOT_V01", "snapshot schema")
        require(workload.get("drive_id") == self.contract["drive_id"], "wrong drive")
        require(workload.get("parent_folder_id") == self.contract["intake_root_folder_id"], "wrong intake root")
        require(isinstance(workload.get("workload_folder_id"), str) and workload["workload_folder_id"], "workload folder id")
        require(isinstance(workload.get("workload_folder_name"), str) and workload["workload_folder_name"].strip(), "workload folder name")
        require("/" not in workload["workload_folder_name"] and not workload["workload_folder_name"].startswith("_"), "workload folder rule")
        files = workload.get("files"); require(isinstance(files, list), "files")
        for item in files: self._validate_file(item)
        require(len({x["file_id"] for x in files}) == len(files), "duplicate file id")
        base = {"schema": "MULTI_TAKE_WATCHER_DECISION_V01", "drive_id": workload["drive_id"],
                "workload_folder_id": workload["workload_folder_id"], "workload_folder_name": workload["workload_folder_name"],
                "dispatch_enabled": False, "real_acceptance_required": True, "files_observed": len(files)}
        if not files:
            return {**base, "status": "EMPTY_NO_TRIGGER", "trigger_eligible": False, "reason": "EMPTY_FOLDER"}
        classified = [{**deepcopy(x), "kind": self._kind(x["name"])} for x in files]
        unavailable = [x["file_id"] for x in classified if not x["cloud_bytes_local"]]
        if unavailable:
            return {**base, "status": "HOLD_CLOUD_BYTES_UNAVAILABLE", "trigger_eligible": False,
                    "unavailable_file_ids": sorted(unavailable)}
        unsupported = [x["file_id"] for x in classified if x["kind"] == "UNSUPPORTED"]
        if unsupported:
            return {**base, "status": "HOLD_UNSUPPORTED_FILE", "trigger_eligible": False,
                    "unsupported_file_ids": sorted(unsupported)}
        videos = [x for x in classified if x["kind"] == "TAKE"]
        audio = [x for x in classified if x["kind"] == "MASTER_AUDIO_CANDIDATE"]
        photos = [x for x in classified if x["kind"] == "PHOTO"]
        if len(audio) > 1:
            return {**base, "status": "HOLD_MASTER_AUDIO_AMBIGUITY", "trigger_eligible": False,
                    "master_audio_candidate_ids": sorted(x["file_id"] for x in audio)}
        unique_video = {}
        aliases = []
        for video in sorted(videos, key=lambda x: x["file_id"]):
            if video["sha256"] in unique_video:
                aliases.append({"file_id": video["file_id"], "canonical_file_id": unique_video[video["sha256"]],
                                "sha256": video["sha256"], "status": "DUPLICATE_SUPPRESSED"})
            else: unique_video[video["sha256"]] = video["file_id"]
        if len(unique_video) < self.contract["minimum_unique_video_takes"] or len(audio) != 1:
            return {**base, "status": "WAITING_INCOMPLETE_FILE_SET", "trigger_eligible": False,
                    "unique_video_takes": len(unique_video), "master_audio_candidates": len(audio), "aliases": aliases}
        identity = {x["file_id"]: {"sha256": x["sha256"], "size": x["size"], "modified_token": x["modified_token"]}
                    for x in classified}
        if previous is None:
            return {**base, "status": "PENDING_STABILITY", "trigger_eligible": False,
                    "set_identity_sha256": digest(identity), "stable_polls": 1, "aliases": aliases}
        require(previous.get("workload_folder_id") == workload["workload_folder_id"], "previous workload mismatch")
        previous_identity = previous.get("identity")
        if previous_identity != identity:
            previous_by_id = previous_identity or {}
            drift = sorted(k for k in set(previous_by_id) & set(identity)
                           if previous_by_id[k].get("sha256") != identity[k].get("sha256"))
            return {**base, "status": "HOLD_SOURCE_DRIFT" if drift else "PENDING_STABILITY",
                    "trigger_eligible": False, "drift_file_ids": drift, "set_identity_sha256": digest(identity),
                    "stable_polls": 1, "aliases": aliases}
        event_key = digest({"drive_id": workload["drive_id"], "workload_folder_id": workload["workload_folder_id"],
                            "files": identity})
        if already_emitted == event_key:
            return {**base, "status": "DUPLICATE_EVENT_SUPPRESSED", "trigger_eligible": False,
                    "event_key": event_key, "aliases": aliases}
        manifest = {"schema": "MULTI_TAKE_RAW_DROP_V01", "scope": "FUTURE_REAL_ACCEPTANCE_ONLY",
                    "workload_folder_id": workload["workload_folder_id"], "takes": sorted(unique_video.values()),
                    "master_audio_file_id": audio[0]["file_id"], "photo_file_ids": sorted(x["file_id"] for x in photos),
                    "file_sha256": {x["file_id"]: x["sha256"] for x in classified}, "filename_semantics_used": False}
        return {**base, "status": "READY_FOR_EXPLICIT_REAL_ACCEPTANCE", "trigger_eligible": True,
                "dispatch_enabled": False, "stable_polls": 2, "event_key": event_key, "aliases": aliases,
                "manifest": manifest, "event_ledger_action": "APPEND_ON_EXPLICIT_REAL_ACCEPTANCE_ONLY"}

    def stability_checkpoint(self, workload):
        identity = {x["file_id"]: {"sha256": x["sha256"], "size": x["size"], "modified_token": x["modified_token"]}
                    for x in workload["files"]}
        return {"schema": "MULTI_TAKE_STABILITY_CHECKPOINT_V01", "workload_folder_id": workload["workload_folder_id"],
                "identity": identity, "checkpoint_sha256": digest(identity)}
