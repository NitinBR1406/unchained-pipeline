import copy
import json
import unittest
from pathlib import Path

from multitake.raw_reference_look import validate_contract, verify_render_plan


ROOT = Path(__file__).parents[1]


class RawReferenceLookTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "evidence/aakhri_multitake_real_v01/r5/RAW_REFERENCE_SUPREMACY_V01.json").read_text())

    def test_contract_green(self):
        self.assertTrue(validate_contract(self.contract))

    def test_ai_cannot_override_nitin(self):
        bad = copy.deepcopy(self.contract); bad["ai_qc_may_override_nitin"] = True
        with self.assertRaisesRegex(ValueError, "HUMAN_AUTHORITY_DRIFT"):
            validate_contract(bad)

    def test_r4_mask_is_forbidden(self):
        bad = copy.deepcopy(self.contract); bad["forbidden"].remove("R4_STATIC_INVERTED_ELLIPSE")
        with self.assertRaisesRegex(ValueError, "FORBIDDEN_SET_INCOMPLETE"):
            validate_contract(bad)

    def test_full_master_and_incomplete_matrix_fail(self):
        plan = {"full_master": False, "segments": [
            {"scene_index": s, "look": look, "fusion_tools": []}
            for s in range(1, 5) for look in ("RAW_REFERENCE", "A_RAW_PLUS", "B_NATURAL_CINEMATIC", "C_UNCHAINED_CINEMATIC")
        ]}
        self.assertTrue(verify_render_plan(plan))
        bad = copy.deepcopy(plan); bad["full_master"] = True
        with self.assertRaisesRegex(ValueError, "FULL_MASTER_RENDER_ATTEMPT"):
            verify_render_plan(bad)


if __name__ == "__main__":
    unittest.main()
