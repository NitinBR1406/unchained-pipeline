#!/usr/bin/env python3
"""Produce a signed visualizer-approve link (reuses APPROVAL_SIGNING_SECRET).

The visualizer review-mail generator calls create_link() and sends the URL to Nitin. The link points
to the Render approval_server's /v/approve route, which verifies HMAC + expiry + single-use nonce
before forwarding to the NEW Make webhook. Nitin never builds URLs; the client only holds the opaque
signed token.

CLI: python3 make_visualizer_link.py <content_id> <title> <base_url> [ttl]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unpipe.visualizer_approval import VisualizerApprovalService


def create_link(content_id, title, base_url, ttl=86400, secret=None, consumed_path=None):
    secret = secret or os.environ.get("APPROVAL_SIGNING_SECRET", "")
    svc = VisualizerApprovalService(
        signing_secret=secret, approvers=[],
        consumed_path=consumed_path or str(Path("campaigns") / "_visualizer_approvals_consumed.json"))
    token = svc.create_request(content_id, title, ttl=ttl)
    return f"{base_url.rstrip('/')}/v/approve?token={token}"


if __name__ == "__main__":
    cid, title, base = sys.argv[1], sys.argv[2], sys.argv[3]
    ttl = int(sys.argv[4]) if len(sys.argv) > 4 else 86400
    print(create_link(cid, title, base, ttl))
