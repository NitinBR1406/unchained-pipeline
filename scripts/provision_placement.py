"""CLI: provision or revoke a publish GRANT for one channel placement (video or still). Nitin-triggered, run on the
verifier host. Creates/revokes grants ONLY; never approves content. `create` refuses unless the three human gates
(creative + final video/asset + publish) already exist for `<content_id>::<platform>`, bound to the computed fingerprint.

The asset hash is computed from the EXACT file bytes; the packaging hash from the exact title + caption that will be
posted. The target account is bound into the grant (the verifier refuses any other account).

Examples:
  python3 -m scripts.provision_placement create \\
    --grants /data/_publish_grants.json --approvals /data/_publish_approvals.json \\
    --content-id aki:post:D01-V01 --platform youtube_shorts --target-account "<account label as in the data store>" \\
    --file /path/AKI_POST_D01_V01_CAPTION_V01.mp4 --title-file title.txt --caption-file caption.txt \\
    --scheduled-at "2026-10-19 19:00:00" --schedule-version 2 --exp 1795000000 --medium video

  python3 -m scripts.provision_placement revoke --grants /data/_publish_grants.json \\
    --content-id aki:post:D01-V01 --platform youtube_shorts
"""
import argparse
import hashlib
import sys

from unpipe.approvals import ApprovalStore
from unpipe.placement_provisioner import PlacementProvisioner, ProvisionError


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path):
    if not path:
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    p = argparse.ArgumentParser(description="Placement publish grant provisioner (grants only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--grants", required=True)
    c.add_argument("--approvals", required=True)
    c.add_argument("--content-id", required=True)
    c.add_argument("--platform", required=True)
    c.add_argument("--target-account", required=True)
    c.add_argument("--file", default="", help="the EXACT media bytes that will be published")
    c.add_argument("--asset-sha256", default="", help="instead of --file: sha256 of the exact media bytes")
    c.add_argument("--packaging-sha256", default="", help="instead of --title-file/--caption-file: packaging sha256 of the exact texts")
    c.add_argument("--title-file", default="", help="UTF-8 file with the exact title (YouTube); empty for none")
    c.add_argument("--caption-file", default="", help="UTF-8 file with the exact caption/description")
    c.add_argument("--scheduled-at", required=True, help="'YYYY-MM-DD HH:MM:SS' Europe/Amsterdam")
    c.add_argument("--schedule-version", required=True)
    c.add_argument("--exp", required=True, type=int)
    c.add_argument("--medium", choices=("video", "poster"), default="video")
    c.add_argument("--approval-id", default=None)
    r = sub.add_parser("revoke")
    r.add_argument("--grants", required=True)
    r.add_argument("--content-id", required=True)
    r.add_argument("--platform", required=True)
    a = p.parse_args(argv)

    if a.cmd == "create":
        prov = PlacementProvisioner(ApprovalStore(a.approvals), a.grants)
        if bool(a.file) == bool(a.asset_sha256) or bool(a.caption_file) == bool(a.packaging_sha256):
            print("REFUSED: give exactly one of --file/--asset-sha256 and one of --caption-file/--packaging-sha256", file=sys.stderr)
            return 2
        try:
            asset = _sha256_file(a.file) if a.file else a.asset_sha256
            if a.packaging_sha256:
                g = prov.create_grant_from_hashes(a.content_id, asset, a.platform, a.target_account.strip(), a.packaging_sha256,
                                                  a.scheduled_at, a.schedule_version, a.exp, medium=a.medium, approval_id=a.approval_id)
            else:
                g = prov.create_grant(a.content_id, asset, a.platform, a.target_account.strip(), _read(a.title_file),
                                      _read(a.caption_file), a.scheduled_at, a.schedule_version, a.exp, medium=a.medium,
                                      approval_id=a.approval_id)
        except ProvisionError as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        print(f"GRANT_CREATED content_id={a.content_id} platform={a.platform} fingerprint={g['fingerprint']}")
        return 0
    ok = PlacementProvisioner(None, a.grants).revoke_grant(a.content_id, a.platform)
    print("REVOKED" if ok else "NOT_FOUND", a.content_id, a.platform)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
