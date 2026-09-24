import copy
import json
import unittest
from pathlib import Path

from multitake.source_color_management import (
    HLG_TAGS, assess_roundtrip, assert_reference_label, classify_source,
    validate_reference_names, validate_resolve_hlg_settings,
)


def metadata(bits=10, tags=None, dolby=True):
    atoms = {"dvvC": {"byte_count": 24}} if dolby else {}
    values = tags or HLG_TAGS
    return {"video": {"bits_per_component": bits, "format_description_extensions": {
        "ColorPrimaries": values["color_primaries"],
        "TransferFunction": values["transfer_function"],
        "YCbCrMatrix": values["ycbcr_matrix"],
        "SampleDescriptionExtensionAtoms": atoms,
    }}}


class SourceColorManagementTests(unittest.TestCase):
    def test_hlg_dolby_source_is_evidence_classified(self):
        row = classify_source(metadata())
        self.assertEqual(row["source_color_space"], "Rec.2100 HLG")
        self.assertTrue(row["dolby_vision_metadata_present"])

    def test_ambiguous_or_8bit_source_fails_closed(self):
        bad = copy.deepcopy(HLG_TAGS); bad["transfer_function"] = "ITU_R_709_2"
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            classify_source(metadata(tags=bad))
        with self.assertRaisesRegex(ValueError, "BIT_DEPTH"):
            classify_source(metadata(bits=8))

    def test_reference_concepts_must_be_distinct(self):
        refs = {
            "SOURCE_BYTES_REFERENCE": {"kind": "HASH_BOUND_CAMERA_ORIGINALS"},
            "RESOLVE_DECODE_REFERENCE": {"kind": "DECODED_UNGRADED_VIEW"},
            "IDENTITY_ROUNDTRIP_REFERENCE": {"kind": "ZERO_CREATIVE_GRADE_RENDER"},
        }
        self.assertTrue(validate_reference_names(refs))
        refs.pop("RESOLVE_DECODE_REFERENCE")
        with self.assertRaisesRegex(ValueError, "CONCEPT_SET"):
            validate_reference_names(refs)

    def test_resolve_hlg_settings_are_explicit(self):
        settings = {
            "colorScienceMode": "davinciYRGBColorManaged", "isAutoColorManage": "0",
            "colorSpaceInput": "Rec.2100 HLG", "colorSpaceTimeline": "Rec.2100 HLG",
            "colorSpaceOutput": "Rec.2100 HLG",
        }
        self.assertTrue(validate_resolve_hlg_settings(settings))
        settings["colorSpaceOutput"] = "Rec.709 (Scene)"
        with self.assertRaisesRegex(ValueError, "colorSpaceOutput"):
            validate_resolve_hlg_settings(settings)

    def test_dolby_loss_prevents_full_identity_and_raw_label(self):
        result = assess_roundtrip(metadata(), metadata(dolby=False))
        self.assertTrue(result["base_layer_hlg_identity_supported"])
        self.assertFalse(result["full_source_display_identity_demonstrated"])
        with self.assertRaisesRegex(ValueError, "RAW_LABEL_FORBIDDEN"):
            assert_reference_label("RAW_REFERENCE", result)
        self.assertTrue(assert_reference_label("IDENTITY_ROUNDTRIP_REFERENCE", result))

    def test_rec709_r5_is_not_identity(self):
        tags = dict(HLG_TAGS); tags.update({
            "color_primaries": "ITU_R_709_2", "transfer_function": "ITU_R_709_2", "ycbcr_matrix": "ITU_R_709_2"
        })
        result = assess_roundtrip(metadata(), metadata(bits=8, tags=tags, dolby=False))
        self.assertFalse(result["base_layer_hlg_identity_supported"])

    def test_persisted_reference_contract_and_gate(self):
        root = Path(__file__).parents[1] / "evidence/aakhri_multitake_real_v01/source_color_forensics"
        refs = json.loads((root / "REFERENCE_CONCEPTS_V01.json").read_text())
        self.assertTrue(validate_reference_names(refs))
        self.assertFalse(refs["IDENTITY_ROUNDTRIP_REFERENCE"]["full_source_display_identity_demonstrated"])
        gate = json.loads((root / "NEXT_READY.json").read_text())
        self.assertIn(gate["state"], {
            "WAITING_FOR_NITIN_SOURCE_COLOR_REFERENCE_VALIDATION",
            "VALIDATED_BY_NITIN_SUPERSEDED_BY_R6_CALIBRATION",
        })
        self.assertTrue(gate["r5_creative_selection_suspended"])

    def test_all_four_persisted_sources_are_hlg_dolby(self):
        path = Path(__file__).parents[1] / "evidence/aakhri_multitake_real_v01/source_color_forensics/SOURCE_BYTES_REFERENCE_V01.json"
        rows = json.loads(path.read_text())["sources"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(row["bits_per_component"], 10)
            self.assertEqual(row["primaries"], "ITU_R_2020")
            self.assertEqual(row["transfer"], "ITU_R_2100_HLG")
            self.assertEqual(row["matrix"], "ITU_R_2020")
            self.assertEqual(row["dolby_vision_dvvC"]["data_bytes"], 24)


if __name__ == "__main__":
    unittest.main()
