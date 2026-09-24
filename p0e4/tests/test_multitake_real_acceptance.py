import unittest

from multitake.real_acceptance import confidence_rubric, validate_real_inventory


class RealAcceptanceTests(unittest.TestCase):
    def test_alignment_rubric_accepts_redundant_consistent_evidence(self):
        anchors = [{"take_time_ms": i * 15000, "offset_ms": 100 + (i % 2) * 2,
                    "peak_corr": .61, "peak_margin": .08} for i in range(6)]
        r = confidence_rubric(anchors, 3.4, 64.8)
        self.assertEqual(r["status"], "GREEN")
        self.assertGreaterEqual(r["confidence_milli"], 850)

    def test_alignment_rubric_holds_low_evidence(self):
        anchors = [{"take_time_ms": i * 1000, "offset_ms": i * 100,
                    "peak_corr": .2, "peak_margin": .01} for i in range(3)]
        self.assertEqual(confidence_rubric(anchors, 25, 100)["status"], "HOLD_LOW_CONFIDENCE")

    def test_inventory_uses_content_tracks_and_exact_master(self):
        a = [
            {"file_id": "v1", "name": "wrong.wav", "bytes_read": 10, "stat_size": 10, "mtime_ns": 1, "sha256": "1"*64, "file_mime": "video/quicktime"},
            {"file_id": "v2", "name": "take", "bytes_read": 11, "stat_size": 11, "mtime_ns": 1, "sha256": "2"*64, "file_mime": "video/quicktime"},
            {"file_id": "a", "name": "audio.bin", "bytes_read": 12, "stat_size": 12, "mtime_ns": 1, "sha256": "3"*64, "file_mime": "audio/x-wav"},
        ]
        probes = {"wrong.wav": {"video_tracks": 1, "audio_tracks": 1}, "take": {"video_tracks": 1, "audio_tracks": 1},
                  "audio.bin": {"video_tracks": 0, "audio_tracks": 1}}
        r = validate_real_inventory(a, list(a), probes, "3"*64)
        self.assertEqual(r["take_count"], 2)
        self.assertFalse(r["filename_semantics_used"])

    def test_inventory_fails_closed_on_master_mismatch(self):
        a = [
            {"file_id": "v1", "name": "v1", "bytes_read": 1, "stat_size": 1, "mtime_ns": 1, "sha256": "1"*64, "file_mime": "video/quicktime"},
            {"file_id": "v2", "name": "v2", "bytes_read": 1, "stat_size": 1, "mtime_ns": 1, "sha256": "2"*64, "file_mime": "video/quicktime"},
            {"file_id": "a", "name": "a", "bytes_read": 1, "stat_size": 1, "mtime_ns": 1, "sha256": "3"*64, "file_mime": "audio/x-wav"},
        ]
        probes = {"v1": {"video_tracks": 1, "audio_tracks": 1}, "v2": {"video_tracks": 1, "audio_tracks": 1},
                  "a": {"video_tracks": 0, "audio_tracks": 1}}
        with self.assertRaises(ValueError):
            validate_real_inventory(a, a, probes, "4"*64)


if __name__ == "__main__": unittest.main()
