import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff as h
from control_loop.control_loop import CrashInjected


class HandoffTests(unittest.TestCase):
    def test_real_repo_is_blocked_without_inventing_approval(self):
        intake = h.inspect()
        self.assertEqual(intake['approvals_observed']['NITIN_FINAL_VIDEO_APPROVAL']['decision'], 'APPROVE')
        self.assertIn('FINAL_VIDEO_SHA_UNBOUND', intake['blockers'])
        self.assertIn('RIGHTS_NOT_PASS', intake['blockers'])
        self.assertFalse(intake['publish_ready'])
        self.assertNotIn('NITIN_PUBLISH_APPROVAL', intake['approvals_observed'])

    def test_replay_restart_and_independent_work(self):
        with tempfile.TemporaryDirectory() as d:
            first = h.run(d)
            second = h.run(d)
            self.assertEqual(first, second)
            self.assertEqual(first['backlog_summary']['completed'], 2)
            self.assertEqual(first['backlog_summary']['blocked'], 1)
            self.assertEqual(first['authoritative_master_state_version'], 10)
            events = [json.loads(x) for x in (Path(d)/'EVENT_LEDGER.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['event_type']=='TASK_RESULT' for e in events), 2)
            self.assertFalse(any(e['event_type']=='HUMAN_GATE_GRANTED' for e in events))
            self.assertEqual(first['intake']['first_real_poster'], 'PAUSED_BY_NITIN')
            self.assertTrue(all(v is False for v in first['intake']['authorizations'].values()))

    def test_adapter_forbids_release_and_is_idempotent_before_store_record(self):
        with tempfile.TemporaryDirectory() as d:
            adapter = h.ReadOnlyAdapter(d, h.inspect())
            with self.assertRaises(PermissionError):
                adapter({'task_id':'AKI_RELEASE'}, 'job', 1)
            t = {'task_id':'AKI_INTAKE'}
            a = adapter(t, 'job', 1)
            before = (Path(d)/'AKI_INTAKE.json').stat().st_mtime_ns
            self.assertEqual(a, adapter(t, 'job', 2))
            self.assertEqual(before, (Path(d)/'AKI_INTAKE.json').stat().st_mtime_ns)
            with self.assertRaises(ValueError):
                adapter(t, 'different-job', 3)

    def test_frozen_gate_semantics_nonblocking_TEST_ONLY(self):
        # Synthetic gate contract test, explicitly NOT real AKI readiness evidence.
        with tempfile.TemporaryDirectory() as d:
            loop = h.DurableControlLoop(d, keyring={}, executor=h.ReadOnlyAdapter(d, h.inspect()))
            loop.backlog.tasks = [h.task('TEST_ONLY_PUBLISH_GATE', 1, 'test', 'NITIN_PUBLISH_APPROVAL'),
                                  h.task('INDEPENDENT_GOVERNANCE_AUDIT', 2, 'test')]
            loop.backlog.save(); loop.run()
            self.assertEqual(loop.backlog.by_id('TEST_ONLY_PUBLISH_GATE')['status'], 'WAITING_FOR_NITIN')
            self.assertEqual(loop.backlog.by_id('INDEPENDENT_GOVERNANCE_AUDIT')['status'], 'COMPLETED')
            self.assertEqual(loop.master_state()['approvals'], {})

    def test_crash_after_effect_recovers_without_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            adapter = h.ReadOnlyAdapter(d, h.inspect())
            def crash(boundary, ctx):
                if boundary == 'after_side_effect': raise CrashInjected()
            loop = h.DurableControlLoop(d, keyring={}, executor=adapter, crash_hook=crash)
            loop.backlog.tasks = [h.task('AKI_INTAKE', 1, 'test')]; loop.backlog.save()
            with self.assertRaises(CrashInjected): loop.run()
            before = (Path(d)/'AKI_INTAKE.json').stat().st_mtime_ns
            restarted = h.DurableControlLoop(d, keyring={}, executor=adapter, clock=h.Clock(1100))
            restarted.run()
            self.assertEqual(before, (Path(d)/'AKI_INTAKE.json').stat().st_mtime_ns)
            self.assertEqual(restarted.backlog.summary()['completed'], 1)

    def test_input_drift_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            h.run(d)
            (Path(d)/'INPUT_BINDING.json').write_text('{"sha256":"wrong"}')
            with self.assertRaises(ValueError): h.run(d)

    def test_governance_flags_rejected_even_truthy_string(self):
        for value in (True, 'false', 0, None):
            with tempfile.TemporaryDirectory() as d:
                for p in h.INPUTS:
                    target = Path(d)/p; target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((h.ROOT/p).read_bytes())
                path = Path(d)/h.STATE; state = json.loads(path.read_text())
                state['authorizations']['PUBLICATION_AUTHORIZED'] = value
                path.write_text(json.dumps(state))
                with self.assertRaises(ValueError): h.inspect(Path(d))

if __name__ == '__main__': unittest.main()
