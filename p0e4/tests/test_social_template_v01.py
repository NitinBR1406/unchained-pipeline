import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "p0e4/evidence/first_publish_ready_clip_fasttrack_v01_execution"
TPL = ROOT / "p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/config.json"


def load(path):
    return json.loads(path.read_text())


class SocialTemplateV01Tests(unittest.TestCase):
    def test_r2_is_about_twenty_percent_larger_and_preserves_clearance(self):
        review = load(EVID / "r2_caption_size/CAPTION_TREATMENT_REVIEW_R2.json")
        self.assertEqual(review["status"], "READY_FOR_NITIN_REVIEW")
        self.assertEqual(review["comparison_controls"]["size_multiplier"], 1.2)
        self.assertEqual(review["next_gate"], "NITIN_SELECTS_REVISED_TREATMENT_A_OR_B")
        self.assertFalse(review["publication_authorized"])
        for treatment in review["treatments"]:
            self.assertEqual(treatment["mobile_visual_check"], "PASS_READABLE_AT_360X640")
            self.assertEqual(treatment["face_mouth_exclusion"], "PASS_NO_TEXT_OVER_EYES_NOSE_MOUTH")
            self.assertEqual(treatment["frame_edge_check"], "PASS_NO_CLIPPING")
            for element in treatment["elements"]:
                self.assertAlmostEqual(element["configured_size_change_percent"], 20.0, places=1)
                self.assertGreaterEqual(element["rendered_width_change_percent"], 19.5)
                self.assertLessEqual(element["rendered_width_change_percent"], 20.5)

    def test_caption_candidates_are_larger_native_and_mobile_reviewable(self):
        review = load(EVID / "CAPTION_TREATMENT_REVIEW_V01.json")
        self.assertEqual(review["status"], "READY_FOR_NITIN_REVIEW")
        self.assertEqual(review["comparison_controls"]["full_output_px"], [1080, 1920])
        self.assertEqual(review["comparison_controls"]["phone_output_px"], [360, 640])
        self.assertEqual(review["next_gate"], "NITIN_SELECTS_TREATMENT_A_OR_B")
        self.assertFalse(review["publication_authorized"])
        for treatment in review["treatments"]:
            self.assertFalse(treatment["face_mouth_obscured"])
            self.assertTrue(treatment["full_resolution_asset"]["readback_verified"])
            self.assertTrue(treatment["phone_scale_asset"]["readback_verified"])
            for element in treatment["elements"]:
                self.assertIn(element["font_readback"], {"Montserrat", "Cinzel"})
                self.assertIn(element["style_readback"], {"Medium", "SemiBold"})
                self.assertGreater(element["mapped_1080_output_px"]["width"], 140)
                self.assertGreaterEqual(element["mapped_1080_output_px"]["height"], 37)

    def test_template_fails_closed_on_unverified_lyrics_and_publication(self):
        template = load(TPL)
        lyric = next(x for x in template["sections"] if x["id"] == "SELECTIVE_LYRICS")
        self.assertEqual(lyric["unverified_behavior"], "OMIT")
        self.assertFalse(template["lyrics_may_be_invented"])
        self.assertFalse(template["effects_default_enabled"])
        package = load(EVID / "FIRST_PUBLISH_REVIEW_PACKAGE_DRAFT_V01.json")
        self.assertFalse(package["publication_authorized"])
        self.assertFalse(package["scheduled"])
        self.assertFalse(package["uploaded_to_social"])

    def test_platform_presets_are_distinct_and_not_claimed_official_geometry(self):
        preflight = load(EVID / "PLATFORM_PREFLIGHT_SOURCE_V01.json")
        ids = {x["id"] for x in preflight["presets"]}
        self.assertEqual(ids, {"REELS_CONSERVATIVE_PREVIEW_V01", "TIKTOK_CONSERVATIVE_PREVIEW_V01", "SHORTS_CONSERVATIVE_PREVIEW_V01"})
        self.assertEqual(preflight["numeric_margin_status"], "INTERNAL_CONSERVATIVE_ENGINEERING_PRESETS_NOT_CLAIMED_AS_OFFICIAL_PIXEL_REQUIREMENTS")

    def test_rhythm_revision_does_not_upgrade_detector_labels(self):
        rhythm = load(EVID / "STRONGER_PERFORMANCE_ENERGY_V03_PREPARED.json")
        self.assertEqual(rhythm["status"], "PREPARED_NOT_RENDERED_WAITING_CAPTION_SELECTION")
        self.assertFalse(rhythm["rules"]["effect_on_every_beat"])
        self.assertFalse(rhythm["rules"]["band_labels_as_kick_snare"])
        self.assertFalse(rhythm["rules"]["every_fourth_beat_as_downbeat"])
        self.assertTrue(all(x["status"] == "PREPARED_NOT_RENDERED" for x in rhythm["prepared_event_reviews"]))


if __name__ == "__main__":
    unittest.main()
