"""Poster Publish Approval Provisioner.

Creates and revokes publish GRANTS only. It NEVER writes human approval records and CANNOT infer a
Publish Approval from workflow state or from a Final Asset Approval. A grant is created ONLY when all
three human gates (creative + final-asset + publish) already exist for the platform-scoped campaign
(content_id::platform), each APPROVE and bound to the exact material fingerprint. Any material change
(asset / packaging / platform / schedule_version) produces a different fingerprint, so a stale grant
cannot authorize changed content. Nitin remains sole Publish Authority; this is mechanical assembly.

Grants are stored under a platform-scoped key `content_id::platform`, so a poster's Instagram and
Facebook grants are fully independent. The logical content_id is unchanged (storage detail only).
"""
import time

from .approvals import GATE_CREATIVE, GATE_FINAL_ASSET, GATE_PUBLISH
from .canonical import (compute_fingerprint, packaging_sha256, scheduled_at_to_epoch,
                        schedule_window, MEDIUM_POSTER)
from .util import read_json, write_json, sha256_bytes


class ProvisionError(Exception):
    pass


class PosterProvisioner:
    def __init__(self, approvals, grants_path, now=None):
        self.approvals = approvals
        self.grants_path = grants_path
        self._now = now or (lambda: int(time.time()))

    @staticmethod
    def grant_key(content_id, platform):
        """Platform-scoped storage key. Logical content_id is unchanged; this is storage only."""
        return "{}::{}".format(content_id, platform)

    def _load(self):
        data = read_json(self.grants_path, default={"grants": {}}) or {"grants": {}}
        if not isinstance(data, dict) or "grants" not in data or not isinstance(data["grants"], dict):
            data = {"grants": {}}
        return data

    def _all_gates_bound(self, campaign, fp):
        return (self.approvals.is_approved(campaign, GATE_CREATIVE, fp)
                and self.approvals.is_approved(campaign, GATE_FINAL_ASSET, fp)
                and self.approvals.is_approved(campaign, GATE_PUBLISH, fp))

    def compute_poster_fingerprint(self, content_id, image_bytes, caption, platform, schedule_version):
        asset_sha = sha256_bytes(image_bytes)
        pkg_sha = packaging_sha256(content_id, caption)
        # fp uses the LOGICAL content_id (matches the verifier, which computes fp from the request).
        fp = compute_fingerprint(content_id, asset_sha, platform, pkg_sha, schedule_version)
        return fp, asset_sha, pkg_sha

    def create_grant(self, content_id, image_bytes, caption, platform, scheduled_at,
                     schedule_version, exp, approval_id=None):
        """Create (or idempotently re-create identical) a poster grant for ONE platform.

        Grant is stored under content_id::platform. Refuses unless creative + final-asset + publish
        approvals exist under the SAME platform-scoped campaign, bound to the computed fingerprint.
        Independent per platform; non-destructive to other keys. Raises ProvisionError if not bound.
        """
        key = self.grant_key(content_id, platform)
        fp, asset_sha, pkg_sha = self.compute_poster_fingerprint(
            content_id, image_bytes, caption, platform, schedule_version)

        if not self._all_gates_bound(key, fp):
            raise ProvisionError(
                "REFUSED: creative + final-asset + publish approvals must all exist (campaign "
                "'{}') bound to the current fingerprint before a grant can be created".format(key))

        epoch = scheduled_at_to_epoch(scheduled_at)
        window = schedule_window(epoch)
        grant = {
            "approval_id": approval_id or "PA-{}-{}".format(content_id, platform),
            "content_id": content_id,
            "fingerprint": fp,
            "platforms": [platform],
            "schedule_window": window,
            "schedule_version": schedule_version,
            "exp": int(exp),
            "revoked": False,
            "medium": MEDIUM_POSTER,
        }
        data = self._load()
        data["grants"][key] = grant  # non-destructive to other platform keys / content_ids
        write_json(self.grants_path, data)
        return grant

    def revoke_grant(self, content_id, platform):
        """Revoke ONE platform's grant (content_id::platform). Never affects the other platform."""
        key = self.grant_key(content_id, platform)
        data = self._load()
        g = data["grants"].get(key)
        if not g:
            return False
        g["revoked"] = True
        data["grants"][key] = g
        write_json(self.grants_path, data)
        return True
