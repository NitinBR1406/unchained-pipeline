# P0-E Live-Server Bake-Off Harness — Temporal vs Hatchet

> HONEST STATUS: This harness was authored from the official SDK/deployment docs. It was **NOT executed
> in the Cowork sandbox**, which has no Docker, no PostgreSQL, no Temporal CLI, and no package-registry
> or download access (PyPI/npm/download.temporal.io all return 403). A genuine live-server bake-off
> requires a Docker-capable host. Run it there (your dev machine, a cloud VM, or Codespaces) and paste
> the `RESULTS_TEMPLATE.json` back — or grant a Docker-capable environment and I will run + analyse it.
> No fabricated "live" numbers are provided.

All production prohibitions hold: this harness NEVER touches REAL P1 9627055, datastore 177455, the
Render verifier, real platform credentials, real approvals/grants, or the Aakhri Ishq master. It uses
disposable infra, mock agents, a safe sink, and explicit idempotency/dedup.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ with `pip` access
- `pip install temporalio hatchet-sdk` (in the respective worker envs)

## Run — Temporal
```
docker compose -f docker-compose.temporal.yml up -d      # temporal server + postgres + UI:8233
pip install temporalio
python temporal_bakeoff.py --worker &                    # start worker
python temporal_bakeoff.py --tests                       # runs the 7 decision-critical tests
```
## Run — Hatchet
```
docker compose -f docker-compose.hatchet.yml up -d        # hatchet engine + postgres + dashboard
export HATCHET_CLIENT_TOKEN=...                            # from hatchet dashboard
pip install hatchet-sdk
python hatchet_bakeoff.py --worker &
python hatchet_bakeoff.py --tests
```

## The 7 decision-critical tests (each writes a line to RESULTS)
1. **DURABLE_HUMAN_WAIT** — start workflow → approval wait → `docker kill` the worker → restart worker
   (and restart the server container where safe) → send approve signal/event → assert exact resume +
   assert no worker slot was occupied during the wait (check queue/worker metrics).
2. **CRASH_DURING_LONG_ACTIVITY** — 2–5 min mock multimodal activity with heartbeats → hard-kill worker
   mid-run → measure detection time (heartbeat-timeout) + retry/resume → assert the explicit
   idempotency key prevented a duplicate side effect (dedup store count == 1).
3. **ORCHESTRATOR_DB_INTERRUPTION** — restart the Postgres container (and server) → restore → assert
   workflow state + event history integrity, no duplicated completion.
4. **DUPLICATE_STALE_EVENTS** — duplicate approve, duplicate dispatch, delayed stale-worker completion,
   out-of-order event → assert deterministic final state.
5. **PARALLEL_AUTONOMY** — Workflow A parked in AWAITING_NITIN while 20 independent tasks run across
   multiple workers with mixed success/retry/failure → record throughput, queue behaviour, starvation,
   lock contention, and wait-state resource use.
6. **AUDIT_RECOVERY** — after the failures: can an engineer reconstruct exactly what happened? can state
   be replayed/recovered? how much custom ledger logic was needed? how clear is stale/duplicate
   visibility? (qualitative + LOC count of custom glue).
7. **OPS_BURDEN** — record services/containers, DB deps, config lines, setup time, upgrade surface,
   backup/restore steps, idle + under-test CPU/RAM (`docker stats`), debugging effort, custom-glue LOC.

## Shared semantics (`common_semantics.py`)
Both engines import the SAME mock agents, explicit idempotency/side-effect dedup, model/prompt/policy
provenance, asset-ref-only rule, artifact-staleness binding, and DLQ helper — so ONLY the engine
differs, never the workload (fair test).

## Decision rule (pre-wired)
- CHOOSE **Hatchet** if: all safety/durability tests pass AND no meaningful recovery/audit gap AND
  custom glue stays modest AND ops burden is materially lower.
- CHOOSE **Temporal** if: Hatchet exposes a meaningful durability/recovery/audit weakness OR needs
  enough custom glue that its simplicity advantage disappears.
- Do not score popularity/ecosystem size by itself.

Fill `RESULTS_TEMPLATE.json` from the real run; that produces the final RETURN block.
