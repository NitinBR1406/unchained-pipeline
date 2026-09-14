#!/usr/bin/env python3
"""Produce a signed approval link (the notification mechanism) — Nitin never builds URLs.

Reads APPROVAL_SIGNING_SECRET (server-side), computes the frozen-JSON SHA for the campaign, and
returns a ready-to-tap URL. In production the notification layer calls create_link() and sends the
URL to Nitin's phone.

CLI: python3 make_approval_link.py <campaigns_root> <campaign_id> <gate> <base_url> [ttl]
gate = creative | final_video | publish
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unpipe.approval_service import ApprovalService
from unpipe.approvals import GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_FINAL_ASSET, GATE_PUBLISH
from unpipe.manifest import load_manifest
from unpipe.util import sha256_file

GATE_MAP = {"creative": GATE_CREATIVE, "final_video": GATE_FINAL_VIDEO,
            "final_asset": GATE_FINAL_ASSET, "publish": GATE_PUBLISH}


def _frozen_sha(campaigns_root, campaign_id):
    mani = load_manifest(Path(campaigns_root) / campaign_id / "campaign.json")
    fm = mani.get("frozen_master")
    p = Path(fm) if os.path.isabs(fm) else (Path(campaigns_root) / campaign_id / fm)
    return sha256_file(p.resolve())


def create_link(campaigns_root, campaign_id, gate, base_url, ttl=86400, secret=None):
    secret = secret or os.environ.get("APPROVAL_SIGNING_SECRET", "")
    svc = ApprovalService(secret, campaign_factory=lambda cid: None, approvers=[],
                          consumed_path=str(Path(campaigns_root) / "_approvals_consumed.json"))
    sha = _frozen_sha(campaigns_root, campaign_id)
    token = svc.create_request(campaign_id, GATE_MAP[gate], "frozen_master", sha, ttl=ttl)
    return f"{base_url.rstrip('/')}/approve?token={token}"


if __name__ == "__main__":
    root, cid, gate, base = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    ttl = int(sys.argv[5]) if len(sys.argv) > 5 else 86400
    print(create_link(root, cid, gate, base, ttl))
