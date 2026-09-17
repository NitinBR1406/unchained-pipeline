# P0-E3 — Durable Autonomous Control Loop — Slice 1 (Foundation)

**Verdict:** `P0E3_SLICE_1 = GREEN` · `SAFE_FOR_P0E3_LIVE_ACCEPTANCE = TRUE`
**MUST_FIX = 0 · MATERIAL = 0 · NON_BLOCKING = 1 (P0E2-NB-001, addressed in code)**
`PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE` · `PUBLICATION_AUTHORIZED = FALSE` · `FIRST_REAL_POSTER = PAUSED_BY_NITIN`

## Baseline
- P0-E2 FINAL FREEZE = GREEN · freeze commit `1265c68680068cdda7215334a9c009355d2a0dc1`
- Authoritative live run `35138346011` (run commit `c89277180557d1525d219adec680ebbf6692a10a`)
- TEMPORAL = LOCKED · P0-E2 autonomous runner = LIVE_VERIFIED · central persistence = VERIFIED
- P0-E1 / P0-E2 are **not redesigned**: the new package imports the frozen `control_plane` unchanged.

## Architecture / data flow (implemented)
```
EVENT LEDGER (append-only, hash-chained)            [frozen P0-E1 control_plane.ledger]
   -> DETERMINISTIC STATE REDUCER                   [frozen P0-E1 control_plane.reducer]
   -> VERSIONED MASTER STATE                        [state_model.py]
        state_version / previous_state_hash / state_hash / ledger_head_hash / updated_at / updated_by
        invariant: REPLAY(ledger) == persisted MASTER STATE
   -> CENTRAL PERSISTENCE                           [persistence.py]
        write candidate -> read back -> SHA256 verify -> only then success
        optimistic concurrency (expected_state_version + expected_ledger_head_hash); CONFLICT, never LWW
        immutable versioned files (state_v{N}.json never overwritten); atomic HEAD swap
   -> BACKLOG / DEPENDENCY RESOLUTION               [durable_stores.BacklogStore]
        canonical task schema; READY only when all deps COMPLETED; deterministic (priority, task_id)
   -> CLAIM + LEASE                                 [frozen P0-E1 control_plane.leases]
        exactly one live claim; heartbeat/expiry; safe reclaim by a different holder
   -> (TEMPORAL) EXECUTION                          [control_loop.py + frozen P0-E2 LiveRunner offline]
        job_id = SHA256(task_id + state_version + input_hash), recorded immutably in TASK_STARTED
        exactly-once side effect (durable across restart)  [durable_stores.DurableSideEffectStore]
   -> EVIDENCE -> STATE UPDATE -> AUTOMATIC NEXT READY TASK   [control_loop.run(), bounded]
```

## Key durability principle
The **Event Ledger is the only source of truth.** Backlog status, lease liveness and Master State are pure
projections re-derived from the ledger on start. A crash at any boundary is recovered by re-deriving and
continuing; the immutable job identity guarantees no side effect is ever applied twice, and any TASK_RESULT
already in the ledger is never lost or re-run. `WAITING_FOR_NITIN` parks durably and never blocks independent
READY work. `now` is an explicit deterministic clock — no wall clock, no randomness.

## Human gates (P0-E1 model preserved)
No AI can create, infer, impersonate or fabricate a Nitin approval; only an independently Ed25519-verified
detached signature grants a gate. `approval_authority.json` remains empty / fail-closed. A gated task
(`TASK_C`) parks and never self-approves.

## Slice-1 acceptance (all mandatory criteria explicitly satisfied; fail-closed)
| Criterion | Result |
|---|---|
| EVENT_LEDGER_APPEND_ONLY | TRUE |
| EVENT_LEDGER_CHAIN_VALID | TRUE |
| STATE_REPLAY_MATCHES_MASTER | TRUE |
| STATE_VERSION_MONOTONIC | TRUE |
| CENTRAL_WRITE_READBACK_VERIFIED | TRUE |
| STALE_WRITE_REJECTED | TRUE |
| CONCURRENT_DOUBLE_CLAIM_COUNT | 0 |
| STALE_LEASE_RECLAIM | PASS |
| DUPLICATE_SIDE_EFFECT_COUNT | 0 |
| AUTONOMOUS_NEXT_TASK | PASS |
| WAITING_WORKFLOW_BLOCKS_OTHER_WORK | FALSE |
| HUMAN_MESSAGE_RELAY_REQUIRED | FALSE |
| NO_APPROVAL_FABRICATED | TRUE |
| CRASH_RECOVERY_MATRIX (A–F) | PASS |

Crash-recovery matrix boundaries proven: A after ledger append/before state persistence; B after state
write/before read-back; C after claim/before execution; D during execution; E after side effect/before
completion event; F while a task is WAITING_FOR_NITIN. Each restart: deterministic reconcile, 0 duplicate
side effects, no lost completed work, no fabricated approval, independent work continues, replay matches.

## Tests / regression
- P0-E3 offline: 131/131 PASS (state_model 12, persistence 13, control_loop 19, concurrency 14,
  crash_recovery 42, nb001 12, acceptance_gate 19)
- Full offline regression P0-E1 + P0-E2 + P0-E3: **254 / 254 PASS** (frozen 123 unchanged + 131 new)

## P0E2-NB-001 (non-blocking)
`nb001_normalize.py` reconciles a P0E2_LIVE_RESULTS-style aggregate `POC_INFRA_REMAINING` to `false` **only**
when authoritative teardown evidence explicitly proves false (fail-closed otherwise), with 12 regression
checks. The frozen P0-E2 aggregate/acceptance files themselves are intentionally **not** mutated — P0-E2
GREEN is not reopened.

## Security / scope
No secrets in repo/evidence. No Ed25519 private key requested. `approval_authority.json` fail-closed.
No production / Make / Render mutation. No social publication. Local filesystem persistence backend stands
in for the Shared Drive offline; the identical write→read-back→SHA256 contract was proven live against the
Shared Drive at the P0-E2 freeze. No live Drive persistence is fabricated here.
