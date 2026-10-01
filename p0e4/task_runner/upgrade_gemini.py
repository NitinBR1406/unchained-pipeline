"""Controlled opt-in upgrade of the existing launchd worker; never a second agent."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

import runner as r
import runner_gemini as v2
import gemini_qc as qc

LABEL = 'com.unchained.claude-task-inbox'
RUNTIME_PATHS = list(dict.fromkeys(r.PINNED + v2.EXTRA_PINS))


def pending_tasks(gh, root, config, head):
    pending = []
    for pr in gh.pages('pulls?state=closed&base=' + r.BRANCH + '&per_page=100'):
        commit = pr.get('merge_commit_sha')
        if not pr.get('merged_at') or not commit:
            continue
        old = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, config['baseline']], cwd=root,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        if old == 0:
            continue
        r.git(root, 'merge-base', '--is-ancestor', commit, head)
        files = gh.pages('pulls/' + str(pr['number']) + '/files?per_page=100')
        if any(f['filename'].startswith(r.INBOX) for f in files):
            marker = Path(config['state']) / ('pr_' + str(pr['number'])) / 'delivered.json'
            if not marker.is_file():
                pending.append(pr['number'])
    return pending


def replace_bytes(path, raw):
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def activate(config_path, plist_path, config, plist, uid):
    """Restore exact old config/plist on failure; never remove state or runtime."""
    old_config = config_path.read_bytes(); old_plist = plist_path.read_bytes()
    domain = 'gui/' + str(uid)
    r.run(['/bin/launchctl', 'bootout', domain + '/' + LABEL])
    try:
        replace_bytes(config_path, (json.dumps(config, indent=2) + '\n').encode())
        replace_bytes(plist_path, plistlib.dumps(plist))
        r.run(['/bin/launchctl', 'bootstrap', domain, str(plist_path)])
        r.run(['/bin/launchctl', 'print', domain + '/' + LABEL])
    except Exception:
        # The new service may have bootstrapped before its health read failed.
        subprocess.run(['/bin/launchctl', 'bootout', domain + '/' + LABEL], capture_output=True)
        replace_bytes(config_path, old_config); replace_bytes(plist_path, old_plist)
        r.run(['/bin/launchctl', 'bootstrap', domain, str(plist_path)])
        raise ValueError('UPGRADE_FAILED_OLD_CONFIG_RESTORED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--activate-gemini-text-qc', action='store_true', required=True)
    args = parser.parse_args()
    r.require(sys.platform == 'darwin', 'MAC_REQUIRED')
    os.umask(0o077)
    home = Path.home(); source = Path(args.repo).resolve()
    target = home / 'Library/Application Support/UnchainedTaskRunner'
    config_path = target / 'config.json'
    plist_path = home / 'Library/LaunchAgents' / (LABEL + '.plist')
    r.require(config_path.is_file() and not config_path.is_symlink()
              and plist_path.is_file() and not plist_path.is_symlink(), 'EXISTING_INSTALL_REQUIRED')
    config = json.loads(config_path.read_text()); plist = plistlib.loads(plist_path.read_bytes())
    r.require(not config.get('gemini_text_qc_enabled'), 'ALREADY_UPGRADED_NO_SECOND_INSTALL')
    r.require(config['state'] == str(target / 'state') and config['repo'] == str(target / 'repo'), 'INSTALL_PATH_DRIFT')
    r.require(plist['Label'] == LABEL and plist['ProgramArguments'][1:] ==
              [str(target/'runtime/runner.py'), '--config', str(config_path)], 'LAUNCHD_CONFIG_DRIFT')
    gh = r.GitHub(config['gh'])
    owner = json.loads(r.run([config['gh'], 'api', '--hostname', 'github.com', 'user']))['login']
    r.require(owner == 'NitinBR1406', 'GITHUB_OWNER')
    origin = r.git(source, 'remote', 'get-url', 'origin').decode().strip()
    r.require(origin in ('https://github.com/'+r.REPO+'.git','https://github.com/'+r.REPO,
                         'git@github.com:'+r.REPO+'.git'), 'SOURCE_ORIGIN')
    r.require(not r.git(source, 'status', '--porcelain').strip(), 'SOURCE_DIRTY')
    head = r.git(source, 'rev-parse', 'HEAD').decode().strip()
    remote = gh.api('git/ref/heads/' + r.BRANCH)['object']['sha']
    r.require(head == remote, 'SOURCE_NOT_CURRENT_MERGED_HEAD')
    for path, digest in config['pins'].items():
        r.require(r.sha(r.regular_blob(source, head, path)) == digest, 'OLD_PIN_DRIFT:' + path)
    for name in ('runner.py', 'tool_gate.py'):
        r.require(r.sha((target/'runtime'/name).read_bytes()) == config['pins']['p0e4/task_runner/'+name], 'INSTALLED_RUNTIME_DRIFT')
    r.require(not qc.adapter_config_conflicts(home, home/'Unchained-Gemini-QC'), 'GEMINI_CONFIG_HOLD')
    r.require(qc.sha((home/'.local/bin/agy').read_bytes()) == qc.BINARY_SHA, 'GEMINI_BINARY_DRIFT')
    proof = json.loads(r.regular_blob(source, head, 'p0e4/evidence/gemini_text_qc_v01/LOCAL_0c98c5b60693c538.json'))
    r.require(proof['request_sha256'] == qc.sha(qc.encoded(qc.synthetic_request()))
              and {c['id']:c['verdict'] for c in proof['checks']} == {'C1':'CONTRADICTED','C2':'NOT_PROVEN'}, 'LIVE_ADAPTER_PROOF')
    # Same lock as the existing worker: never stop an active model task.
    with (Path(config['state'])/'runner.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('RUNNER_BUSY_NOT_CHANGED')
        r.require(not pending_tasks(gh, source, config, head), 'PENDING_TASKS_DRAIN_FIRST_NOT_CHANGED')
        r.require(gh.api('git/ref/heads/' + r.BRANCH)['object']['sha'] == head, 'REMOTE_MOVED_NOT_CHANGED')
        r.run(['/bin/launchctl', 'print', 'gui/'+str(os.getuid())+'/'+LABEL])
        snapshot = target / ('runtime-gemini-' + head[:12])
        r.require(not snapshot.exists(), 'UPGRADE_SNAPSHOT_EXISTS_INSPECT_NO_OVERWRITE')
        snapshot.mkdir()
        for path in RUNTIME_PATHS:
            output = snapshot/path; output.parent.mkdir(parents=True, exist_ok=True)
            raw = r.regular_blob(source, head, path); output.write_bytes(raw)
            r.require(r.sha(output.read_bytes()) == r.sha(raw), 'RUNTIME_COPY_MISMATCH')
        backup = snapshot/'rollback'; backup.mkdir()
        shutil.copyfile(config_path, backup/'config.json'); shutil.copyfile(plist_path, backup/'runner.plist')
        new_config = dict(config, baseline=head, gemini_text_qc_enabled=True,
                          prior_baseline=config['baseline'], gemini_runtime=str(snapshot))
        new_config['pins'] = dict(config['pins'])
        new_config['pins'].update({p:r.sha(r.regular_blob(source,head,p)) for p in v2.EXTRA_PINS})
        new_plist = dict(plist)
        new_plist['ProgramArguments'] = [sys.executable, str(snapshot/'p0e4/task_runner/runner_gemini.py'),
                                        '--config', str(config_path)]
        activate(config_path, plist_path, new_config, new_plist, os.getuid())
        r.atomic(snapshot/'INSTALL_RECEIPT.json', {'status':'INSTALLED_INTEGRATED_ROUTE_UNPROVEN',
                  'source_sha':head,'existing_state_preserved':True,'old_runtime_preserved':True,
                  'label':LABEL,'governance':r.GATES})
    print(json.dumps({'status':'INSTALLED_INTEGRATED_ROUTE_UNPROVEN', 'source_sha':head,
                      'next':'One explicit GEMINI_TEXT_QC task roundtrip; no second installation.'}))


if __name__ == '__main__': main()
