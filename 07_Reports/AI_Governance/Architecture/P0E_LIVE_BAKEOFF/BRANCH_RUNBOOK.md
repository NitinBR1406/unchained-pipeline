# P0-E Live Bake-Off — Branch & Trigger Runbook (GitHub Actions)

> I cannot push to GitHub or trigger Actions from the Cowork environment (no GitHub connector, the
> connected folder is not a git checkout, and there is no outbound network). These are the exact steps to
> run it on an ephemeral `ubuntu-latest` runner. When the run finishes, attach the `p0e-live-bakeoff-
> evidence` artifact (or paste the six evidence JSON/MD files) and I will produce the final decision.

## 1. Put the harness in the GitHub repo (authoritative source of truth)
The files live at `07_Reports/AI_Governance/Architecture/P0E_LIVE_BAKEOFF/`. Copy the CI workflow to the
standard path and create the isolated branch:
```
git checkout -b p0e/live-control-plane-bakeoff
mkdir -p .github/workflows
cp 07_Reports/AI_Governance/Architecture/P0E_LIVE_BAKEOFF/ci/p0e-live-bakeoff.yml .github/workflows/
git add 07_Reports/AI_Governance/Architecture/P0E_LIVE_BAKEOFF .github/workflows/p0e-live-bakeoff.yml
git commit -m "P0-E: live Temporal-vs-Hatchet bake-off harness (disposable, no prod secrets)"
git push -u origin p0e/live-control-plane-bakeoff
```
## 2. Trigger
- Auto: the push to `p0e/live-control-plane-bakeoff` starts it, OR
- Manual: GitHub → Actions → "p0e-live-bakeoff" → Run workflow (workflow_dispatch).

## 3. Safety (enforced by design)
- Do NOT add production publishing secrets to this repo/branch/workflow. The harness needs none.
- No REAL P1 / 177455 / Render verifier / Make / social creds / approvals / grants / Aakhri Ishq.
- Disposable infra only; every job ends with `docker compose down -v` + a teardown verification step.
- Do not merge to `main`; this branch is for evidence only.

## 4. What the run produces (uploaded as artifact `p0e-live-bakeoff-evidence/`)
`P0E_LIVE_BAKEOFF_RESULTS_V01.json`, `P0E_TEMPORAL_LIVE_EVIDENCE_V01.json`,
`P0E_HATCHET_LIVE_EVIDENCE_V01.json`, `P0E_LIVE_FAILURE_MATRIX_V01.json`,
`P0E_LIVE_RESOURCE_METRICS_V01.json`, `P0E_LIVE_FINAL_DECISION_V01.md`, plus `run_meta.json`,
`*_versions.json` (image digests), `*_stats.log` (CPU/RAM), `EVIDENCE_SHA256SUMS.txt`. Every result is
labelled OBSERVED / SIMULATED / NOT_TESTABLE — no simulation is presented as live.

## 5. Notes / likely tuning on first run
- `hatchet-lite` token bootstrap: the workflow runs `hatchet-admin token create`; confirm the exact
  admin command/tenant-id for the pinned hatchet-lite version and adjust if the CLI differs.
- Pin exact image digests once known (compose files have TODO tags) — digests are also captured to
  `*_versions.json` at run time.
- If any required test lands NOT_TESTABLE (e.g., token/health race), re-run; `controller.py assemble`
  keeps the decision PENDING until the required tests are OBSERVED (it will not fabricate a pass).

## 6. Hand back
Attach the artifact or paste the six files here. I will compute the final RETURN block and the
architecture-approval recommendation (still stopping before any production deployment).
