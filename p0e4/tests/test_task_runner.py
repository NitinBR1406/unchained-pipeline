import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'p0e4/task_runner'))
import runner as r
import tool_gate as gate


def task():
    value = json.loads((ROOT / 'p0e4/tasks/AUTOMATED_TASK_TEMPLATE_V01.json').read_text())
    value.update(status='READY', base_commit='a' * 40)
    return value


def filename(t):
    return r.INBOX + t['task_id'] + '_R' + str(t['revision']) + '.json'


class ContractTests(unittest.TestCase):
    def test_valid_task_and_immutable_gates(self):
        t = task()
        self.assertEqual(r.validate_task(t, filename(t)), t['task_id'] + '_R1')
        for key in r.GATES:
            changed = copy.deepcopy(t); changed['governance'][key] = True
            with self.assertRaises(ValueError): r.validate_task(changed, filename(changed))

    def test_scope_bypass_and_unknown_fields_rejected(self):
        for kind in ('BUILD', 'RENDER', 'PUBLISH', 'MAKE', 'REPAIR'):
            t = task(); t['task_type'] = kind
            with self.assertRaises(ValueError): r.validate_task(t, filename(t))
        for key in ('command', 'allowedTools', 'nitin_approval', 'settings', 'outputs'):
            t = task(); t[key] = 'arbitrary'
            with self.assertRaises(ValueError): r.validate_task(t, filename(t))

    def test_traversal_secret_path_bad_hash_budget_and_draft(self):
        for path in ('p0e4/../.env', '/etc/passwd', 'p0e4/.env', 'p0e4/..\\.env'):
            t = task(); t['inputs'] = [{'path': path, 'sha256': 'b' * 64}]
            with self.assertRaises(ValueError): r.validate_task(t, filename(t))
        t = task(); t['budget']['max_attempts'] = 2
        with self.assertRaises(ValueError): r.validate_task(t, filename(t))
        t = task(); t['status'] = 'DRAFT'
        with self.assertRaises(ValueError): r.validate_task(t, filename(t))

    def test_pr_authorization_rejects_mixed_pr_fork_other_merger(self):
        pr = {'state': 'closed', 'merged_at': 'now', 'merge_commit_sha': 'a' * 40,
              'base': {'ref': r.BRANCH, 'repo': {'full_name': r.REPO}},
              'head': {'repo': {'full_name': r.REPO}}, 'merged_by': {'login': 'NitinBR1406'}}
        files = [{'status': 'added', 'filename': filename(task())}]
        config = {'merge_actors': ['NitinBR1406']}
        self.assertEqual(r.authorize_pr(pr, files, config), filename(task()))
        with self.assertRaises(ValueError): r.authorize_pr(pr, files + [{'status': 'modified', 'filename': '.claude/settings.json'}], config)
        for bad in ('head', 'merged_by'):
            changed = copy.deepcopy(pr)
            if bad == 'head': changed['head']['repo']['full_name'] = 'outsider/repo'
            else: changed['merged_by']['login'] = 'outsider'
            with self.assertRaises(ValueError): r.authorize_pr(changed, files, config)

    def test_only_existing_read_tools_can_pass_gate(self):
        script = (ROOT / '.claude/resolve/readonly_identity_probe_v01.py').read_text()
        self.assertEqual(gate.decide({'tool_name': r.STATUS, 'tool_input': {}}), 'allow')
        self.assertEqual(gate.decide({'tool_name': r.SCRIPT, 'tool_input': {'script': script}}), 'allow')
        cases = [dict(tool_name=r.SCRIPT, tool_input={'script': 'print(123)'}),
                 dict(tool_name=r.SCRIPT, tool_input={'script': script, 'unsafe': True}),
                 dict(tool_name=r.STATUS, tool_input={'launch': True})]
        cases += [dict(tool_name=name, tool_input={}) for name in
                  ('Bash', 'Write', 'Agent', 'mcp__make__activate', 'mcp__davinci_resolve__launch_resolve',
                   'mcp__davinci_resolve__run_script_unsafe', 'mcp__davinci_resolve__update_dctl')]
        for event in cases: self.assertEqual(gate.decide(event), 'deny', event)

    def test_malformed_gate_input_fails_closed(self):
        p = subprocess.run([sys.executable, str(ROOT / 'p0e4/task_runner/tool_gate.py')],
                           input=b'{bad', capture_output=True, check=True)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_cli_does_not_widen_tools_or_load_global_mcp(self):
        cmd = r.claude_command({'claude': '/fake/claude'}, ROOT, task())
        self.assertEqual(cmd[cmd.index('--tools') + 1], '')
        self.assertEqual(cmd[cmd.index('--mcp-config') + 1], '{"mcpServers":{}}')
        self.assertIn('--restricted', cmd); self.assertIn('--strict-mcp-config', cmd)
        self.assertNotIn('--allowedTools', cmd); self.assertNotIn('--dangerously-skip-permissions', cmd)
        settings = json.loads(cmd[cmd.index('--settings') + 1])
        original = json.loads((ROOT / '.claude/settings.json').read_text())
        self.assertEqual(settings['permissions'], original['permissions'])
        self.assertEqual(settings['hooks']['PreToolUse'][:-1], original['hooks']['PreToolUse'])

    def test_secret_filter(self):
        self.assertFalse(r.contains_secret(b'Ordinary result without credentials'))
        self.assertTrue(r.contains_secret(b'ghp_' + b'x' * 30))
        self.assertTrue(r.contains_secret(b'-----BEGIN RSA PRIVATE KEY-----'))
        self.assertTrue(r.contains_secret(b'"password": "example-secret"'))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name); self.repo = self.home / 'repo'; self.repo.mkdir()
        self.state = self.home / 'state'; self.state.mkdir()
        r.git(self.repo, 'init', '-q')
        r.git(self.repo, 'config', 'user.name', 'offline-test')
        r.git(self.repo, 'config', 'user.email', 'offline@localhost')
        for path in r.PINNED:
            out = self.repo / path; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((ROOT / path).read_bytes())
        pointer = json.loads((ROOT / 'p0e4/MASTER_STATE_LATEST.json').read_text())
        statefile = self.repo / pointer['path']; statefile.parent.mkdir(parents=True, exist_ok=True)
        statefile.write_bytes((ROOT / pointer['path']).read_bytes())
        r.git(self.repo, 'add', '.'); r.git(self.repo, 'commit', '-qm', 'offline baseline')
        self.baseline = r.git(self.repo, 'rev-parse', 'HEAD').decode().strip()
        self.task = task(); self.task['base_commit'] = self.baseline
        path = self.repo / filename(self.task); path.parent.mkdir(parents=True); path.write_text(json.dumps(self.task))
        r.git(self.repo, 'add', '.'); r.git(self.repo, 'commit', '-qm', 'offline merged task')
        self.commit = r.git(self.repo, 'rev-parse', 'HEAD').decode().strip()
        (self.repo / '.git/FETCH_HEAD').write_text(self.commit + '\n')
        self.config = {'repo': str(self.repo), 'baseline': self.baseline,
                       'pins': {p: r.sha((self.repo / p).read_bytes()) for p in r.PINNED},
                       'merge_actors': ['NitinBR1406'], 'gh': '/fake/gh', 'claude': '/fake/claude', 'codex': '/fake/codex'}
        self.pr = {'number': 11, 'state': 'closed', 'merged_at': '2026-09-30T12:00:00Z',
                   'merge_commit_sha': self.commit, 'base': {'ref': r.BRANCH, 'repo': {'full_name': r.REPO}},
                   'head': {'repo': {'full_name': r.REPO}}, 'merged_by': {'login': 'NitinBR1406'}}
        self.files = [{'status': 'added', 'filename': filename(self.task)}]

    def fake_github(self):
        gh = mock.Mock()
        gh.pages.side_effect = lambda path: self.files if '/files?' in path else [self.pr]
        gh.api.return_value = self.pr
        gh.deliver.return_value = 'https://github.com/example/offline'
        return gh

    def test_real_git_context_and_fake_cli_execution(self):
        claude = self.home / 'claude'
        claude.write_text('#!' + sys.executable + '\nimport json\nprint(json.dumps({"type":"result","is_error":False,"result":"Offline analysis only","session_id":"fake-session"}))\n')
        codex = self.home / 'codex'
        codex.write_text('#!' + sys.executable + '\nimport sys,pathlib\npathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text("NIET BEWEZEN: no live tests")\nprint("{\\"type\\":\\"turn.completed\\"}")\n')
        claude.chmod(0o700); codex.chmod(0o700)
        self.config.update(claude=str(claude), codex=str(codex))
        job = self.state / 'pr_11'; job.mkdir()
        result = r.execute_task(self.repo, self.commit, self.task, job, self.config)
        self.assertEqual(result['status'], 'IN_REVIEW')
        self.assertFalse(result['independent_test_execution'])
        self.assertTrue((job / 'intent.json').exists())
        self.assertIn('NIET BEWEZEN', result['codex_review'])

    def test_two_polls_invoke_once(self):
        gh = self.fake_github()
        with mock.patch.object(r, 'GitHub', return_value=gh), mock.patch.object(r, 'execute_task', return_value={'status':'IN_REVIEW'}) as execute:
            r.tick(self.config, self.state); r.tick(self.config, self.state)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(gh.deliver.call_count, 1)

    def test_ambiguous_intent_never_restarts(self):
        job = self.state / 'pr_11'; job.mkdir(); r.atomic(job / 'intent.json', {'started': True})
        gh = self.fake_github()
        with mock.patch.object(r, 'GitHub', return_value=gh), mock.patch.object(r, 'execute_task') as execute:
            r.tick(self.config, self.state)
            execute.assert_not_called()
        result = json.loads((job / 'result.json').read_text())
        self.assertEqual(result['status'], 'HOLD')

    def test_delivery_failure_retries_only_delivery(self):
        gh = self.fake_github(); gh.deliver.side_effect = [ValueError('offline'), 'delivered']
        with mock.patch.object(r, 'GitHub', return_value=gh), mock.patch.object(r, 'execute_task', return_value={'status':'IN_REVIEW'}) as execute:
            r.tick(self.config, self.state); r.tick(self.config, self.state)
            self.assertEqual(execute.call_count, 1); self.assertEqual(gh.deliver.call_count, 2)

    def test_current_pin_drift_blocks_dispatch(self):
        (self.repo / 'CLAUDE.md').write_text('altered governance')
        r.git(self.repo, 'add', '.'); r.git(self.repo, 'commit', '-qm', 'drift')
        (self.repo / '.git/FETCH_HEAD').write_bytes(r.git(self.repo, 'rev-parse', 'HEAD'))
        with mock.patch.object(r, 'GitHub', return_value=self.fake_github()), mock.patch.object(r, 'execute_task') as execute:
            with self.assertRaisesRegex(ValueError, 'CURRENT_POLICY_DRIFT'): r.tick(self.config, self.state)
            execute.assert_not_called()

    def test_duplicate_identity_different_pr_is_blocked(self):
        r.atomic(self.state / ('identity_' + self.task['task_id'] + '_R1.json'), {'task_sha256':'other', 'pr':7})
        with mock.patch.object(r, 'GitHub', return_value=self.fake_github()), mock.patch.object(r, 'execute_task') as execute:
            r.tick(self.config, self.state); execute.assert_not_called()
        result = json.loads((self.state / 'pr_11/result.json').read_text())
        self.assertEqual(result['status'], 'BLOCKED')

    def test_input_sha_mismatch_and_symlink_rejected(self):
        t = copy.deepcopy(self.task); t['inputs'] = [{'path':'p0e4/README.md','sha256':'0'*64}]
        with self.assertRaisesRegex(ValueError, 'input hash mismatch'):
            r.prepare_context(self.repo, self.commit, t, self.config)
        (self.repo / 'p0e4/link').symlink_to('/etc/passwd')
        r.git(self.repo, 'add', '.'); r.git(self.repo, 'commit', '-qm', 'symlink')
        head = r.git(self.repo, 'rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'not regular blob'): r.regular_blob(self.repo, head, 'p0e4/link')


if __name__ == '__main__':
    unittest.main(verbosity=2)
