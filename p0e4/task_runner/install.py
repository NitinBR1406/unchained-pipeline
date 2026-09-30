"""One-time Mac installation. No tokens, shell profiles or existing agents changed."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys

from runner import PINNED, REPO, BRANCH, GitHub, atomic, git, regular_blob, require, run, sha

LABEL = 'com.unchained.claude-task-inbox'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--activate', action='store_true')
    p.add_argument('--codex', default='/Applications/ChatGPT.app/Contents/Resources/codex')
    a = p.parse_args()
    require(sys.platform == 'darwin', 'Mac required; nothing installed')
    os.umask(0o077)
    source = Path(a.repo).resolve()
    home = Path.home()
    target = home / 'Library/Application Support/UnchainedTaskRunner'
    require(not target.exists(), 'Existing installation: inspect it; no overwrite or second runner')
    gh_path = shutil.which('gh')
    claude = home / '.local/bin/claude'
    require(gh_path and claude.is_file() and Path(a.codex).is_file(), 'gh/Claude/Codex missing')
    require(not git(source, 'status', '--porcelain').strip(), 'source checkout must be clean')
    origin = git(source, 'remote', 'get-url', 'origin').decode().strip()
    require(origin in ('https://github.com/' + REPO + '.git', 'https://github.com/' + REPO,
                       'git@github.com:' + REPO + '.git'), 'unexpected repository')
    services = run(['/bin/launchctl', 'list']).decode()
    conflicts = [x for x in services.splitlines() if any(s in x.lower() for s in ('unchained', 'p0e4'))]
    require(not conflicts, 'Existing UNCHAINED/P0E4 LaunchAgent: reconcile before installing; none stopped automatically')
    gh = GitHub(gh_path)
    owner = json.loads(run([gh_path, 'api', '--hostname', 'github.com', 'user']))['login']
    require(owner == 'NitinBR1406', 'Expected owner GitHub identity')
    require(json.loads(run([gh_path, 'api', 'repos/' + REPO]))['permissions']['push'], 'GitHub write access missing')
    run([str(claude), 'auth', 'status'])
    run([a.codex, '--version'])
    # Verify source is the actual merged target; never install a PR head or stale checkout.
    remote = gh.api('git/ref/heads/' + BRANCH)['object']['sha']
    baseline = git(source, 'rev-parse', 'HEAD').decode().strip()
    require(baseline == remote, 'Checkout must match current merged target HEAD')
    pins = {path: sha(regular_blob(source, baseline, path)) for path in PINNED}
    pointer = json.loads(regular_blob(source, baseline, 'p0e4/MASTER_STATE_LATEST.json'))
    pins[pointer['path']] = sha(regular_blob(source, baseline, pointer['path']))
    require(pins[pointer['path']] == pointer['sha256'], 'Master State binding mismatch')
    target.mkdir(parents=True)
    root = target / 'repo'
    git(source, 'clone', '--quiet', '--no-hardlinks', str(source), str(root))
    git(root, 'remote', 'set-url', 'origin', 'https://github.com/' + REPO + '.git')
    runtime = target / 'runtime'; runtime.mkdir()
    for name in ('runner.py', 'tool_gate.py'):
        shutil.copyfile(source / 'p0e4/task_runner' / name, runtime / name)
    state = target / 'state'; state.mkdir()
    config = target / 'config.json'
    atomic(config, {'repo': str(root), 'state': str(state), 'pins': pins, 'baseline': baseline,
                    'merge_actors': ['NitinBR1406'], 'gh': gh_path, 'claude': str(claude), 'codex': a.codex})
    plist = home / 'Library/LaunchAgents' / (LABEL + '.plist')
    require(not plist.exists(), 'LaunchAgent already exists')
    plist.parent.mkdir(exist_ok=True)
    contents = {'Label': LABEL, 'ProgramArguments': [sys.executable, str(runtime / 'runner.py'), '--config', str(config)],
                'StartInterval': 180, 'RunAtLoad': True, 'ProcessType': 'Background',
                'WorkingDirectory': str(root), 'StandardOutPath': str(state / 'launchd.out'),
                'StandardErrorPath': str(state / 'launchd.err'),
                'EnvironmentVariables': {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin',
                                         'HOME': str(home)}}
    with plist.open('xb') as f:
        plistlib.dump(contents, f)
    if a.activate:
        run(['/bin/launchctl', 'bootstrap', 'gui/' + str(os.getuid()), str(plist)])
    print(json.dumps({'status': 'INSTALLED_ACTIVATED_UNPROVEN' if a.activate else 'INSTALLED_INACTIVE',
                      'health': str(state / 'health.json'), 'label': LABEL,
                      'live_task_acceptance': 'NIET BEWEZEN'}))


if __name__ == '__main__':
    main()
