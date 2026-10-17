"""Placement Publish Grant Provisioner (video + still channel placements).

Same contract as unpipe.provisioner.PosterProvisioner, extended to one CHANNEL PLACEMENT:
creates/revokes publish GRANTS only, never writes human approval records, and refuses unless the
three human gates (creative + final video/asset + publish) already exist APPROVE for the
platform-scoped campaign key `content_id::platform`, each bound to the exact material fingerprint.

Additionally binds the target account: the verifier rejects a request for any other account
(TARGET_ACCOUNT_MISMATCH). The fingerprint basis itself is unchanged (unpipe.canonical).

Synthetic test grants: `test_only=True` is allowed ONLY for content ids in the reserved "test:"
namespace, and a non-test grant can never be created for that namespace. A real AKI placement id
("aki:post:...") can therefore never be released by test data.
"""
import time

from .approvals import GATE_CREATIVE, GATE_PUBLISH
from .canonical import (compute_fingerprint, packaging_sha256, scheduled_at_to_epoch,
                        schedule_window, final_gate_for_medium, MEDIUM_VIDEO, MEDIUM_POSTER)
from .publish_approval import TEST_PREFIX
from .util import read_json, write_json, locked


class ProvisionError(Exception):
    pass


def posted_text(title, caption):
    """Exact text the gate binds: title + blank line + caption (YouTube), else caption only."""
    return "{}\n\n{}".format(title, caption) if title else caption


class PlacementProvisioner:
    def __init__(self, approvals, grants_path, now=None):
        self.approvals = approvals
        self.grants_path = grants_path
        self._now = now or (lambda: int(time.time()))

    @staticmethod
    def grant_key(content_id, platform):
        return "{}::{}".format(content_id, platform)

    def _load(self):
        data = read_json(self.grants_path, default={"grants": {}}) or {"grants": {}}
        if not isinstance(data, dict) or not isinstance(data.get("grants"), dict):
            data = {"grants": {}}
        return data

    @staticmethod
    def fingerprint(content_id, asset_sha256, platform, title, caption, schedule_version):
        pkg = packaging_sha256(content_id, posted_text(title, caption))
        return compute_fingerprint(content_id, asset_sha256, platform, pkg, schedule_version), pkg

    def create_grant(self, content_id, asset_sha256, platform, target_account, title, caption,
                     scheduled_at, schedule_version, exp, medium=MEDIUM_VIDEO, test_only=False,
                     approval_id=None):
        _, pkg = self.fingerprint(content_id, asset_sha256, platform, title, caption, schedule_version)
        return self.create_grant_from_hashes(content_id, asset_sha256, platform, target_account, pkg, scheduled_at,
                                             schedule_version, exp, medium=medium, test_only=test_only, approval_id=approval_id)

    def create_grant_from_hashes(self, content_id, asset_sha256, platform, target_account, packaging_sha,
                                 scheduled_at, schedule_version, exp, medium=MEDIUM_VIDEO, test_only=False,
                                 approval_id=None):
        """Same as create_grant, for a host that only holds the exact hashes (bytes sha256 + packaging sha256 of the
        exact title/caption). The fingerprint and all refusals are identical."""
        if medium not in (MEDIUM_VIDEO, MEDIUM_POSTER):
            raise ProvisionError("REFUSED: unknown medium {!r}".format(medium))
        if not target_account:
            raise ProvisionError("REFUSED: target_account is required for a placement grant")
        if bool(test_only) != str(content_id).startswith(TEST_PREFIX):
            raise ProvisionError("REFUSED: test grants only in the '{}' namespace, and never a real "
                                 "grant there".format(TEST_PREFIX))
        key = self.grant_key(content_id, platform)
        fp = compute_fingerprint(content_id, asset_sha256, platform, packaging_sha, schedule_version)
        gates = (GATE_CREATIVE, final_gate_for_medium(medium), GATE_PUBLISH)
        if not all(self.approvals.is_approved(key, g, fp) for g in gates):
            raise ProvisionError("REFUSED: creative + final + publish approvals must all exist (campaign "
                                 "'{}') bound to the current fingerprint".format(key))
        grant = {
            "approval_id": approval_id or "PA-{}-{}".format(content_id, platform),
            "content_id": content_id,
            "fingerprint": fp,
            "platforms": [platform],
            "target_account": target_account,
            "schedule_window": schedule_window(scheduled_at_to_epoch(scheduled_at)),
            "schedule_version": schedule_version,
            "exp": int(exp),
            "revoked": False,
            "medium": medium,
            "test_only": bool(test_only),
        }
        with locked(self.grants_path):   # serialised with every other grant-store writer
            data = self._load()
            data["grants"][key] = grant
            write_json(self.grants_path, data)
        return grant

    def revoke_grant(self, content_id, platform):
        key = self.grant_key(content_id, platform)
        with locked(self.grants_path):
            data = self._load()
            g = data["grants"].get(key)
            if not g:
                return False
            g["revoked"] = True
            write_json(self.grants_path, data)
        return True
