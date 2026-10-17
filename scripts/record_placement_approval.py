"""CLI: record NITIN's three human gate decisions (creative + final video/asset + publish) for ONE channel placement,
bound to the exact placement fingerprint. Run by Nitin on the verifier host (Render shell). Writes ONLY the approval store;
it never creates a grant (that stays scripts/provision_placement.py) and never publishes.

The fingerprint is computed from the exact media bytes sha256 and the packaging sha256 of the exact title + caption
(unpipe.canonical) - the same values Make sends to /v/publish-eligibility. A different file, text, platform or schedule
version gives a different fingerprint, so these approvals do not apply to it.

Example:
  python3 -m scripts.record_placement_approval --approvals /data/_publish_approvals.json \\
    --content-id aki:post:TEASER-NEON-V03 --platform youtube_shorts \\
    --asset-sha256 <64 hex> --packaging-sha256 <64 hex> --schedule-version 1 \\
    --approver nitin --evidence "chat brief 2026-10-17 (dress rehearsal teaser)"
"""
import argparse
import os
import re
import sys

from unpipe.approvals import ApprovalStore, APPROVE, GATE_CREATIVE, GATE_PUBLISH
from unpipe.canonical import compute_fingerprint, final_gate_for_medium, MEDIUM_VIDEO, MEDIUM_POSTER

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def main(argv=None):
    p = argparse.ArgumentParser(description="Record Nitin's 3 gate approvals for one placement fingerprint")
    p.add_argument("--approvals", required=True)
    p.add_argument("--content-id", required=True)
    p.add_argument("--platform", required=True)
    p.add_argument("--asset-sha256", required=True)
    p.add_argument("--packaging-sha256", required=True)
    p.add_argument("--schedule-version", required=True)
    p.add_argument("--medium", choices=("video", "poster"), default="video")
    p.add_argument("--approver", required=True)
    p.add_argument("--evidence", required=True, help="where the human decision is recorded (e.g. brief/date)")
    a = p.parse_args(argv)
    approvers = {x.strip() for x in os.environ.get("APPROVERS", "nitin").split(",") if x.strip()}
    if a.approver not in approvers:
        print("REFUSED: approver not in APPROVERS", file=sys.stderr)
        return 2
    if a.content_id.startswith("test:"):
        print("REFUSED: test namespace is never approved in a real store", file=sys.stderr)
        return 2
    if not (HEX64.match(a.asset_sha256) and HEX64.match(a.packaging_sha256)):
        print("REFUSED: hashes must be 64 lowercase hex", file=sys.stderr)
        return 2
    fp = compute_fingerprint(a.content_id, a.asset_sha256, a.platform, a.packaging_sha256, a.schedule_version)
    key = "{}::{}".format(a.content_id, a.platform)
    store = ApprovalStore(a.approvals)
    medium = MEDIUM_VIDEO if a.medium == "video" else MEDIUM_POSTER
    for gate in (GATE_CREATIVE, final_gate_for_medium(medium), GATE_PUBLISH):
        store.record(key, a.content_id, gate, APPROVE, a.approver, fp, notes=a.evidence)
    print("APPROVALS_RECORDED key={} fingerprint={}".format(key, fp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
