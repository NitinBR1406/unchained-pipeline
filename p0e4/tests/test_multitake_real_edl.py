import copy
import unittest

from multitake.real_edl import digest, validate_real_edl


class RealEdlTests(unittest.TestCase):
    def fixtures(self):
        sync = {"set_sha256": digest(b"set"), "takes": [{"asset_id": "t", "take_usable_start_ms": 10,
                 "take_usable_end_ms": 1010}]}
        evidence = digest(b"range")
        intel = {"intelligence_sha256": digest(b"intel"), "programme_duration_ms": 1000,
                 "take_observations": [{"asset_id": "t", "ranges": [{"asset_id": "t", "start_ms": 0,
                 "end_ms": 1000, "evidence_sha256": evidence}]}]}
        edl = {"schema": "MULTI_TAKE_EDIT_DECISION_LIST_V01", "scope": "PRIVATE_AAKHRI_ISHQ_ACCEPTANCE_ONLY",
               "synchronized_take_set_sha256": sync["set_sha256"], "intelligence_sha256": intel["intelligence_sha256"],
               "filename_semantics_used": False, "frame_quantization": {"max_bridge_ms": 10},
               "segments": [{"segment_id": "s", "take_asset_id": "t", "timeline_start_ms": 0,
               "timeline_end_ms": 1000, "take_start_ms": 20, "take_end_ms": 1020,
               "performer_visible": True, "evidence_sha256": evidence, "reason_code": "EVIDENCE",
               "tail_frame_bridge_ms": 10}], "derivatives": []}
        return sync, intel, edl

    def test_frame_bridge_is_explicit_and_bounded(self):
        s, i, e = self.fixtures()
        self.assertEqual(validate_real_edl(s, i, e)["status"], "GREEN_MACHINE_READABLE_REAL_ACCEPTANCE")

    def test_unacknowledged_bridge_fails(self):
        s, i, e = self.fixtures(); del e["segments"][0]["tail_frame_bridge_ms"]
        with self.assertRaisesRegex(ValueError, "unacknowledged"):
            validate_real_edl(s, i, e)

    def test_excess_bridge_fails(self):
        s, i, e = self.fixtures(); e["segments"][0]["take_end_ms"] += 1
        with self.assertRaises(ValueError):
            validate_real_edl(s, i, e)

    def test_filename_inference_fails(self):
        s, i, e = self.fixtures(); e["filename_semantics_used"] = True
        with self.assertRaisesRegex(ValueError, "filename"):
            validate_real_edl(s, i, e)


if __name__ == "__main__":
    unittest.main()
