import json
from pathlib import Path
import unittest


class PersistenceHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = Path(__file__).parents[1] / "evidence" / "aakhri_multitake_real_v01"
        cls.receipt = json.loads((cls.evidence / "PERSISTENCE_HANDOFF_RECEIPT_V01.json").read_text())

    def test_handoff_is_green_and_non_destructive(self):
        self.assertEqual(self.receipt["status"], "GREEN_NON_DESTRUCTIVE_PERSISTENCE_COMPLETE")
        policy = self.receipt["copy_policy"]
        self.assertTrue(policy["copy_never_move"])
        self.assertFalse(policy["overwrite_existing_differing_artifact"])
        self.assertTrue(policy["source_staging_untouched_and_reverified"])

    def test_all_destination_readbacks_match(self):
        mappings = self.receipt["source_to_destination"]
        file_mappings = [m for m in mappings if m["source_path"]]
        self.assertEqual(len(file_mappings), 39)
        self.assertTrue(all(m["verified"] for m in mappings))
        self.assertTrue(all(m["source_sha256"] == m["destination_sha256_readback"] for m in file_mappings))

    def test_governance_is_preserved(self):
        governance = self.receipt["governance"]
        self.assertFalse(governance["production_deployment_authorized"])
        self.assertFalse(governance["publication_authorized"])
        self.assertEqual(governance["first_real_poster"], "PAUSED_BY_NITIN")


if __name__ == "__main__":
    unittest.main()
