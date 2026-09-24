import copy
import unittest

from multitake.color_development import assess_metrics, frame_metrics, validate_color_contract


BASE = {
    "schema": "R4_COLOR_DEVELOPMENT_CONTRACT_V01",
    "stage_order": ["NORMALIZATION", "INTER_TAKE_SHOT_MATCH", "SKIN_EXPOSURE_CONTRAST", "SUBJECT_BACKGROUND_SEPARATION", "BOUNDED_CREATIVE_LOOK"],
    "preserved_r3": {"framing": True, "edl": True, "synchronization": True, "beat_motion_timing": True},
    "known_r3_defects": {"status": "CONFIRMED_UNRESOLVED"},
    "takes": {"t": {"cdl": {"Slope": "1.01 1.00 0.99", "Offset": "0.0 0.0 0.0", "Power": "1.02 1.02 1.02", "Saturation": 1.06}}},
    "subject_background_separation": {"method": "SOFT_STATIC_INVERTED_ELLIPSE_FAIL_CLOSED", "gain": .95, "saturation": .9},
}


class ColorDevelopmentTests(unittest.TestCase):
    def test_contract_green(self): self.assertTrue(validate_color_contract(BASE))
    def test_rejects_excessive_grade(self):
        bad = copy.deepcopy(BASE); bad["takes"]["t"]["cdl"]["Saturation"] = 1.5
        with self.assertRaisesRegex(ValueError, "SATURATION_BOUNDS"): validate_color_contract(bad)
    def test_rejects_edit_drift(self):
        bad = copy.deepcopy(BASE); bad["preserved_r3"]["edl"] = False
        with self.assertRaisesRegex(ValueError, "NOT_PRESERVED"): validate_color_contract(bad)
    def test_scope_metrics_and_clipping_hold(self):
        frame = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
        row = {"time_ms": 1000, "metrics": frame_metrics(frame)}
        out = assess_metrics([row], {"max_shadow_clip_pct": 2, "max_highlight_clip_pct": 2, "max_saturation_p99": .98})
        self.assertEqual(out["status"], "HOLD")


if __name__ == "__main__": unittest.main()
