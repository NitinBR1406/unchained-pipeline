import json
import tempfile
import unittest
from pathlib import Path

from controller import master_recovery_v1620 as recovery
from control_loop.state_model import derive


class MasterRecoveryV1620Tests(unittest.TestCase):
    def test_source_failure_and_additive_recovery(self):
        report = recovery.forensic_report()
        self.assertEqual(report["first_failure"], "tamper detected at seq 31")
        self.assertEqual(report["malformed_index"], 34)
        self.assertFalse(report["historical_source_mutated"])
        with tempfile.TemporaryDirectory() as directory:
            ledger = recovery.build_recovered_ledger(Path(directory) / "ledger.jsonl")
            records = ledger.read_all()
            self.assertEqual(len(records), 35)
            self.assertEqual(records[-1]["event_id"], "p0e4-v1620-master-integrity-recovery")
            self.assertFalse(records[-1]["inputs"]["malformed_record_replayed"])
            self.assertEqual(derive(ledger, keyring={})["state_version"], 35)

    def test_projection_is_replayable_and_preserves_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = recovery.build_recovered_ledger(Path(directory) / "ledger.jsonl")
            first = recovery.project(recovery.PARENT.read_bytes(), ledger)
            second = recovery.project(recovery.PARENT.read_bytes(), ledger)
            self.assertEqual(first, second)
            self.assertEqual(first["state_version"], 46)
            self.assertFalse(first["authorizations"]["PRODUCTION_DEPLOYMENT_AUTHORIZED"])
            self.assertFalse(first["authorizations"]["PUBLICATION_AUTHORIZED"])
            self.assertEqual(first["production_state"]["first_real_poster"], "PAUSED_BY_NITIN")
            self.assertFalse(first["p0e4"]["autonomous_intake_control"]["always_on_dispatcher_proven"])

    def test_recovered_semantic_events_keep_inputs_and_correct_hashes(self):
        source = recovery._load_records(recovery.SOURCE_LEDGER)
        with tempfile.TemporaryDirectory() as directory:
            records = recovery.build_recovered_ledger(Path(directory) / "ledger.jsonl").read_all()
            for index in recovery.RECOVERED_EVENT_INDEXES:
                self.assertEqual(records[index]["event_id"], source[index]["event_id"])
                self.assertEqual(records[index]["inputs"], source[index]["inputs"])
                self.assertNotEqual(records[index]["input_hash"], source[index]["input_hash"])


if __name__ == "__main__":
    unittest.main()
