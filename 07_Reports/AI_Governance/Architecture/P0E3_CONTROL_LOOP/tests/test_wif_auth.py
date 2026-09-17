"""P0-E3 Slice-2 WIF auth closure: keyless Workload Identity Federation only, fail-closed, no long-lived key.

Proves (offline, deterministic):
  1-4  missing/malformed WIF variables => pre-flight fails closed
  5    no inline JSON credential (credentials_json) path in the workflow
  6    no GCP_DRIVE_SA (long-lived key) path in the workflow
  7    no WIF->long-lived fallback exists
  8    id-token: write present
  9    contents: read present
  10   auth action is google-github-actions/auth@v3 with the three vars.*
  11   SharedVolumeBackend cannot satisfy live Shared Drive acceptance
"""
import os, sys, yaml
from _harness import Counter, ROOT

sys.path.insert(0, os.path.join(ROOT, "ci"))
import wif_preflight as W
from control_loop import live_evidence as LE
c = Counter("WIF")

WF = os.path.join(ROOT, "ci", "p0e3-durable-live.yml")
doc = yaml.safe_load(open(WF))
raw = open(WF).read()
ON = doc.get("on", doc.get(True))   # PyYAML 1.1 parses the bareword `on` as boolean True
job = doc["jobs"]["live"]
steps = job["steps"]
auth = [s for s in steps if str(s.get("uses", "")).startswith("google-github-actions/auth")]

GOOD = {"GCP_PROJECT_ID": "unchained-nitin-123",
        "GCP_WIF_PROVIDER": "projects/123456789012/locations/global/workloadIdentityPools/github-pool/providers/github-oidc",
        "GCP_DRIVE_SERVICE_ACCOUNT": "p0e3-drive@unchained-nitin-123.iam.gserviceaccount.com"}

# baseline: a fully-specified var set passes the pre-flight (format-valid; not a claim that CI is wired)
c.ok("preflight_pass_on_valid_vars", W.validate(GOOD)[0] is True)

# 1-4 fail-closed on each missing / malformed variable
c.ok("1_missing_project_id_fail", W.validate({**GOOD, "GCP_PROJECT_ID": ""})[0] is False)
c.ok("2_missing_wif_provider_fail", W.validate({**GOOD, "GCP_WIF_PROVIDER": ""})[0] is False)
c.ok("3_malformed_provider_fail",
     W.validate({**GOOD, "GCP_WIF_PROVIDER": "projects/x/providers/y"})[0] is False)
c.ok("4_missing_service_account_fail", W.validate({**GOOD, "GCP_DRIVE_SERVICE_ACCOUNT": ""})[0] is False)
c.ok("4b_malformed_service_account_fail",
     W.validate({**GOOD, "GCP_DRIVE_SERVICE_ACCOUNT": "not-an-sa-email"})[0] is False)

# 5 no inline JSON credential input anywhere in the workflow
c.ok("5_no_credentials_json_path", "credentials_json" not in raw)
c.ok("5b_auth_step_has_no_credentials_json", all("credentials_json" not in (s.get("with") or {}) for s in steps))

# 6 no GCP_DRIVE_SA long-lived-key path anywhere
c.ok("6_no_gcp_drive_sa_path", "GCP_DRIVE_SA" not in raw)

# 7 no WIF -> long-lived fallback: exactly one auth step, it is v3, and there is no secrets.* usage at all
c.ok("7_single_auth_step", len(auth) == 1)
c.ok("7b_no_secrets_reference_anywhere", "secrets." not in raw)
c.ok("7c_preflight_rejects_longlived_var", W.validate({**GOOD, "GCP_DRIVE_SA": "{json}"})[0] is False)

# 8-9 job permissions
perms = doc.get("permissions", {})
c.ok("8_id_token_write", perms.get("id-token") == "write")
c.ok("9_contents_read", perms.get("contents") == "read")

# 10 auth action pinned to v3 and uses the three vars.*
a = auth[0]
c.ok("10_auth_is_v3", a["uses"] == "google-github-actions/auth@v3")
w = a.get("with") or {}
c.ok("10b_project_id_from_var", w.get("project_id") == "${{ vars.GCP_PROJECT_ID }}")
c.ok("10c_provider_from_var", w.get("workload_identity_provider") == "${{ vars.GCP_WIF_PROVIDER }}")
c.ok("10d_service_account_from_var", w.get("service_account") == "${{ vars.GCP_DRIVE_SERVICE_ACCOUNT }}")

# pre-flight step runs BEFORE the Drive live-acceptance run step, and before the auth step too
names = [str(s.get("name", "")) for s in steps]
def idx(sub):
    return next(i for i, n in enumerate(names) if sub in n)
c.ok("preflight_before_drive_run", idx("WIF pre-flight") < idx("Run P0-E3 durable loop live"))
c.ok("preflight_before_auth", idx("WIF pre-flight") < idx("Workload Identity Federation"))

# 11 SharedVolumeBackend can never satisfy REAL Shared Drive acceptance
from control_loop.live_backend import SharedVolumeBackend
sv_contract = {"backend_type": SharedVolumeBackend("/tmp/x").describe()["backend_type"],
               "drive_id": LE.AUTHORITATIVE_DRIVE_ID, "disposable_test_namespace": "ns",
               "version_object_id": "v", "head_object_id": "h", "write_observed": True,
               "readback_observed": True, "expected_sha256": "a", "readback_sha256": "a",
               "readback_sha_matches": True, "cas_head_update_observed": True,
               "head_readback_observed": True, "stale_write_rejected": True}
c.ok("11_shared_volume_cannot_satisfy_drive", LE.drive_persistence_observed(sv_contract) is False)

# preserved guarantees still present in the workflow
c.ok("preserved_sha_input_required", ON["workflow_dispatch"]["inputs"]["ref"]["required"] is True)
c.ok("preserved_drive_id", "0AG0CqqUZ6YuXUk9PVA" in raw)
c.ok("preserved_teardown_temporal", any("Teardown" in n for n in names))
c.ok("preserved_acceptance_gate_step", any("acceptance verdict" in n.lower() for n in names))
c.ok("preserved_fail_closed_final_gate", any("FAIL-CLOSED final gate" in n for n in names))

c.done()
