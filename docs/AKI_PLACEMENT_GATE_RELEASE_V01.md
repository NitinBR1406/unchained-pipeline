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

## Update 2026-10-14 (P2 version e)

P2 (Make 9974134) was changed in its stored configuration (still INACTIVE):

1. The lock is taken before the claim update (a stale bundle can no longer rewrite a finished record).
2. P2 fetches the exact bytes first and computes `sha256()` over them.
3. FB/YT additionally require Drive's `sha256Checksum` (SHA-256, same algorithm as the registry) to match.
4. Instagram requires a URL pinned to one object generation and named by its sha256.
5. The gate request carries the **computed** hash (`{{<n>.bytes_sha256}}`), so a changed file invalidates the approval at the verifier.

There is **no verifier code change** for this. `tests/test_p2_request_contract.py` and its fixture were regenerated from the stored P2 (read back via the Make API).

Not yet proven in Make itself: that IML `sha256()` over a binary buffer equals the true SHA-256. If it does not, every placement BLOCKS; it can never pass by accident. The isolated test scenario 9975568 (synthetic files, no data store, no upload) is ready for a manual "Run once".

## Post-deploy verification (after a later, approved deploy)

1. Before the merge, back up `/data/_publish_grants.json` and `/data/_publish_approvals.json`, and record their sha256.
2. After the deploy:
   - Render shows the new commit as `live`.
   - `GET /healthz` returns 200.
   - Logs show no tracebacks.
3. `POST /v/publish-eligibility` without a key returns 401. With the key:
   - `{}` returns `MALFORMED_REQUEST`;
   - an unknown content id returns `NO_PUBLISH_APPROVAL`.
4. The sha256 of both stores is unchanged. Nothing else is touched: no grant is created, no test grant, and `PUBLISH_ALLOW_TEST_GRANTS` stays unset.
5. Existing poster flow (P1 9627055): no change in behaviour. A legacy poster grant without `target_account` evaluates exactly as before; `PosterCompatibilityTests` covers this. Do not run P1 as a test.
6. If any of these checks fails, use the rollback below.

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
