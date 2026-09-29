import unittest
from pathlib import Path

from p0e4.resolve.aakhri_premium_style_sample_v02_contract import (
    CHAIN_LOGO_SHA256,
    SAMPLE_FRAMES,
    WINDOWS,
    sha256,
    validate_windows,
)


class PremiumStyleContractTests(unittest.TestCase):
    def test_windows_are_disjoint_and_bounded(self):
        validate_windows()
        self.assertEqual(WINDOWS, {"logo": (0, 53), "hook": (54, 88), "title_artist": (89, 179)})
        self.assertEqual(SAMPLE_FRAMES, (0, 179))

    def test_logo_binding_matches_v13_asset(self):
        root = Path(__file__).resolve().parents[2]
        logo = root / ".local/aakhri-integrated-preview-v13-chain-caption-repair/unchained_chain_emblem.png"
        self.assertEqual(sha256(logo), CHAIN_LOGO_SHA256)

    def test_overlap_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "overlap"):
            validate_windows({"logo": (0, 54), "hook": (54, 88), "title_artist": (89, 179)})


if __name__ == "__main__":
    unittest.main()
