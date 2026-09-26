import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "p0e4/evidence/claude_dispatch_beat_recovery_v01_execution"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClaudeDetectorReuseTests(unittest.TestCase):
    def test_recovered_source_and_exact_binding(self):
        data = json.loads((EV / "CLAUDE_EXISTING_DETECTOR_MASTER2_ANALYSIS_V01.json").read_text())
        self.assertEqual("670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2", data["source_binding"]["sha256"])
        self.assertEqual("690e58ebec8f9e6979d0ec8a2d835c5b2db31c9e46249cc51d290fe157854dbb", sha(EV / "detector/app.py"))
        self.assertEqual("04fa93aff2847eaa9ae7b8542192ca37892c46b6b149c5235360a5c14abe3e97", sha(EV / "detector/clip_fx.py"))
        self.assertLess(abs(data["analysis"]["coverage_end_s"] - 214.4), 0.001)

    def test_policy_stays_off_and_unselected(self):
        data = json.loads((ROOT / "p0e4/resolve/templates/UNCHAINED_PERFORMANCE_TEMPLATE_V01/motion_policy.json").read_text())
        self.assertFalse(data["default_enabled"])
        self.assertEqual("UNSELECTED", data["selected_policy_version"])
        self.assertFalse(data["detector_binding"]["effect_mapping_selected"])

    def test_gemini_does_not_pick_winner(self):
        data = json.loads((EV / "GEMINI_CONTINUOUS_TREATMENTS_FROM_VALIDATED_MAP_V01.json").read_text())
        self.assertFalse(data["winner_selected"])
        self.assertEqual({"treatment_A_CONTROLLED_GROOVE", "treatment_B_STRONGER_PERFORMANCE_ENERGY"}, set(data["treatments"]))

    def test_master_state_integrity_hold_recorded(self):
        data = json.loads((EV / "ACCEPTANCE_V01.json").read_text())
        self.assertFalse(data["master_state"]["updated"])
        self.assertTrue(data["master_state"]["pointer_unchanged"])
