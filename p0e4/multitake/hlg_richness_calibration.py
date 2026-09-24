"""Fail-closed rules for minimal HDR-native HLG color-richness calibration."""
from __future__ import annotations


VARIANTS = ("HLG_IDENTITY", "R1_SUBTLE_RICHNESS", "R2_MEDIUM_RICHNESS", "R3_STRONG_RICHNESS")


def validate_contract(contract: dict) -> bool:
    if contract.get("schema") != "HLG_COLOR_RICHNESS_CALIBRATION_V01":
        raise ValueError("R6_SCHEMA")
    if tuple(contract.get("variant_order", ())) != VARIANTS:
        raise ValueError("R6_VARIANT_ORDER")
    if contract.get("technical_baseline") != "10_BIT_BT2020_REC2100_HLG":
        raise ValueError("R6_BASELINE")
    if contract.get("full_dolby_vision_identity_claimed") is not False:
        raise ValueError("DOLBY_IDENTITY_OVERCLAIM")
    if contract.get("full_master_render_authorized") is not False:
        raise ValueError("FULL_MASTER_FORBIDDEN")
    if contract.get("preserved") != {
        "source_scene": True, "framing": True, "exposure": True,
        "gamma_tone_mapping": True, "contrast": True,
    }:
        raise ValueError("R6_PRESERVATION_CONTRACT")
    forbidden = set(contract.get("forbidden", ()))
    required = {"REC709_CONVERSION", "STATIC_MASK", "BLUR", "SKIN_SMOOTHING",
                "FACE_MANIPULATION", "GENERATIVE_PROCESSING", "FULL_SONG_RENDER"}
    if not required.issubset(forbidden):
        raise ValueError("R6_FORBIDDEN_SET")
    scenes = contract.get("representative_scenes", [])
    if len(scenes) != 4 or len({x.get("take_asset_id") for x in scenes}) != 4:
        raise ValueError("R6_FOUR_SOURCE_SCENES")
    recipes = contract.get("variant_recipes", {})
    if set(recipes) != set(VARIANTS):
        raise ValueError("R6_RECIPE_SET")
    if recipes["HLG_IDENTITY"].get("operation") != "NONE":
        raise ValueError("R6_IDENTITY_NOT_NEUTRAL")
    previous = 1.0
    for variant in VARIANTS[1:]:
        recipe = recipes[variant]
        if recipe.get("operation") != "ASC_CDL_SATURATION_ONLY":
            raise ValueError("R6_OPERATION:" + variant)
        cdl = recipe.get("cdl", {})
        if cdl.get("Slope") != "1.0 1.0 1.0" or cdl.get("Offset") != "0.0 0.0 0.0" or cdl.get("Power") != "1.0 1.0 1.0":
            raise ValueError("R6_NON_CHROMA_CHANGE:" + variant)
        saturation = float(cdl.get("Saturation", 0))
        if not previous < saturation <= 1.12:
            raise ValueError("R6_SATURATION_BOUNDS:" + variant)
        previous = saturation
    return True


def verify_render_plan(plan: dict) -> bool:
    if plan.get("full_master") is not False:
        raise ValueError("FULL_MASTER_RENDER_ATTEMPT")
    rows = plan.get("segments", [])
    expected = {(scene, variant) for scene in range(1, 5) for variant in VARIANTS}
    actual = {(row.get("scene_index"), row.get("variant")) for row in rows}
    if len(rows) != 16 or actual != expected:
        raise ValueError("R6_INCOMPLETE_MATRIX")
    if any(row.get("fusion_tools") or row.get("mask_used") or row.get("blur_used") for row in rows):
        raise ValueError("R6_FORBIDDEN_FINISHING")
    return True


def assess_candidate_metrics(identity: dict, candidate: dict, limits: dict) -> dict:
    failures = []
    for key in ("luma_mean", "luma_p05", "luma_p95"):
        if abs(float(candidate[key]) - float(identity[key])) > float(limits["max_luma_delta"]):
            failures.append("LUMA_DRIFT:" + key)
    if float(candidate["clip_low_pct"]) > float(identity["clip_low_pct"]) + float(limits["max_added_clip_pct"]):
        failures.append("SHADOW_CLIPPING")
    if float(candidate["clip_high_pct"]) > float(identity["clip_high_pct"]) + float(limits["max_added_clip_pct"]):
        failures.append("HIGHLIGHT_CLIPPING")
    if float(candidate["saturation_p99"]) > float(limits["max_saturation_p99"]):
        failures.append("GAMUT_OR_SATURATION_EXCURSION")
    if abs(float(candidate["skin_hue_median_degrees"]) - float(identity["skin_hue_median_degrees"])) > float(limits["max_skin_hue_shift_degrees"]):
        failures.append("SKIN_HUE_DISPLACEMENT")
    return {"status": "GREEN" if not failures else "HOLD", "failures": failures}
