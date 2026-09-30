"""One-shot read-only host audit. Publishes only a derived report when --publish.

No model launch, Gemini login, raw transcript upload, runner update or state edit.
This cannot prove absence of all effects on the host; missing evidence stays unknown.
"""
import argparse
import base64
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import shlex
import subprocess
import sys

REPO = 'NitinBR1406/unchained-pipeline'
BRANCH = 'p0e4/slice1-production-handoff'
RESULT_COMMIT = '933cd1415b4af450872e813120452504540df63e'
RESULT_PATH = 'p0e4/evidence/task_runs/pr_2/RESULT.json'
TASK_PATH = 'p0e4/tasks/inbox/INBOX_READONLY_SMOKE_20260930_V01_R1.json'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check(ok, detail):
    return {'status': 'VERIFIED' if ok else 'FAILED', 'detail': detail}


def unknown(detail):
    return {'status': 'NIET BEWEZEN', 'detail': detail}


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16000000:
        raise ValueError('missing/unsafe/oversized evidence file')
    return path.read_bytes()


def command(argv):
    p = subprocess.run(argv, capture_output=True, timeout=60)
    if p.returncode:
        raise ValueError('command failed: ' + Path(argv[0]).name)
    return p.stdout


def blob(repo, commit, path):
    return command(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), 'show', commit + ':' + path])


def tools_in_transcript(raw):
    """Inspect only actual assistant message content; never count quoted tool text."""
    names = []
    assistants = 0
    sessions = set()
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get('sessionId'):
            sessions.add(event['sessionId'])
        if event.get('type') != 'assistant':
            continue
        assistants += 1
        for block in event.get('message', {}).get('content', []):
            if isinstance(block, dict) and block.get('type') in ('tool_use', 'server_tool_use'):
                names.append(block.get('name', 'UNKNOWN'))
    return assistants, sessions, dict(Counter(names))


def audit(home, applications=None):
    service = home / 'Library/Application Support/UnchainedTaskRunner'
    job = service / 'state/pr_2'
    repo = service / 'repo'
    published = json.loads(blob(repo, RESULT_COMMIT, RESULT_PATH))
    task = json.loads(blob(repo, published['merge_commit'], TASK_PATH))
    results = {}
    observations = {}
    def probe(name, fn):
        try:
            results[name] = fn()
        except Exception as exc:
            results[name] = unknown(type(exc).__name__ + ': required evidence unavailable or unparseable')

    for engine in ('claude', 'codex'):
        probe(engine + '_receipt_hash', lambda engine=engine: check(
            digest(read(job / (engine + '.stdout'))) == published['raw_receipt_sha256'][engine + '.stdout'],
            'Local receipt SHA256 compared with immutable published result ' + RESULT_COMMIT))
    probe('local_result_matches_published', lambda: check(
        json.loads(read(job / 'result.json')) == published, 'Exact parsed local/published result comparison'))
    probe('task_intent_binding', lambda: check(
        json.loads(read(job / 'intent.json'))['task_sha256'] == digest(json.dumps(task, sort_keys=True).encode())
        and json.loads(read(job / 'intent.json'))['merge_commit'] == published['merge_commit'],
        'Intent binds task bytes and merge commit'))

    def claude_argv():
        args = json.loads(read(job / 'claude_process.json'))['argv']
        def value(flag):
            return args[args.index(flag) + 1]
        settings = json.loads(value('--settings'))
        expected = json.loads(blob(repo, published['merge_commit'], '.claude/settings.json'))
        expected_overlay = json.loads(json.dumps(expected))
        expected_overlay['hooks']['PreToolUse'].append({'matcher': '*', 'hooks': [{'type': 'command', 'command':
            '/usr/bin/python3 ' + shlex.quote(str(job / 'checkout/p0e4/task_runner/tool_gate.py')), 'timeout': 10}]})
        expected_overlay['autoMemoryEnabled'] = False
        expected_args = [str(home / '.local/bin/claude'), '-p', '--restricted', '--tools', '',
            '--disable-slash-commands', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--settings', value('--settings'), '--permission-mode', 'default', '--permission-prompts', 'none',
            '--max-turns', '8', '--output-format', 'json']
        ok = (args == expected_args and settings == expected_overlay and args[1:3] == ['-p', '--restricted'] and value('--tools') == ''
              and '--strict-mcp-config' in args and json.loads(value('--mcp-config')) == {'mcpServers': {}}
              and '--disable-slash-commands' in args and value('--permission-mode') == 'default'
              and value('--permission-prompts') == 'none' and value('--max-turns') == '8'
              and value('--output-format') == 'json' and settings['permissions'] == expected['permissions']
              and settings['hooks']['PreToolUse'][:-1] == expected['hooks']['PreToolUse']
              and settings['hooks']['PreToolUse'][-1]['matcher'] == '*'
              and '--dangerously-skip-permissions' not in args and '--allowedTools' not in args)
        observations['claude_requested_profile'] = {'restricted': '--restricted' in args,
            'built_in_tools': value('--tools'), 'mcp_servers': list(json.loads(value('--mcp-config'))['mcpServers']),
            'permission_mode': value('--permission-mode'), 'max_turns': value('--max-turns')}
        return check(ok, 'Recorded argv and permission overlay; not proof of all effective managed settings')
    probe('claude_recorded_argv', claude_argv)

    def codex_events():
        args = json.loads(read(job / 'codex_process.json'))['argv']
        events = [json.loads(x) for x in read(job / 'codex.stdout').decode().splitlines() if x.strip()]
        item_types = Counter(e.get('item', {}).get('type') for e in events if e.get('item'))
        observations['codex_event_types'] = dict(Counter(e.get('type', 'UNKNOWN') for e in events))
        observations['codex_item_types'] = dict(item_types)
        thread = [e.get('thread_id') for e in events if e.get('type') == 'thread.started']
        config = json.loads(read(service / 'config.json'))
        expected_args = [config['codex'], 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
            '--sandbox', 'read-only', '-c', 'approval_policy="never"', '--json',
            '--output-last-message', str(job / 'review.txt'), '-C', str(job / 'review_workspace'), '-']
        ok = (args == expected_args and thread == [published['codex_thread_id']] and any(e.get('type') == 'turn.completed' for e in events)
              and not any(e.get('type') in ('error', 'turn.failed') for e in events)
              and args[args.index('--sandbox') + 1] == 'read-only' and '--ignore-user-config' in args
              and 'approval_policy="never"' in args)
        results['codex_no_recorded_tool_items'] = check(
            bool(item_types) and set(item_types) <= {'agent_message', 'reasoning'},
            'Only agent_message/reasoning items permitted in this tool-free smoke audit')
        return check(ok, 'Recorded read-only argv, completed turn and published thread binding')
    probe('codex_execution_receipt', codex_events)

    def claude_transcript():
        session = published['claude_session_id']
        if not re.fullmatch(r'[0-9a-f-]{36}', session):
            raise ValueError('unexpected session id')
        matches = list((home / '.claude/projects').glob('*/' + session + '.jsonl'))
        if len(matches) != 1:
            return unknown('Expected exactly one persisted transcript for the published Claude session')
        raw = read(matches[0]); count, sessions, names = tools_in_transcript(raw)
        observations['claude_transcript'] = {'sha256': digest(raw), 'assistant_events': count,
                                              'tool_name_counts': names}
        return check(count > 0 and sessions == {session} and not names,
                     'Persisted transcript for published session has assistant events and no recorded tool calls; not OS-wide proof')
    probe('claude_no_recorded_tool_calls', claude_transcript)

    def state_binding():
        pointer = json.loads(blob(repo, published['merge_commit'], 'p0e4/MASTER_STATE_LATEST.json'))
        raw = blob(repo, published['merge_commit'], pointer['path'])
        state = json.loads(raw)
        observations['state_versions'] = {'pointer': pointer['master_state_version'],
                                         'internal': state.get('master_state_version'), 'state_version': state.get('state_version')}
        results['state_version_label_consistency'] = check(pointer['master_state_version'] == state.get('master_state_version'),
                                                          'Existing metadata discrepancy; no state files changed')
        return check(digest(raw) == pointer['sha256'], 'Independent SHA256 of committed Master State bytes')
    probe('state_sha256_binding', state_binding)

    def runtime_binding():
        config = json.loads(read(service / 'config.json'))
        checks = {}
        for name in ('runner.py', 'tool_gate.py'):
            path = 'p0e4/task_runner/' + name
            checks[name] = (digest(read(service / 'runtime' / name)) == config['pins'][path]
                            == digest(blob(repo, config['baseline'], path)))
        observations['runtime_hash_matches'] = checks
        return check(all(checks.values()), 'Installed runtime bytes match local pins and committed baseline')
    probe('installed_runtime_binding', runtime_binding)
    def delivery():
        value = json.loads(read(job / 'delivered.json'))
        return check(value.get('url') == 'https://github.com/' + REPO + '/pull/3',
                     'Local delivery receipt matches independently observed merged PR #3')
    probe('delivery_receipt', delivery)
    for name, explanation in {
        'os_wide_absence_of_side_effects': 'Application logs are not a complete operating-system audit.',
        'effective_managed_permissions': 'Recorded argv does not establish every managed/global runtime setting.',
        'resolve_mcp_acceptance': 'This task intentionally had zero MCP servers.',
        'gemini_task_receipt': 'No Gemini task, login or model was started by this audit.'}.items():
        results[name] = unknown(explanation)

    apps = []
    for base in applications or [Path('/Applications'), home / 'Applications', home / 'Applications/Chrome Apps.localized']:
        if not base.is_dir():
            continue
        for app in sorted(base.glob('*.app')):
            if 'gemini' not in app.name.lower():
                continue
            try:
                info = plistlib.loads(read(app / 'Contents/Info.plist'))
                # No login database, keychain, browser profile or chat history is read.
                apps.append({'app_name': app.name, 'bundle_id': info.get('CFBundleIdentifier'),
                             'version': info.get('CFBundleShortVersionString'),
                             'build': info.get('CFBundleVersion'),
                             'scripting_dictionaries': [p.name for p in (app / 'Contents/Resources').glob('*.sdef')],
                             'url_schemes': [s for entry in info.get('CFBundleURLTypes', []) for s in entry.get('CFBundleURLSchemes', [])]})
            except Exception:
                apps.append({'app_name': app.name, 'metadata_status': 'NIET BEWEZEN'})
    cli = shutil.which('gemini')
    if not cli:
        cli = next((str(p) for p in [home / '.local/bin/gemini', Path('/opt/homebrew/bin/gemini'), Path('/usr/local/bin/gemini')]
                    if p.is_file() and os.access(p, os.X_OK)), None)
    return {'schema': 'P0E4_LOCAL_RECEIPTS_GEMINI_AUDIT_V01', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status': 'PARTIAL_VERIFICATION', 'task_pr': 2, 'result_commit': RESULT_COMMIT,
            'audit_script_sha256': digest(Path(__file__).read_bytes()), 'checks': results, 'observations': observations,
            'gemini_inventory': {'apps': apps, 'cli_found': bool(cli), 'cli_executed': False,
                                 'chat_context_access': 'NIET BEWEZEN', 'identity_is_vendor_verified': False},
            'raw_transcripts_uploaded': False, 'credentials_read': False, 'models_started': False,
            'master_state_modified': False, 'runner_modified': False}


def publish(report, gh):
    """Exactly one derived JSON file; no raw logs or config content exported."""
    raw = json.dumps(report, indent=2, ensure_ascii=False).encode() + b'\n'
    if len(raw) > 100000 or re.search(rb'(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|sk-ant-|PRIVATE KEY|AIza[A-Za-z0-9_-]{25,})', raw):
        raise ValueError('Report blocked by size/secret check')
    def api(endpoint, method='GET', body=None):
        args = [gh, 'api', '--hostname', 'github.com', '--method', method, endpoint]
        if body is not None:
            args += ['--input', '-']
        p = subprocess.run(args, input=json.dumps(body).encode() if body is not None else None,
                           capture_output=True, timeout=60)
        if p.returncode:
            raise ValueError('GitHub request failed; no raw response exported')
        return json.loads(p.stdout)
    if api('user')['login'] != 'NitinBR1406':
        raise ValueError('Unexpected GitHub identity')
    prefix = 'repos/' + REPO + '/'
    base = api(prefix + 'git/ref/heads/' + BRANCH)['object']['sha']
    suffix = digest(raw)[:16]
    branch = 'audit/local-receipts-' + suffix
    api(prefix + 'git/refs', 'POST', {'ref': 'refs/heads/' + branch, 'sha': base})
    result = api(prefix + 'contents/p0e4/evidence/local_receipts_gemini_v01/LOCAL_' + suffix + '.json', 'PUT',
                 {'message': 'audit: local receipts and Gemini inventory [skip ci]', 'branch': branch,
                  'content': base64.b64encode(raw).decode()})
    commit = result['commit']['sha']
    pr = api(prefix + 'pulls', 'POST', {'title': 'Local receipt audit and Gemini identity', 'head': branch, 'base': BRANCH,
        'body': 'Derived local read-only audit. No raw chats, credentials, model launches, runner changes or Master State edits. Partial findings remain explicit; not an unconditional safety acceptance.'})
    merged = api(prefix + 'pulls/' + str(pr['number']) + '/merge', 'PUT', {'sha': commit, 'merge_method': 'merge'})
    if not merged.get('merged'):
        raise ValueError('Report PR created; merge not confirmed')
    return pr['html_url']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    a = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('Mac required; no audit or publication performed')
    report = audit(Path.home())
    if a.publish:
        gh = str(Path.home() / '.local/bin/gh')
        print(json.dumps({'status': 'REPORT_PUBLISHED', 'url': publish(report, gh)}))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
