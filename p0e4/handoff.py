"""Read-only production intake on the frozen P0-E3 loop. No production transport."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / '07_Reports/AI_Governance/Architecture'
for directory in ('P0E1_CONTROL_PLANE', 'P0E3_CONTROL_LOOP'):
    sys.path.insert(0, str(ARCH / directory))
from control_loop.control_loop import DurableControlLoop, Clock
from control_loop.durable_stores import TASK_FIELDS, _atomic_write_json
from control_loop.state_model import verify_replay
from control_plane.events import make_event

FREEZE = '263a36980fc2e2aa3138609f5406555ead9ef8d7'
STATE = '07_Reports/AI_Governance/Architecture/P0E3_CONTROL_LOOP/evidence/freeze/UNCHAINED_MASTER_PROJECT_STATE_V05.json'
INPUTS = (STATE, 'campaigns/aakhri-ishq/campaign.json',
          'campaigns/aakhri-ishq/state/approvals.json',
          'campaigns/aakhri-ishq/state/registry.json',
          'campaigns/aakhri-ishq/state/PACKAGING.json',
          'campaigns/aakhri-ishq/state/DERIVATIVE_PLAN.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def inspect(root=ROOT):
    """Return factual gaps; an old APPROVED boolean is never an asset binding."""
    raw = {p: (root / p).read_bytes() for p in INPUTS}
    state, campaign, approvals, registry, packages, derivatives = (
        json.loads(raw[p]) for p in INPUTS)
    if (state['state_version'] != 10 or
        state['authorizations']['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is not False or
        state['authorizations']['PUBLICATION_AUTHORIZED'] is not False or
        state['production_state']['first_real_poster'] != 'PAUSED_BY_NITIN'):
        raise ValueError('governance differs from authorized Slice 1 contract')
    if campaign['campaign_id'] != 'aakhri-ishq':
        raise ValueError('wrong campaign')
    latest = {}
    for a in approvals['approvals']:
        if a.get('campaign_id') != campaign['campaign_id']:
            raise ValueError('cross-campaign approval')
        latest[a['gate']] = a
    video = latest.get('NITIN_FINAL_VIDEO_APPROVAL', {})
    publish = latest.get('NITIN_PUBLISH_APPROVAL', {})
    blockers = []
    if video.get('decision') != 'APPROVE':
        blockers.append('FINAL_VIDEO_APPROVAL_NOT_RECORDED')
    video_sha = video.get('artifact_sha256', '')
    if not re.fullmatch('[0-9a-f]{64}', video_sha):
        blockers.append('FINAL_VIDEO_SHA_UNBOUND')
    if not any(x.get('sha256') == video_sha and x.get('kind') == 'production_master'
               for x in registry.values()):
        blockers.append('PRODUCTION_MASTER_NOT_REGISTERED')
    if campaign.get('rights', {}).get('status') != 'RIGHTS_PASS':
        blockers.append('RIGHTS_NOT_PASS')
    if packages.get('status') != 'READY' or any(
        not p.get('caption') or not p.get('asset') for p in packages.get('packages', [])):
        blockers.append('PACKAGING_INCOMPLETE')
    if derivatives.get('status') != 'READY':
        blockers.append('DERIVATIVES_NOT_VERIFIED')
    # These are required integrations, never inferred from old live P0-E3 evidence.
    blockers.extend(['SHARED_DRIVE_ASSET_READBACK_REQUIRED',
                     'DURABLE_LIVE_EXECUTOR_NOT_PROVISIONED',
                     'SHARED_DRIVE_STATE_PERSISTENCE_NOT_PROVISIONED'])
    if publish.get('decision') == 'APPROVE':
        raise ValueError('unexpected publish approval; scope must be reviewed')
    return {
        'schema_version': 1, 'workload_type': 'production_release_handoff',
        'campaign_id': campaign['campaign_id'], 'source_freeze_sha': FREEZE,
        'source_master_state_version': state['state_version'],
        'source_sha256': {p: digest(b) for p, b in raw.items()},
        'authorizations': {k: state['authorizations'][k] for k in
                           ('PRODUCTION_DEPLOYMENT_AUTHORIZED', 'PUBLICATION_AUTHORIZED')},
        'first_real_poster': state['production_state']['first_real_poster'],
        'approvals_observed': latest,
        'publish_approval_created': False,
        'publish_ready': False, 'status': 'BLOCKED_INTEGRATION',
        'blockers': blockers,
        'next_human_gate': 'NITIN_PUBLISH_APPROVAL',
        'publication_side_effect_count': 0,
        'evidence_scope': 'repository_intake_and_local_control_loop_only',
    }


def task(tid, priority, ih, gate=None, deps=(), status='READY'):
    t = {k: None for k in TASK_FIELDS}
    t.update(task_id=tid, title=tid, priority=priority, dependencies=list(deps),
             status=status, autonomy_level='HUMAN_GATED' if gate else 'AUTONOMOUS_SAFE',
             allowed_scope=['p0e4_readonly_intake'], definition_of_done='hash-bound intake evidence',
             tests_required=['offline'], evidence_required=['intake.json'],
             rollback='discard isolated staging only', human_gate_required=gate,
             next_action='inspect', input_hash=ih)
    return t


class ReadOnlyAdapter:
    """Only writes immutable staging evidence. No Make/Render/publisher callable exists."""
    def __init__(self, workdir, intake):
        self.workdir = Path(workdir)
        self.intake = intake

    def __call__(self, t, job_id, now):
        if t['task_id'] not in ('AKI_INTAKE', 'INDEPENDENT_GOVERNANCE_AUDIT'):
            raise PermissionError('production adapter is closed')
        content = {'job_id': job_id, 'task_id': t['task_id'], 'intake': self.intake}
        target = self.workdir / (t['task_id'] + '.json')
        encoded = canonical(content)
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError('immutable evidence conflict')
        if not target.exists():
            # Atomic create of complete bytes. Re-entry after executor/store crash is a no-op.
            import os, tempfile
            fd, tmp = tempfile.mkstemp(dir=self.workdir)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(encoded); f.flush(); os.fsync(f.fileno())
                try:
                    os.link(tmp, target)
                except FileExistsError:
                    if target.read_bytes() != encoded:
                        raise ValueError('concurrent evidence conflict')
            finally:
                os.unlink(tmp)
        return {'status': 'OK', 'evidence': [target.name + '#sha256=' + digest(encoded)]}


def run(workdir, root=ROOT):
    """Resumable local engineering run; cannot represent live production acceptance."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    intake = inspect(root)
    ih = digest(canonical(intake))
    binding = workdir / 'INPUT_BINDING.json'
    if binding.exists() and json.loads(binding.read_text()) != {'sha256': ih}:
        raise ValueError('inputs changed: create a new isolated run')
    _atomic_write_json(str(binding), {'sha256': ih})
    loop = DurableControlLoop(str(workdir), keyring={}, clock=Clock(1000),
                              executor=ReadOnlyAdapter(workdir, intake))
    if not loop.backlog.tasks:
        loop.backlog.tasks = [task('AKI_INTAKE', 10, ih),
            task('AKI_RELEASE', 20, ih, gate='NITIN_PUBLISH_APPROVAL',
                 deps=('AKI_INTAKE',), status='BLOCKED'),
            task('INDEPENDENT_GOVERNANCE_AUDIT', 30, ih)]
        loop.backlog.by_id('AKI_RELEASE')['blocked_reason'] = ','.join(intake['blockers'])
        loop.backlog.save()
        loop.ledger.append(make_event('p0e4-intake-request', 'TASK_REQUEST', '1000', 'codex',
                           task_id='AKI_INTAKE', inputs={'workload': intake}))
    result = loop.run()
    replay, detail = verify_replay(loop.ledger, loop.persisted_state(), keyring={})
    if not replay:
        raise ValueError(detail)
    report = {'acceptance': 'BLOCKED_NOT_GREEN', 'intake': intake,
              'backlog_summary': loop.backlog.summary(), 'replay_verified': replay,
              'control_loop_state_version': loop.master_state()['state_version'],
              'ledger_head_hash': loop.master_state()['ledger_head_hash'],
              'authoritative_master_state_version': 10,
              'authoritative_master_state_updated': False,
              'live_temporal_observed': False, 'shared_drive_persisted': False}
    _atomic_write_json(str(workdir / 'HANDOFF_ASSESSMENT.json'), report)
    return report


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--workdir', required=True, help='isolated local staging directory')
    args = p.parse_args()
    print(json.dumps(run(args.workdir), indent=2))
