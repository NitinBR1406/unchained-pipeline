import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "p0e4/evidence/aakhri_factory_realization_v01"


class AakhriFactoryRealizationTests(unittest.TestCase):
    def load(self, name):
        return json.loads((EVIDENCE / name).read_text())

    def test_exact_input_bindings(self):
        ingest = self.load("INGEST_RECEIPT.json")
        self.assertEqual(ingest["raw"]["sha256"], "50144b7d4754355cdfa69a2be626709116e5aead1faa566bbb4e1ab361ea8790")
        self.assertEqual(ingest["authoritative_audio"]["sha256"], "670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2")
        self.assertEqual(ingest["status"], "HASH_BOUND")

    def test_final_outputs_decode_and_independent_qc(self):
        qc = self.load("TECHNICAL_QC_V01.json")
        independent = self.load("INDEPENDENT_GEMINI_QC_RUN2.json")
        self.assertEqual(len(qc["outputs"]), 5)
        self.assertTrue(all(row["decode_status"] == "COMPLETE" for row in qc["outputs"]))
        self.assertEqual(len(independent["reviewed_files"]), 5)
        self.assertTrue(all(row["verdict"] == "PASS" for row in independent["reviewed_files"]))
        self.assertEqual(independent["package_verdict"], "ACCEPT_PRIVATE_POST_READY")

    def test_repair_is_bounded_and_inputs_unchanged(self):
        repair = self.load("BOUNDED_REPAIR_RECEIPT.json")
        run2 = self.load("RESOLVE_RUN2_RECEIPT.json")
        self.assertFalse(repair["scope_expanded"])
        self.assertTrue(run2["original_restored"])
        self.assertEqual(run2["inputs_before"], run2["inputs_after"])
        self.assertEqual(len(run2["outputs"]), 5)

    def test_post_ready_is_private_and_human_gated(self):
        manifest = self.load("POST_READY_MANIFEST.json")
        next_ready = self.load("NEXT_READY.json")
        self.assertEqual(manifest["status"], "POST_READY_WAITING_FOR_NITIN")
        self.assertEqual(manifest["stage_outcomes"]["RIGHTS_ROUTING"], "RIGHTS_HOLD")
        self.assertFalse(manifest["publish_ready"])
        self.assertFalse(manifest["production_deployment_authorized"])
        self.assertFalse(manifest["publication_authorized"])
        self.assertEqual(manifest["first_real_poster"], "PAUSED_BY_NITIN")
        self.assertEqual(next_ready["status"], "WAITING_FOR_NITIN")
        self.assertFalse(next_ready["publish_approval_requested"])

    def test_no_unsupported_lyric_or_publication_metadata(self):
        metadata = self.load("CAPTIONS_METADATA_V01.json")
        self.assertEqual(metadata["lyrics_caption_status"], "NOT_PRODUCED_SOURCE_UNAVAILABLE")
        self.assertEqual(metadata["publication_metadata_status"], "NOT_CREATED")
        self.assertIsNone(metadata["release_caption"])
        self.assertIsNone(metadata["rights_claim"])


if __name__ == "__main__":
    unittest.main()
