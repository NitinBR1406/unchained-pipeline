"""Reusable, fail-closed Resolve performance-template contract and dry-run planner."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EFFECT_KEYS = ("micro_push", "restrained_shake", "slow_push")
CAPTION_MODES = {"NONE", "ORIGINAL_OPENING_DRAFT", "VERIFIED_LYRIC_ONLY"}


class TemplateContractError(ValueError):
    pass


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def validate_job(job: dict[str, Any]) -> None:
    for group in ("source_binding", "style_binding", "motion_binding", "outputs"):
        if group not in job:
            raise TemplateContractError(f"MISSING_GROUP:{group}")
    source = job["source_binding"]
    for key in ("audio_sha256", "take_asset_ids_and_sha256", "alignment_map", "edit_plan_sha256", "source_color_metadata"):
        if not source.get(key):
            raise TemplateContractError(f"MISSING_SOURCE_BINDING:{key}")
    motion = job["motion_binding"]
    switches = motion.get("effect_switches", {})
    if set(switches) != set(EFFECT_KEYS):
        raise TemplateContractError("EFFECT_SWITCH_SET_MISMATCH")
    if any(value is not False for value in switches.values()):
        if motion.get("selected_policy_version") in (None, "UNSELECTED"):
            raise TemplateContractError("EFFECT_ENABLED_WITHOUT_SELECTED_POLICY")
        if motion.get("event_evidence_status") != "NITIN_SELECTED_AND_VALIDATED":
            raise TemplateContractError("EFFECT_ENABLED_WITHOUT_VALIDATED_EVENTS")
    caption = job["style_binding"].get("caption_mode")
    if caption not in CAPTION_MODES:
        raise TemplateContractError("INVALID_CAPTION_MODE")
    if caption == "VERIFIED_LYRIC_ONLY" and not job["style_binding"].get("verified_lyric_sha256"):
        raise TemplateContractError("LYRIC_MODE_WITHOUT_VERIFIED_TEXT")
    if caption != "NONE" and job["style_binding"].get("brand_typography_status") != "VERIFIED":
        raise TemplateContractError("CAPTION_WITHOUT_VERIFIED_BRAND_TYPOGRAPHY")
    color = source["source_color_metadata"]
    required = {"input", "timeline", "output", "tone_mapping", "gamut_mapping", "minimum_bit_depth"}
    if not required.issubset(color):
        raise TemplateContractError("INCOMPLETE_COLOR_METADATA")
    if {color["input"], color["timeline"], color["output"]} != {"Rec.2100 HLG"}:
        raise TemplateContractError("SILENT_NON_HLG_TRANSFORM")
    if color["minimum_bit_depth"] < 10:
        raise TemplateContractError("INSUFFICIENT_BIT_DEPTH")


def build_dry_run_plan(job: dict[str, Any]) -> dict[str, Any]:
    validate_job(job)
    switches = job["motion_binding"]["effect_switches"]
    invalidation = {
        "ingest": ["audio_sha256", "take_asset_ids_and_sha256", "source_color_metadata"],
        "alignment": ["take_asset_ids_and_sha256", "alignment_map"],
        "timeline": ["alignment_map", "edit_plan_sha256"],
        "color": ["source_color_metadata", "color_preset_sha256"],
        "motion": ["event_map_sha256", "event_evidence_status", "selected_policy_version", "effect_switches", "vocal_protection_intervals"],
        "caption": ["brand_preset_version", "caption_mode", "verified_lyric_sha256"],
        "render": ["timeline", "color", "motion", "caption", "output_recipe"],
    }
    return {
        "schema": "UNCHAINED_PERFORMANCE_TEMPLATE_DRY_RUN_PLAN_V01",
        "template_version": job["template_version"],
        "source_specific": job["source_binding"],
        "reusable_style": job["style_binding"],
        "motion": job["motion_binding"],
        "effect_nodes_instantiated": list(EFFECT_KEYS),
        "effect_nodes_enabled": [key for key, value in switches.items() if value],
        "effect_nodes_bypassed": [key for key, value in switches.items() if not value],
        "caption_enabled": job["style_binding"]["caption_mode"] != "NONE",
        "render_requested": False,
        "full_master_rendered": False,
        "invalidation_graph": invalidation,
        "outputs": job["outputs"],
    }


def write_plan(job_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    plan = build_dry_run_plan(load_json(job_path))
    Path(output_path).write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan
