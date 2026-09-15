# P0E ADR 001 — Temporal Control Plane (Architecture Decision Record)

- **Decision:** Adopt **Temporal** as the Unchained Nitin autonomous control plane.
- **Status:** APPROVED (architecture). Bake-off CLOSED. Winner = TEMPORAL.
- **Date/Time:** 2026-01-01 (frozen from V02.12 bake-off evidence).
- **Owner / Release Authority:** Nitin Ramdaras. **Engineering Executor:** Claude. **Architecture/Governance:** ChatGPT.

## Authoritative evidence
- **GITHUB_RUN_ID:** 34979288601
- **GIT_COMMIT_SHA:** fe1b83c1d36960016834b9eda6577c53a84c159a
- **BRANCH:** p0e/live-control-plane-bakeoff
- **Evidence version:** P0-E V02.12
- **Temporal SDK:** 1.33.0  ·  **Hatchet SDK:** 0.47.0
- Evidence artifacts (bake-off harness): `P0E_LIVE_BAKEOFF/` (results.jsonl, P0E_TEMPORAL_LIVE_EVIDENCE_V01.json, P0E_ACCEPTANCE_BY_ENGINE_V01.json). Historical evidence is NOT overwritten.

## Decision-critical results (Temporal)
DURABLE_HUMAN_WAIT, CRASH_DURING_LONG_ACTIVITY, ORCHESTRATOR_DB_INTERRUPTION, DUPLICATE_STALE_EVENTS, IDEMPOTENCY_UNDER_RETRY, PARALLEL_AUTONOMY_20 — **6/6 OBSERVED_PASS**.

## Five acceptance invariants (Temporal, per-engine reducer)
- WAITING_WORKFLOW_BLOCKS_OTHER_WORK = FALSE
- WORKER_SLOT_HELD_DURING_HUMAN_WAIT = FALSE
- STATE_RECOVERED_AFTER_RESTART = TRUE
- DUPLICATE_SIDE_EFFECT_COUNT = 0
- HUMAN_MESSAGE_RELAY_REQUIRED = FALSE
→ **5/5 MET; ACCEPTANCE_ALL_MET = TRUE.** Hatchet did not meet the threshold.

## Why Temporal was selected
Temporal met every decision-critical durability test and all five acceptance invariants on live disposable infrastructure: durable human waits that hold no worker slot, independent parallel autonomy, deterministic crash/DB-restart recovery, and zero duplicate side effects under retry. Hatchet did not reach an equivalent, verified acceptance state.

## Explicit statements
- **The Temporal-vs-Hatchet comparison is CLOSED.** No further Hatchet remediation; no new orchestration framework; criteria are not re-interpreted or altered retroactively.
- **PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE.** This ADR authorizes architecture only, not production deployment.
- P1 (scenario 9627055) is unchanged; FIRST_REAL_POSTER remains PAUSED_BY_NITIN; no grants, no arming, no publication.

## Rollback / revisit conditions
Revisit only if: (a) a reproducible Temporal durability regression violates any of the five invariants on live evidence; (b) an operational constraint (licensing/cost/hosting) makes Temporal infeasible; or (c) Nitin (Release Authority) explicitly reopens the decision. Any revisit requires a new ADR superseding this one; this record is not edited in place.

## Provenance
Authored by Claude (engineering executor) under the P0-E1 execution order; architecture authority ChatGPT; release authority Nitin. Frozen from run 34979288601 @ commit fe1b83c1d36960016834b9eda6577c53a84c159a.
