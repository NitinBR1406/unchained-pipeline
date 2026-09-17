"""P0-E3 Slice-2 WIF pre-flight — fail-closed validation of the keyless auth variables.

Runs in the workflow BEFORE the Drive live acceptance. It validates the three NON-SECRET repository
variables required for Google Workload Identity Federation and refuses to proceed (exit 1) if any is
missing or malformed. There is NO long-lived-key fallback: WIF is the only accepted path.

Required repository variables (github `vars`, not secrets):
  GCP_PROJECT_ID              e.g. my-project-123
  GCP_WIF_PROVIDER           projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL>/providers/<PROVIDER>
  GCP_DRIVE_SERVICE_ACCOUNT  <service-account>@<project>.iam.gserviceaccount.com

This module NEVER reads a secret, a key, or a token — only these three public identifiers.
"""
import os, re, sys

REQUIRED_VARS = ["GCP_PROJECT_ID", "GCP_WIF_PROVIDER", "GCP_DRIVE_SERVICE_ACCOUNT"]

PROVIDER_RE = re.compile(
    r"^projects/\d+/locations/global/workloadIdentityPools/[A-Za-z0-9._-]+/providers/[A-Za-z0-9._-]+$")
SA_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][-a-z0-9]*\.iam\.gserviceaccount\.com$")
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


def validate(env):
    """Return (ok, errors). Fail-closed: any missing/blank/malformed value is an error."""
    errors = []
    for k in REQUIRED_VARS:
        v = (env.get(k) or "").strip()
        if not v:
            errors.append("MISSING:%s" % k)
    # only run format checks on values that are present
    prov = (env.get("GCP_WIF_PROVIDER") or "").strip()
    if prov and not PROVIDER_RE.match(prov):
        errors.append("MALFORMED:GCP_WIF_PROVIDER")
    sa = (env.get("GCP_DRIVE_SERVICE_ACCOUNT") or "").strip()
    if sa and not SA_RE.match(sa):
        errors.append("MALFORMED:GCP_DRIVE_SERVICE_ACCOUNT")
    proj = (env.get("GCP_PROJECT_ID") or "").strip()
    if proj and not PROJECT_RE.match(proj):
        errors.append("MALFORMED:GCP_PROJECT_ID")
    # explicitly forbid any long-lived-key variable leaking into the auth path
    for forbidden in ("GCP_DRIVE_SA", "GOOGLE_CREDENTIALS", "GCP_SA_KEY", "credentials_json"):
        if (env.get(forbidden) or "").strip():
            errors.append("FORBIDDEN_LONG_LIVED_CREDENTIAL:%s" % forbidden)
    return (len(errors) == 0), errors


def main():
    ok, errors = validate(os.environ)
    if ok:
        print("WIF_PREFLIGHT=PASS")
        sys.exit(0)
    print("WIF_PREFLIGHT=FAIL", errors)
    sys.exit(1)


if __name__ == "__main__":
    main()
