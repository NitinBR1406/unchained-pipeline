"""Tests for the single shared canonicalization module."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unpipe import canonical as C
from unpipe.approvals import GATE_FINAL_VIDEO, GATE_FINAL_ASSET


class T(unittest.TestCase):
    def test_fingerprint_deterministic_and_material(self):
        a = C.compute_fingerprint("c1", "asset", "instagram", "pkg", "v1")
        self.assertEqual(a, C.compute_fingerprint("c1", "asset", "instagram", "pkg", "v1"))
        for changed in (
            C.compute_fingerprint("c2", "asset", "instagram", "pkg", "v1"),
            C.compute_fingerprint("c1", "asset2", "instagram", "pkg", "v1"),
            C.compute_fingerprint("c1", "asset", "facebook", "pkg", "v1"),
            C.compute_fingerprint("c1", "asset", "instagram", "pkg2", "v1"),
            C.compute_fingerprint("c1", "asset", "instagram", "pkg", "v2"),
        ):
            self.assertNotEqual(a, changed)

    def test_packaging_canonical_and_sha(self):
        j = C.packaging_canonical_json("p1", "Hello é")
        self.assertEqual(j, '{"caption":"Hello \\u00e9","content_id":"p1"}')
        self.assertEqual(C.packaging_sha256("p1", "cap"), C.packaging_sha256("p1", "cap"))
        self.assertNotEqual(C.packaging_sha256("p1", "cap"), C.packaging_sha256("p1", "cap2"))

    def test_scheduled_at_to_epoch_amsterdam_dst(self):
        expected = int(datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(C.scheduled_at_to_epoch("2026-06-01 12:00:00"), expected)
        expected_w = int(datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(C.scheduled_at_to_epoch("2026-01-01 12:00:00"), expected_w)

    def test_schedule_window(self):
        self.assertEqual(C.schedule_window(1000, pre=60, post=120), [940, 1120])
        self.assertEqual(C.schedule_window(5000),
                         [5000 - C.SCHEDULE_GRACE_SECONDS, 5000 + C.SCHEDULE_GRACE_SECONDS])

    def test_final_gate_for_medium(self):
        self.assertEqual(C.final_gate_for_medium(C.MEDIUM_POSTER), GATE_FINAL_ASSET)
        self.assertEqual(C.final_gate_for_medium(C.MEDIUM_VIDEO), GATE_FINAL_VIDEO)
        self.assertEqual(C.final_gate_for_medium(None), GATE_FINAL_VIDEO)
        self.assertEqual(C.final_gate_for_medium("something"), GATE_FINAL_VIDEO)


if __name__ == "__main__":
    unittest.main(verbosity=2)
