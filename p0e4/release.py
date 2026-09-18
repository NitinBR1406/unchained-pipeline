"""Typed production handoff preparation; immutable outputs, no production transports.

The existing P0-E3 loop schedules these executor activities. A candidate package is
not a publish approval, nor proof that existing creative approvals cover new bytes.
"""
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

import handoff as h

DRIVE = '0AG0CqqUZ6YuXUk9PVA'
MASTER_ID = '1ifHVAW1E0NjhN-eguBWUMNRekoemweAn'
TASKS = ('AKI_ASSET_INVENTORY', 'AKI_PACKAGE_DRAFT', 'AKI_READINESS', 'INDEPENDENT_GOVERNANCE_AUDIT')


@dataclass(frozen=True)
class VerifiedAsset:
    file_id: str
    sha256: str
    size_bytes: int
    name: str
    duration: float

    @classmethod
    def read(cls, row):
        if (row.get('drive_id') != DRIVE or row.get('technical_decode_pass') is not True
                or row.get('bytes_unchanged') is not True or row.get('full_av_decode_exit_code') != 0
                or type(row.get('size_bytes')) is not int or row['size_bytes'] <= 0
                or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                or not row.get('file_id') or row.get('probe', {}).get('duration', 0) <= 0):
            raise ValueError('unverified asset evidence')
        return cls(row['file_id'], row['sha256'], row['size_bytes'], row['name'], row['probe']['duration'])


def build(media, root=h.ROOT):
    intake = h.inspect(root)
    rows = media['assets']
    assets = [VerifiedAsset.read(r) for r in rows]
    if len({a.file_id for a in assets}) != len(assets):
        raise ValueError('duplicate asset identity')
    master = next((a for a in assets if a.file_id == MASTER_ID), None)
    if master is None:
        raise ValueError('expected Drive master missing')
    campaign = json.loads((root/'campaigns/aakhri-ishq/campaign.json').read_text())
    if master.name != campaign['production_master_name']:
        raise ValueError('master identity mismatch')
    # Only metadata drafts: no cuts/re-render/re-approval of locked source media.
    variants = {
        'youtube_hero': ('Aakhri Ishq — UNCHAINED NITIN | Cover Performance',
                        'Aakhri Ishq, in mijn stem. Een coverperformance van UNCHAINED NITIN.'),
        'youtube_shorts': ('Aakhri Ishq | UNCHAINED NITIN', 'Even alles stil. Alleen Aakhri Ishq.'),
        'instagram_reels': ('Aakhri Ishq', 'Sommige gevoelens blijven in een lied. Aakhri Ishq — UNCHAINED NITIN.'),
        'instagram_feed': ('Aakhri Ishq — coverperformance', 'Mijn uitvoering van Aakhri Ishq. UNCHAINED NITIN.'),
        'instagram_stories': ('Aakhri Ishq', 'Aakhri Ishq — een moment om te luisteren.'),
        'tiktok': ('Aakhri Ishq | Cover', 'Aakhri Ishq, in mijn stem. Welk moment raakt jou?'),
        'facebook_reels': ('Aakhri Ishq — UNCHAINED NITIN', 'Een coverperformance van Aakhri Ishq. Dank je wel voor het luisteren.'),
    }
    packages = []
    for platform in campaign['platform_targets']:
        title, caption = variants[platform]
        packages.append({'platform': platform, 'title': title, 'caption': caption,
            'description': caption + ' Coverperformance; rechtencontrole nog niet afgerond.',
            'hashtags': ['AakhriIshq', 'UnchainedNitin', 'CoverPerformance'],
            'cta': 'Welk moment raakt jou?', 'rights_status': campaign['rights']['status'],
            'asset_candidates': [a.__dict__ for a in assets if platform != 'youtube_hero' or a.file_id == MASTER_ID],
            'selected_asset': None, 'publish_datetime': None,
            'status': 'DRAFT_REQUIRES_ASSET_AND_RELEASE_DECISION'})
    return {'schema_version': 1, 'workload_type': 'production_release_handoff',
        'campaign_id': 'aakhri-ishq', 'baseline': intake,
        'media_evidence_sha256': h.digest(h.canonical(media)),
        'verified_assets': [a.__dict__ for a in assets], 'packages': packages,
        'approval_binding_request': {'gate': 'NITIN_FINAL_VIDEO_APPROVAL',
            'existing_decision': intake['approvals_observed']['NITIN_FINAL_VIDEO_APPROVAL'],
            'candidate_asset': master.__dict__, 'status': 'NEEDS_AUTHORITATIVE_BINDING',
            'approval_created': False},
        'rights_request': campaign['rights'],
        'status': 'BLOCKED', 'publish_ready': False,
        'blockers': ['FINAL_VIDEO_APPROVAL_BINDING_REQUIRED', 'RIGHTS_HOLD',
                     'PLATFORM_ASSET_SELECTION_AND_FINAL_PACKAGE_REQUIRED'],
        'next_gate_after_resolution': 'NITIN_PUBLISH_APPROVAL',
        'publication_side_effect_count': 0}


class ReleaseExecutor:
    """Content-addressed immutable evidence; retry including crash-before-receipt is safe."""
    def __init__(self, directory, package):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.package = package

    def __call__(self, task, job_id, now):
        tid = task['task_id']
        if tid not in TASKS:
            raise PermissionError('no publication, production render, or unknown task permitted')
        if task.get('input_hash') != h.digest(h.canonical(self.package)):
            raise ValueError('task input is not bound to this release package')
        payload = {'task_id': tid, 'job_id': job_id, 'package_sha256': task['input_hash'],
                   'package': self.package}
        content = h.canonical(payload)
        target = self.directory/(tid+'.json')
        with (self.directory/'.evidence.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if target.exists():
                if target.read_bytes() != content:
                    raise ValueError('immutable evidence conflict')
            else:
                fd, tmp = tempfile.mkstemp(dir=self.directory)
                try:
                    with os.fdopen(fd,'wb') as f:
                        f.write(content); f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, target)
                finally:
                    if os.path.exists(tmp): os.unlink(tmp)
        return {'status': 'OK', 'evidence': [target.name+'#sha256='+h.digest(content)]}


def seed(loop, package):
    ih = h.digest(h.canonical(package))
    if loop.backlog.tasks:
        if any(t['input_hash'] != ih for t in loop.backlog.tasks):
            raise ValueError('cannot reuse run with changed inputs')
        return
    loop.ledger.append(h.make_event('p0e4-production-intake', 'TASK_REQUEST', '1000', 'codex',
        task_id='AKI_ASSET_INVENTORY', inputs={'package_sha256': ih, 'workload': package}))
    loop.backlog.tasks = [h.task(tid, (i+1)*10, ih,
        deps=() if i == 0 or tid == 'INDEPENDENT_GOVERNANCE_AUDIT' else (TASKS[i-1],))
        for i,tid in enumerate(TASKS)]
    release = h.task('AKI_RELEASE', 35, ih, 'NITIN_PUBLISH_APPROVAL',
                     deps=('AKI_READINESS',), status='BLOCKED')
    release['blocked_reason'] = ','.join(package['blockers'])
    loop.backlog.tasks.append(release)
    loop.backlog.save()
