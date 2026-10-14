# Publish-eligibility: placement grants (video + still) — release notes V01

Status: **REVIEW ONLY.** Do not merge or deploy without Nitin's explicit approval.
Governance remains `PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE` and `PUBLICATION_AUTHORIZED = FALSE`.

## Problem

The P2 publisher (Make scenario 9974134) calls `/v/publish-eligibility` for video and still channel placements, but the
verifier had two gaps:
- It only had a grant provisioner for posters.
- It did not bind the target account.

A grant for one placement could therefore not be created through a controlled path, and an approval did not cover
which account the post goes to.

## Change

| File | Change |
|---|---|
| `unpipe/publish_approval.py` | **Target-account binding.** When a grant carries `target_account`, a request for any other account (or no account) is refused with `TARGET_ACCOUNT_MISMATCH`. |
| `unpipe/publish_approval.py` | **Synthetic test grants (`test_only`).** They are honoured only for content ids in the reserved `test:` namespace, and only on a verifier started with `PUBLISH_ALLOW_TEST_GRANTS=1`. Otherwise the result is `TEST_GRANT_NOT_ALLOWED` or `MALFORMED_APPROVAL`. |
| `unpipe/placement_provisioner.py` (new) | Creates and revokes grants per `content_id::platform`, for medium video or poster. It refuses unless creative, final (video or asset) and publish approvals all exist and are bound to the fingerprint. |
| `approval_server.py` | Reads `PUBLISH_ALLOW_TEST_GRANTS`. The variable is not set in `render.yaml`, so production stays in strict mode. |
| `scripts/provision_placement.py` (new) | CLI for the provisioner, mirroring `scripts/provision_poster.py`. |
| Tests | `tests/test_placement_publish_approval.py`: unit tests, HTTP tests on 127.0.0.1 and poster-compatibility tests. `tests/test_p2_request_contract.py`: P2's stored request template and route filters against the real handler. |

**Fingerprint basis is unchanged** (`unpipe/canonical.compute_fingerprint`). No migration is needed: existing grants carry no `target_account` and no `test_only` field, and they are evaluated exactly as before — with one fail-closed exception: a grant for a content id in the reserved `test:` namespace without `test_only` is now refused (`MALFORMED_APPROVAL`). Known residual: account binding applies only to grants that carry `target_account` (all grants made with the new provisioner do; legacy poster/video grants do not).

## Compatibility evidence

- The full repo suite passes. Existing poster and video tests are unchanged.
- `PosterCompatibilityTests` proves three things:
  - A legacy poster request is still eligible.
  - A poster grant gets no new fields.
  - The existing refusals still apply: other bytes, other platform, other time.
- **New fields add refusals only; they never turn a refusal into an approval.** The target-account check and the test-namespace check sit *after* all existing checks.

## Deploy target (verified 2026-10-14)

- **Service and source:** Render service `unchained-approval` (`srv-dafht9f40ujc73bc48fg`), Docker, branch **`main`**, `autoDeploy: yes` (trigger: commit). PR previews are off.
- **Running build:** the live deploy is commit `594ccf2`, which equals `origin/main` today.
- **What triggers a deploy:** a merge to `main` deploys automatically. GitHub workflows have no push/PR trigger.

## Deploy plan (only after approval)

1. Nitin approves this PR.
2. Before merging, back up the verifier state: download `/data/_publish_grants.json` and `/data/_publish_approvals.json` via the Render shell or disk snapshot.
3. Merge into `main`. Render builds and deploys automatically.
4. Verify:
   - `GET /healthz` returns 200.
   - `POST /v/publish-eligibility` without a key returns 401.
   - With the key, a request for a non-existent content id returns `{"eligible":false,"reason":"NO_PUBLISH_APPROVAL"}`.
   - Do not create test grants in production.
5. Only then create grants for approved placements with `scripts/provision_placement.py` on the host.

## Rollback plan

- Render dashboard → service → Deploys → **Rollback** to the deploy of commit `594ccf2`. Alternatively, revert the merge commit on `main`, which redeploys automatically.
- Grants created with the new provisioner contain `target_account`. The old code ignores that field, so it would **not** enforce the account binding. After a rollback, revoke those grants with the CLI from this branch (or edit the store) until the binding is back.
- The approval and grant stores themselves are not migrated or changed by the deploy.

## Secrets

- `PUBLISH_ELIGIBILITY_APIKEY` stays only in the Render environment and the Make keychain (217337). No key appears in code, tests or docs.
- `PUBLISH_ALLOW_TEST_GRANTS` must never be set on the production service.
