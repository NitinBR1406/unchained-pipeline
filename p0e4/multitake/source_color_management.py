"""Fail-closed source color management contracts for camera originals."""
from __future__ import annotations


HLG_TAGS = {
    "color_primaries": "ITU_R_2020",
    "transfer_function": "ITU_R_2100_HLG",
    "ycbcr_matrix": "ITU_R_2020",
}


def classify_source(metadata: dict) -> dict:
    """Classify only color properties proved by container/codec metadata."""
    video = metadata.get("video", {})
    extensions = video.get("format_description_extensions", {})
    tags = {
        "color_primaries": extensions.get("ColorPrimaries"),
        "transfer_function": extensions.get("TransferFunction"),
        "ycbcr_matrix": extensions.get("YCbCrMatrix"),
    }
    if tags != HLG_TAGS:
        raise ValueError("UNSUPPORTED_OR_AMBIGUOUS_SOURCE_COLOR_TAGS")
    if int(video.get("bits_per_component", 0)) < 10:
        raise ValueError("SOURCE_BIT_DEPTH_BELOW_10")
    atoms = extensions.get("SampleDescriptionExtensionAtoms", {})
    return {
        "source_color_space": "Rec.2100 HLG",
        "base_layer": "BT.2020_HLG_VIDEO_RANGE_10_BIT",
        "dolby_vision_metadata_present": "dvvC" in atoms,
        "dolby_vision_metadata_preservation_required_for_full_display_identity": "dvvC" in atoms,
        "tags": tags,
    }


def validate_reference_names(reference: dict) -> bool:
    required = {"SOURCE_BYTES_REFERENCE", "RESOLVE_DECODE_REFERENCE", "IDENTITY_ROUNDTRIP_REFERENCE"}
    if set(reference) != required:
        raise ValueError("REFERENCE_CONCEPT_SET")
    if reference["SOURCE_BYTES_REFERENCE"].get("kind") != "HASH_BOUND_CAMERA_ORIGINALS":
        raise ValueError("SOURCE_BYTES_REFERENCE_KIND")
    if reference["RESOLVE_DECODE_REFERENCE"].get("kind") != "DECODED_UNGRADED_VIEW":
        raise ValueError("RESOLVE_DECODE_REFERENCE_KIND")
    if reference["IDENTITY_ROUNDTRIP_REFERENCE"].get("kind") != "ZERO_CREATIVE_GRADE_RENDER":
        raise ValueError("IDENTITY_ROUNDTRIP_REFERENCE_KIND")
    return True


def validate_resolve_hlg_settings(settings: dict) -> bool:
    expected = {
        "colorScienceMode": "davinciYRGBColorManaged",
        "isAutoColorManage": "0",
        "colorSpaceInput": "Rec.2100 HLG",
        "colorSpaceTimeline": "Rec.2100 HLG",
        "colorSpaceOutput": "Rec.2100 HLG",
    }
    for key, value in expected.items():
        if str(settings.get(key)) != value:
            raise ValueError("RESOLVE_COLOR_SETTING:" + key)
    return True


def assess_roundtrip(source: dict, rendered: dict) -> dict:
    """Assess tag/bit-depth preservation; never infer Dolby display identity."""
    src = classify_source(source)
    out_video = rendered.get("video", {})
    out_ext = out_video.get("format_description_extensions", {})
    out_tags = {
        "color_primaries": out_ext.get("ColorPrimaries"),
        "transfer_function": out_ext.get("TransferFunction"),
        "ycbcr_matrix": out_ext.get("YCbCrMatrix"),
    }
    base_layer_tags_preserved = out_tags == HLG_TAGS
    bit_depth_preserved = int(out_video.get("bits_per_component", 0)) >= 10
    out_atoms = out_ext.get("SampleDescriptionExtensionAtoms", {})
    dolby_preserved = ("dvvC" in out_atoms) if src["dolby_vision_metadata_present"] else True
    return {
        "base_layer_hlg_identity_supported": base_layer_tags_preserved and bit_depth_preserved,
        "base_layer_tags_preserved": base_layer_tags_preserved,
        "bit_depth_preserved": bit_depth_preserved,
        "dolby_vision_metadata_preserved": dolby_preserved,
        "full_source_display_identity_demonstrated": base_layer_tags_preserved and bit_depth_preserved and dolby_preserved,
        "may_be_called_raw": False,
    }


def assert_reference_label(label: str, assessment: dict) -> bool:
    if "RAW" in label.upper() and not assessment.get("full_source_display_identity_demonstrated"):
        raise ValueError("RAW_LABEL_FORBIDDEN_WITHOUT_FULL_IDENTITY")
    return True
