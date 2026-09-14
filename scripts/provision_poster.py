"""CLI: provision or revoke a poster publish GRANT. Nitin-triggered, run on the verifier host.

Creates/revokes grants ONLY; never approves content. `create` refuses unless the three human gates
(creative + final-asset + publish) already exist bound to the computed fingerprint.

Examples:
  python3 -m scripts.provision_poster create \\
    --grants /data/_publish_grants.json --approvals /data/_publish_approvals.json \\
    --poster-id poster_serie_01 --image /path/poster_serie_01.jpg \\
    --caption "Bollywood zoals het bedoeld is." --platform instagram \\
    --scheduled-at "2026-06-01 12:00:00" --schedule-version v1 --exp 4102444800

  python3 -m scripts.provision_poster revoke \\
    --grants /data/_publish_grants.json --poster-id poster_serie_01
"""
import argparse
import sys

from unpipe.approvals import ApprovalStore
from unpipe.provisioner import PosterProvisioner, ProvisionError


def main(argv=None):
    p = argparse.ArgumentParser(description="Poster publish grant provisioner (grants only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--grants", required=True)
    c.add_argument("--approvals", required=True)
    c.add_argument("--poster-id", required=True)
    c.add_argument("--image", required=True, help="path to the EXACT image bytes to be published")
    c.add_argument("--caption", required=True)
    c.add_argument("--platform", required=True)
    c.add_argument("--scheduled-at", required=True, help="'YYYY-MM-DD HH:MM:SS' (Europe/Amsterdam)")
    c.add_argument("--schedule-version", required=True)
    c.add_argument("--exp", required=True, type=int, help="grant expiry epoch seconds")
    c.add_argument("--approval-id", default=None)

    r = sub.add_parser("revoke")
    r.add_argument("--grants", required=True)
    r.add_argument("--poster-id", required=True)

    a = p.parse_args(argv)

    if a.cmd == "create":
        with open(a.image, "rb") as f:
            image_bytes = f.read()
        store = ApprovalStore(a.approvals)
        prov = PosterProvisioner(store, a.grants)
        try:
            grant = prov.create_grant(a.poster_id, image_bytes, a.caption, a.platform,
                                      a.scheduled_at, a.schedule_version, a.exp, approval_id=a.approval_id)
        except ProvisionError as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        print(f"GRANT_CREATED content_id={a.poster_id} platform={a.platform} "
              f"fingerprint={grant['fingerprint']}")
        return 0

    if a.cmd == "revoke":
        prov = PosterProvisioner(None, a.grants)
        ok = prov.revoke_grant(a.poster_id)
        print("REVOKED" if ok else "NOT_FOUND", a.poster_id)
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
