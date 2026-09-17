# P0-E3 Slice 2 — LIVE ACCEPTANCE (built, not run)

**Verdict:** `SAFE_FOR_SHA_PINNED_P0E3_LIVE_RUN = TRUE`
Baseline: P0-E3 Slice 1 GREEN @ `b09d044404fc410f0894d256e76bf7f164e2ae7e`; P0-E2 freeze GREEN; Temporal LOCKED.
`PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE` · `PUBLICATION_AUTHORIZED = FALSE` · `FIRST_REAL_POSTER = PAUSED_BY_NITIN`

The live run has **not** been started, committed, pushed, or dispatched.

## Workflow design (`ci/p0e3-durable-live.yml`)
`workflow_dispatch` with a single required input `ref` — an **explicit 40-hex commit SHA, no default, no
branch fallback**. Steps: validate SHA is 40-hex → checkout that SHA → assert `CHECKED_OUT_SHA == requested`
(write `checkout.json`, fail otherwise) → pin host `temporalio==1.33.0` + cryptography → bring up the
**frozen P0-E1 disposable Temporal compose** (postgres + temporal + worker1/worker2 running the
ControlPlaneTask worker) with a shared `SE_DIR` (incl. `central/`) → dispatch **real** Temporal workflows via
the **frozen P0-E2 LiveRunner**, extract real workflow/run ids into `workflows.json` (never invented) → run
the **P0-E3 durable loop live** against a **real cross-process central backend** on the shared volume
(`live_driver.py run`) → **unconditional teardown** (`down -v`) → verify teardown → `poc_infra.json`
(`POC_INFRA_REMAINING`) and reassemble the aggregate (NB-001 normalization) → **strict independent
acceptance reducer** (`live_acceptance_p0e3.py`) writes the verdict → upload all evidence (even on failure) →
**fail-closed final gate** exits non-zero unless `FINAL == PASS`.

## Live systems verified
Real disposable Temporal infrastructure; real cross-process central Shared-Drive-style persistence backend
(`SharedVolumeBackend`; the Google Shared Drive drop-in `GoogleDriveBackend` uses the identical 3-op
contract and the byte-identical write→read-back→SHA256 lifecycle already proven live at the P0-E2 freeze);
the P0-E3 Event Ledger / Reducer / versioned Master State / CAS persistence; disposable P0-E3 test
namespace/state only. No authoritative production state is touched.

## Live acceptance criteria (all independently derived; fail-closed)
`EVENT_LEDGER_APPEND_ONLY`, `EVENT_LEDGER_CHAIN_VALID`, `STATE_REPLAY_MATCHES_MASTER`,
`STATE_VERSION_MONOTONIC`, `CENTRAL_WRITE_READBACK_VERIFIED`, `CENTRAL_READBACK_SHA_MATCH`,
`STALE_WRITE_REJECTED`, `CONCURRENT_DOUBLE_CLAIM_COUNT == 0`, `STALE_LEASE_RECLAIM == PASS`,
`DUPLICATE_SIDE_EFFECT_COUNT == 0`, `AUTONOMOUS_NEXT_TASK == PASS`,
`WAITING_WORKFLOW_BLOCKS_OTHER_WORK == FALSE`, `HUMAN_MESSAGE_RELAY_REQUIRED == FALSE`,
`NO_APPROVAL_FABRICATED == TRUE`, `REAL_TEMPORAL_WORKFLOWS_OBSERVED == TRUE`,
`REAL_CENTRAL_PERSISTENCE_OBSERVED == TRUE`, `CHECKED_OUT_SHA_MATCHES_REQUEST`,
`CRASH_RECOVERY_MATRIX == PASS`, `POC_INFRA_REMAINING == FALSE`, `P0E2_NB_001 == CLOSED`. (20 criteria.)

The reducer re-opens the live ledger, re-derives Master State, and re-reads the central store to **recompute**
read-back SHAs — an aggregate boolean can never substitute for missing underlying evidence.

## Crash / recovery matrix — live (A–F)
A ledger-append-before-state-persist; B state-write-before-read-back; C claim-before-execution; D
during-execution; E after-side-effect-before-completion; F one task WAITING_FOR_NITIN while independent work
continues. Each case proves `RECOVERY_OBSERVED`, `STATE_RECONCILED`, `NO_LOST_COMPLETED_WORK`,
`DUPLICATE_SIDE_EFFECT_COUNT == 0`, `NO_APPROVAL_FABRICATED`.

## Central persistence lifecycle
candidate write → read back → SHA256 verify → CAS HEAD update → authoritative success. A stale concurrent
writer is rejected (CONFLICT), HEAD untouched — never last-write-wins. Versioned disposable objects
(`state_v{N}.json` never overwritten). Disposable infra torn down after the run; teardown proves
`POC_INFRA_REMAINING = FALSE`.

## Negative-test matrix (18 offline; all force FAIL)
missing workflow ids · missing central-persistence evidence · empty read-back hash · SHA mismatch · stale
write accepted · double claim > 0 · duplicate side effect > 0 · WAITING blocks independent work · human relay
required · fabricated approval · missing crash scenario · failed crash recovery · POC infra remains · wrong
checkout SHA (non-40-hex) · null decision-critical evidence (empty ledger) · tampered ledger chain ·
aggregate boolean cannot mask missing central evidence.

## Expected live evidence artifact structure (`P0E3_CONTROL_LOOP/evidence/`)
`checkout.json` · `EVENT_LEDGER.jsonl` · `central/` (versioned objects + `HEAD.json`) · `workflows.json` ·
`central_persistence.json` · `replay.json` · `autonomy.json` · `concurrency.json` · `crash_matrix.json` ·
`poc_infra.json` · `P0E3_LIVE_RESULTS.json` · `P0E3_LIVE_ACCEPTANCE_VERDICT.json`.

## Offline regression
P0-E1 46 + P0-E2 77 + P0-E3 Slice-1 131 + P0-E3 Slice-2 50 (live_backend 10, live_acceptance 14,
negatives 18, nb001_live 8) = **304 / 304 PASS**.

## Security / governance
No secrets in repo/evidence. Nitin's Ed25519 private key never requested or exposed;
`approval_authority.json` stays empty/fail-closed. No production / Make / Render / social mutation.
`FIRST_REAL_POSTER = PAUSED_BY_NITIN`. Production deploy + publication pinned FALSE in the gate.
