"""Fail-closed contract checks for RAW-reference color look development."""
from __future__ import annotations


LOOKS = ("RAW_REFERENCE", "A_RAW_PLUS", "B_NATURAL_CINEMATIC", "C_UNCHAINED_CINEMATIC")


def validate_contract(contract):
    if contract.get("schema") != "RAW_REFERENCE_SUPREMACY_V01":
        raise ValueError("RAW_REFERENCE_SCHEMA")
    if contract.get("r4_color_status") != "REJECTED_BY_NITIN":
        raise ValueError("R4_REJECTION_MISSING")
    if contract.get("ai_qc_may_override_nitin") is not False:
        raise ValueError("HUMAN_AUTHORITY_DRIFT")
    if tuple(contract.get("look_order", ())) != LOOKS:
        raise ValueError("LOOK_ORDER")
    if contract.get("full_master_render_authorized") is not False:
        raise ValueError("FULL_MASTER_FORBIDDEN")
    if contract.get("preserved", {}) != {
        "edl": True, "sync": True, "framing": True, "source_media": True
    }:
        raise ValueError("PRESERVATION_CONTRACT")
    forbidden = set(contract.get("forbidden", ()))
    required = {"R4_STATIC_INVERTED_ELLIPSE", "SKIN_SMOOTHING", "FACE_MANIPULATION",
                "GENERATIVE_ALTERATION", "DESTRUCTIVE_GLOBAL_GRADE"}
    if not required.issubset(forbidden):
        raise ValueError("FORBIDDEN_SET_INCOMPLETE")
    scenes = contract.get("representative_scenes", [])
    if len(scenes) != 4 or len({x.get("take_asset_id") for x in scenes}) != 4:
        raise ValueError("FOUR_DISTINCT_TAKES_REQUIRED")
    recipes = contract.get("look_recipes", {})
    if set(recipes) != set(LOOKS):
        raise ValueError("LOOK_RECIPE_SET")
    if recipes["RAW_REFERENCE"].get("resolve_color_page_operation") != "NONE_SOURCE_VALUES":
        raise ValueError("RAW_REFERENCE_NOT_NEUTRAL")
    for name in LOOKS[1:]:
        recipe = recipes[name]
        if recipe.get("operation") != "ASC_CDL_NODE_1":
            raise ValueError("COLOR_PAGE_OPERATION:" + name)
        cdl = recipe.get("cdl", {})
        bounds = {"Slope": (0.94, 1.06), "Offset": (-0.015, 0.015), "Power": (0.94, 1.06)}
        for key, (lo, hi) in bounds.items():
            values = [float(v) for v in cdl.get(key, "").split()]
            if len(values) != 3 or any(v < lo or v > hi for v in values):
                raise ValueError(f"{name}_{key}_BOUNDS")
        if not 0.95 <= float(cdl.get("Saturation", 0)) <= 1.10:
            raise ValueError(name + "_SATURATION_BOUNDS")
    return True


def verify_render_plan(plan):
    if plan.get("full_master") is not False:
        raise ValueError("FULL_MASTER_RENDER_ATTEMPT")
    rows = plan.get("segments", [])
    expected = {(scene, look) for scene in range(1, 5) for look in LOOKS}
    actual = {(row.get("scene_index"), row.get("look")) for row in rows}
    if actual != expected or len(rows) != 16:
        raise ValueError("INCOMPLETE_COMPARISON_MATRIX")
    if any(row.get("fusion_tools") for row in rows):
        raise ValueError("FUSION_OR_MASK_FORBIDDEN")
    return True
