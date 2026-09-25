import copy
import json
import unittest
from pathlib import Path

from p0e4.resolve.performance_template import TemplateContractError, build_dry_run_plan


ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "p0e4/resolve/templates/UNCHAINED_PERFORMANCE_TEMPLATE_V01/job.example.json"


class PerformanceTemplateTests(unittest.TestCase):
    def setUp(self):
        self.job = json.loads(JOB.read_text())

    def test_default_is_effect_and_caption_safe(self):
        plan = build_dry_run_plan(self.job)
        self.assertEqual([], plan["effect_nodes_enabled"])
        self.assertEqual(3, len(plan["effect_nodes_bypassed"]))
        self.assertFalse(plan["caption_enabled"])
        self.assertFalse(plan["render_requested"])

    def test_effect_cannot_enable_without_nitin_policy(self):
        job = copy.deepcopy(self.job)
        job["motion_binding"]["effect_switches"]["micro_push"] = True
        with self.assertRaisesRegex(TemplateContractError, "SELECTED_POLICY"):
            build_dry_run_plan(job)

    def test_effect_cannot_enable_on_unvalidated_events(self):
        job = copy.deepcopy(self.job)
        job["motion_binding"]["effect_switches"]["micro_push"] = True
        job["motion_binding"]["selected_policy_version"] = "NITIN_POLICY_V01"
        with self.assertRaisesRegex(TemplateContractError, "VALIDATED_EVENTS"):
            build_dry_run_plan(job)

    def test_lyric_caption_fails_without_verified_text(self):
        job = copy.deepcopy(self.job)
        job["style_binding"]["caption_mode"] = "VERIFIED_LYRIC_ONLY"
        job["style_binding"]["brand_typography_status"] = "VERIFIED"
        with self.assertRaisesRegex(TemplateContractError, "VERIFIED_TEXT"):
            build_dry_run_plan(job)

    def test_non_hlg_input_fails_closed(self):
        job = copy.deepcopy(self.job)
        job["source_binding"]["source_color_metadata"]["input"] = "Rec.709 Gamma 2.4"
        with self.assertRaisesRegex(TemplateContractError, "NON_HLG"):
            build_dry_run_plan(job)

    def test_source_change_has_bounded_invalidation(self):
        plan = build_dry_run_plan(self.job)
        self.assertIn("alignment_map", plan["invalidation_graph"]["alignment"])
        self.assertNotIn("color_preset_sha256", plan["invalidation_graph"]["alignment"])

    def test_continuous_policy_stays_disabled_until_joint_selection(self):
        policy_path = ROOT / "p0e4/resolve/templates/UNCHAINED_PERFORMANCE_TEMPLATE_V01/motion_policy.json"
        policy = json.loads(policy_path.read_text())
        self.assertEqual("CONTINUOUS_RHYTHMIC_UNCHAINED_NITIN", policy["creative_direction"])
        self.assertIn("NO_THREE_ACCENT_CAP", policy["creative_direction_constraints"])
        self.assertEqual("UNSELECTED", policy["selected_policy_version"])
        self.assertFalse(policy["default_enabled"])
        self.assertEqual("HOLD_SOURCE_AND_OUTPUTS_NOT_RETRIEVED", policy["detector_binding"]["status"])


if __name__ == "__main__":
    unittest.main()
