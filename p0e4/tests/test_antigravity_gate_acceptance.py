import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('agy_gate', Path(__file__).parents[1] / 'tools/antigravity_gate_acceptance.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class GateTests(unittest.TestCase):
    def test_gate_denies_all_and_malformed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = Path(directory) / 'gate.py'
            gate.write_text(M.GATE)
            for text in ['{}', 'not json'] + [json.dumps({'toolCall': {'name': name}}) for name in
                    ('view_file', 'write_to_file', 'run_command', 'mcp_any', 'invoke_subagent', 'unknown_future_tool')]:
                p = subprocess.run([sys.executable, '-B', str(gate)], input=text, text=True, capture_output=True)
                self.assertEqual(p.returncode, 0)
                self.assertEqual(json.loads(p.stdout)['decision'], 'deny')

    def test_denies_when_logging_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = Path(directory) / 'gate.py'
            gate.write_text(M.GATE)
            (Path(directory) / 'denials.jsonl').mkdir()
            p = subprocess.run([sys.executable, '-B', str(gate)], input='{}', text=True, capture_output=True)
            self.assertEqual(json.loads(p.stdout)['decision'], 'deny')

    def test_wildcard_and_quoting(self):
        entry = M.hooks(Path('/a b/gate.py'), '/python path/python')['unchained-qc-deny-all-v01']['PreToolUse'][0]
        self.assertEqual(entry['matcher'], '*')
        self.assertEqual(entry['hooks'][0]['command'], "'/python path/python' -B '/a b/gate.py'")

    def test_no_attempts_not_pass(self):
        status, checks = M.evaluate([], 'SUCCESS', 'secret', False, False, 0, True)
        self.assertEqual(status, 'HOLD')
        self.assertEqual(checks['run_command'], 'NIET BEWEZEN')

    def test_three_attempts_only_limited_acceptance(self):
        events = [{'tool': n, 'decision': 'deny'} for n in ('view_file', 'write_to_file', 'run_command')]
        self.assertEqual(M.evaluate(events, '', 'secret', False, False, 0, True)[0], 'OBSERVED_GATE_TEST_ONLY')
        for args in [('', 'secret', True, False, 0, True), ('secret', 'secret', False, False, 0, True),
                     ('', 'secret', False, True, 0, True), ('', 'secret', False, False, 1, True),
                     ('', 'secret', False, False, 0, False)]:
            self.assertEqual(M.evaluate(events, *args)[0], 'HOLD')

    def test_existing_configuration_blocks_without_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = home / 'qc'
            root.mkdir()
            self.assertEqual(M.config_conflicts(home, root), [])
            config = home / '.gemini/config/hooks.json'
            config.parent.mkdir(parents=True)
            config.write_text('{}')
            self.assertIn('global_hooks', M.config_conflicts(home, root))
            self.assertEqual(config.read_text(), '{}')

    def test_settings_customization_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / '.gemini/antigravity-cli/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('{"nested":{"hooks":{"example":true}}}')
            self.assertIn('settings_customization_present', M.config_conflicts(home, home / 'qc'))


if __name__ == '__main__':
    unittest.main()
