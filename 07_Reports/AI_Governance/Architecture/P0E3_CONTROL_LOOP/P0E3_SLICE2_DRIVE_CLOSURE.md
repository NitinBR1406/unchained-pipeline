# P0-E3 Slice 2 — REAL Shared Drive Backend Closure

**Deterministic verdict:** `SAFE_FOR_SHA_PINNED_P0E3_LIVE_RUN = FALSE`
Reason: the GitHub Actions runner is **not** provisioned with Google Shared Drive credentials, so an
automated SHA-pinned live run cannot satisfy `REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED`. The Drive backend,
lifecycle and evidence contract are proven genuine (below), but CI auth is the one open gap.

Governance unchanged: `PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE`, `PUBLICATION_AUTHORIZED = FALSE`,
`FIRST_REAL_POSTER = PAUSED_BY_NITIN`. No commit, push, dispatch, deploy or publish.

## 1. Root cause / closure
The landed Slice-2 proved *cross-process* persistence (a Docker shared volume) but the mandatory system was
**real central Shared Drive persistence**. A shared volume can never be evidence of Shared Drive persistence.
Closure: a real client-driven `GoogleDriveBackend`, a distinct `REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED`
criterion that a shared volume can never satisfy, an independent Drive evidence contract, and a real Drive
lifecycle executed end-to-end (write → read-back → SHA256 → CAS HEAD → HEAD read-back → stale-writer
rejected → teardown → verify gone) against the authoritative Shared Drive.

## 2. Exact changed / new files
New: `control_loop/drive_client.py` (DriveClient interface + real `GoogleApiDriveClient` + `InMemoryDriveClient`),
`evidence/drive_proof/DRIVE_LIFECYCLE_PROOF.json` (recorded REAL Drive lifecycle), `tests/test_drive_backend.py`,
`tests/test_drive_negatives.py`, `evidence/freeze/SHA256SUMS.P0E3_SLICE2_DRIVE.txt`, this file.
Changed: `control_loop/live_backend.py` (real client-driven `GoogleDriveBackend` + teardown),
`control_loop/live_evidence.py` (`run_drive_lifecycle`, `drive_persistence_observed`, three-way teardown,
Drive contract in bundle/aggregate), `live_acceptance_p0e3.py` (Drive criterion + teardown distinction),
`live_driver.py` (real Drive lifecycle via ADC, fail-closed), `ci/p0e3-durable-live.yml` (Drive auth step +
Drive lifecycle run), `tests/test_live_acceptance_p0e3.py`, `tests/test_nb001_live.py`.
Unchanged: frozen P0-E1 `control_plane/*` and P0-E2 source (byte-identical); P0-E3 Slice-1 core
(`control_loop.py`, `persistence.py`, `state_model.py`, `durable_stores.py`, `nb001_normalize.py`).

## 3. Real Shared Drive authentication mechanism for CI (mechanism only, never secrets)
A Google **service account** provisioned to the runner as **Application Default Credentials** via
`google-github-actions/auth@v2` — Workload Identity Federation preferred, or a JSON key stored ONLY as the
GitHub Actions secret `GCP_DRIVE_SA`. The service account must be granted **Content Manager** on the
"Unchained Nitin — Master" Shared Drive (`0AG0CqqUZ6YuXUk9PVA`). The workflow step is guarded
`if: secrets.GCP_DRIVE_SA != ''`; `GoogleApiDriveClient` obtains creds through `google.auth.default()` and
never reads, prints, commits or embeds a secret. **This secret/binding does not currently exist** (the
repo's only Actions secret is `SHOTSTACK_PRODUCTION_API_KEY`), which is why the verdict is FALSE.

## 4. Disposable Drive namespace strategy
A per-run folder `P0E3_LIVE_ACCEPTANCE_DRIVE_TEST_<run_id>` is created directly under Shared Drive
`0AG0CqqUZ6YuXUk9PVA`. All version objects (`state_v{N}.json`) and `HEAD.json` live inside it. Teardown
trashes every child then the folder and independently verifies the namespace is gone. Authoritative Master
State and frozen P0-E2 evidence are never touched.

## 5. Independent Shared Drive evidence contract (`drive_persistence.json`)
`backend_type = "google_shared_drive"`, `drive_id = "0AG0CqqUZ6YuXUk9PVA"`, non-empty
`disposable_test_namespace`, `version_object_id`, `head_object_id`; `write_observed`, `readback_observed`,
`readback_sha256`, `expected_sha256`, `readback_sha_matches`, `cas_head_update_observed`,
`head_readback_observed`, `stale_write_rejected` all true; `SHARED_DRIVE_TEST_ARTIFACTS_REMAINING = false`.
`drive_persistence_observed()` requires ALL of these AND the exact authoritative drive_id; a `shared_volume`
backend_type (or wrong drive_id, empty object ids, mismatched SHA, absent CAS) → FALSE.

## 6. REAL Drive lifecycle proof (executed now via the authorized session Drive connector — recorded)
Real, disposable, and fully torn down against `0AG0CqqUZ6YuXUk9PVA`:
folder `1TwNkzI9tpvzpEW9hNDNAY3HCWIdDBIu3`; version object `1dZ03CPOnP9O5huxGAt7jJwax2uQTeGOv` (135 bytes),
read back from Drive, SHA `893e80cb…7b120a` matched byte-identical; HEAD object
`15dD879l-Cq3zY2J39yP1pMIv4aeGji4m`, read back, version 1 verified; stale writer (expected v0 vs live HEAD
v1) rejected; teardown trashed all three, search-by-title returned empty and metadata is `NOT_FOUND`
(`SHARED_DRIVE_TEST_ARTIFACTS_REMAINING = false`). This proves the backend + contract are genuine and
satisfiable. **It used the desktop session connector, not the CI runner** — hence it does not, by itself,
make the automated CI run safe.

## 7. Acceptance changes
Added `REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED` (independent of `REAL_CENTRAL_PERSISTENCE_OBSERVED`); a shared
volume forces it FALSE. Teardown split into `TEMPORAL_POC_INFRA_REMAINING_IS_FALSE`,
`SHARED_DRIVE_TEST_ARTIFACTS_REMAINING_IS_FALSE`, `POC_INFRA_REMAINING_IS_FALSE`. Gate now has 23 mandatory
criteria; derives Drive status only from the Drive contract (no aggregate-boolean substitution).

## 8. Negative tests (Drive; all force FAIL) — existing negatives preserved
shared-volume presented as Shared Drive · backend_type != google_shared_drive · wrong drive_id · missing
version_object_id · missing head_object_id · missing Drive readback · readback SHA mismatch · CAS HEAD not
observed · Shared Drive artifacts remain after teardown · drive evidence missing · stale not rejected ·
aggregate cannot mask a shared-volume contract.

## 9. Regression total
P0-E1 46 + P0-E2 77 + P0-E3 Slice-1 131 + P0-E3 Slice-2 81 = **335 / 335 PASS**
(Slice-2 = live_backend 10, live_acceptance 15, live_negatives 18, nb001_live 8, drive_backend 17,
drive_negatives 13).

## 10. Protected-file status
Frozen P0-E1 `control_plane/*` and P0-E2 source: byte-identical (`diff` clean). P0-E3 Slice-1 core files:
unchanged (hashes identical to Slice-1). Frozen P0-E2 evidence: untouched. `approval_authority.json`
empty/fail-closed. Nitin's Ed25519 private key never requested or exposed.

## 11. Teardown proof design
Two independent teardowns, distinct evidence: TEMPORAL disposable compose `down -v` →
`TEMPORAL_POC_INFRA_REMAINING`; Shared Drive namespace trashed + re-queried →
`SHARED_DRIVE_TEST_ARTIFACTS_REMAINING`; `POC_INFRA_REMAINING = (temporal OR drive)`. All three must be
boolean false for the gate to pass; NB-001 closes only when `POC_INFRA_REMAINING` is boolean false.

## 12. Verdict
`SAFE_FOR_SHA_PINNED_P0E3_LIVE_RUN = FALSE` — the only blocker is CI Drive auth. To flip to TRUE: provision
the `GCP_DRIVE_SA` service account (or WIF binding) with Content Manager on Shared Drive
`0AG0CqqUZ6YuXUk9PVA`. Nothing else is outstanding: backend, lifecycle, contract, acceptance, negatives and
teardown are implemented and proven, and the real Drive lifecycle has been demonstrated end-to-end.
