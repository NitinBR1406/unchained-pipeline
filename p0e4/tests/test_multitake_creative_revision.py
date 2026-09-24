import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from multitake.creative_revision import analyze_authoritative_audio, validate_revision_contract


class CreativeRevisionTests(unittest.TestCase):
    def test_audio_events_are_bounded_and_quiet_has_no_shake(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.wav"
            rate = 8000
            signal = np.zeros(rate * 8, dtype=np.float32)
            for second, amplitude in [(1, 0.25), (3, 0.9), (5, 0.45), (7, 0.8)]:
                signal[second * rate : second * rate + 400] = amplitude
            pcm = np.clip(signal * 32767, -32768, 32767).astype("<i2")
            with wave.open(str(path), "wb") as target:
                target.setparams((1, 2, rate, len(pcm), "NONE", "not compressed"))
                target.writeframes(pcm.tobytes())
            result = analyze_authoritative_audio(path, max_accents=5, minimum_spacing_ms=1000)
        self.assertLessEqual(len(result["events"]), 5)
        self.assertTrue(all(e["motion"] != "PUNCH_IN_MICRO_SHAKE" for e in result["events"] if e["energy_zone"] == "QUIET"))
        self.assertEqual(result["analysis"]["lyrics_or_semantics_inferred"], False)

    def test_motion_events_obey_minimum_spacing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dense.wav"
            rate = 8000
            signal = np.zeros(rate * 12, dtype=np.float32)
            for index in range(rate, len(signal), rate):
                signal[index : index + 200] = 0.8
            pcm = (signal * 32767).astype("<i2")
            with wave.open(str(path), "wb") as target:
                target.setparams((1, 2, rate, len(pcm), "NONE", "not compressed"))
                target.writeframes(pcm.tobytes())
            result = analyze_authoritative_audio(path, minimum_spacing_ms=3500)
        times = [event["time_ms"] for event in result["events"]]
        self.assertTrue(all(b - a >= 3500 for a, b in zip(times, times[1:])))

    def test_contract_fails_closed_on_unsafe_crop(self):
        contract = {
            "schema": "MULTI_TAKE_CREATIVE_REVISION_CONTRACT_V01",
            "base_framing_precedes_motion": True,
            "expected_take_ids": ["a"],
            "takes": {"a": {"base_scale": 1.1}},
            "limits": {"minimum_safe_base_scale": 1.6},
            "look": {"background_deemphasis": {"method": "SOFT_STATIC_SUBJECT_REGION_INVERTED_MASK"}},
            "motion": {"source": "AUTHORITATIVE_MASTER_AUDIO_ONLY"},
        }
        with self.assertRaisesRegex(ValueError, "UNSAFE_BASE_SCALE"):
            validate_revision_contract(contract)


if __name__ == "__main__":
    unittest.main()
