import copy
import json
import unittest
from pathlib import Path

from multitake.hlg_richness_calibration import VARIANTS, assess_candidate_metrics, validate_contract, verify_render_plan


ROOT = Path(__file__).parents[1]


class HLGRichnessCalibrationTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "evidence/aakhri_multitake_real_v01/r6/HLG_COLOR_RICHNESS_CALIBRATION_V01.json"
        self.contract = json.loads(path.read_text())

    def test_contract_green(self):
        self.assertTrue(validate_contract(self.contract))

    def test_rec709_and_full_master_remain_forbidden(self):
        bad = copy.deepcopy(self.contract); bad["forbidden"].remove("REC709_CONVERSION")
        with self.assertRaisesRegex(ValueError, "FORBIDDEN_SET"):
            validate_contract(bad)
        bad = copy.deepcopy(self.contract); bad["full_master_render_authorized"] = True
        with self.assertRaisesRegex(ValueError, "FULL_MASTER"):
            validate_contract(bad)

    def test_only_monotonic_bounded_saturation_changes(self):
        bad = copy.deepcopy(self.contract)
        bad["variant_recipes"]["R2_MEDIUM_RICHNESS"]["cdl"]["Power"] = "0.98 1.0 1.0"
        with self.assertRaisesRegex(ValueError, "NON_CHROMA_CHANGE"):
            validate_contract(bad)
        bad = copy.deepcopy(self.contract)
        bad["variant_recipes"]["R3_STRONG_RICHNESS"]["cdl"]["Saturation"] = 1.2
        with self.assertRaisesRegex(ValueError, "SATURATION_BOUNDS"):
            validate_contract(bad)

    def test_matrix_and_no_fusion(self):
        plan = {"full_master": False, "segments": [
            {"scene_index": scene, "variant": variant, "fusion_tools": [], "mask_used": False, "blur_used": False}
            for scene in range(1, 5) for variant in VARIANTS]}
        self.assertTrue(verify_render_plan(plan))
        plan["segments"][0]["mask_used"] = True
        with self.assertRaisesRegex(ValueError, "FORBIDDEN_FINISHING"):
            verify_render_plan(plan)

    def test_metric_fail_closed_rules(self):
        identity = {"luma_mean": .4, "luma_p05": .1, "luma_p95": .8, "clip_low_pct": 0,
                    "clip_high_pct": 0, "saturation_p99": .5, "skin_hue_median_degrees": 25}
        limits = {"max_luma_delta": .01, "max_added_clip_pct": .01,
                  "max_saturation_p99": .9, "max_skin_hue_shift_degrees": 2}
        self.assertEqual(assess_candidate_metrics(identity, dict(identity), limits)["status"], "GREEN")
        bad = dict(identity); bad["skin_hue_median_degrees"] = 30
        self.assertEqual(assess_candidate_metrics(identity, bad, limits)["status"], "HOLD")

    def test_persisted_qc_and_human_gate(self):
        root = ROOT / "evidence/aakhri_multitake_real_v01/r6"
        qc = json.loads((root / "R6_HDR_SCOPES_GAMUT_SKIN_QC_V01.json").read_text())
        self.assertEqual(qc["status"], "GREEN")
        self.assertEqual(len(qc["rows"]), 16)
        self.assertTrue(all(row["status"] == "GREEN" for row in qc["rows"]))
        timing = json.loads((root / "R6_HLG_MATRIX_SAMPLE_TIMING_QC_V01.json").read_text())
        self.assertEqual(timing["duration_bearing_video_frames"], 480)
        gate = json.loads((root / "NEXT_READY.json").read_text())
        self.assertEqual(gate["state"], "WAITING_FOR_NITIN_R6_COLOR_RICHNESS_SELECTION")
        self.assertFalse(gate["gemini_selected_winner"])

    def test_persisted_output_remains_hlg(self):
        path = ROOT / "evidence/aakhri_multitake_real_v01/r6/R6_OUTPUT_COLOR_METADATA_V01.json"
        output = json.loads(path.read_text())["output"]
        ext = output["format_descriptions"][0]["extensions_safe"]
        self.assertGreaterEqual(ext["BitsPerComponent"], 10)
        self.assertEqual(ext["CVImageBufferColorPrimaries"], "ITU_R_2020")
        self.assertEqual(ext["CVImageBufferTransferFunction"], "ITU_R_2100_HLG")
        self.assertEqual(ext["CVImageBufferYCbCrMatrix"], "ITU_R_2020")


if __name__ == "__main__": unittest.main()
