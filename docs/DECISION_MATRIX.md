# V1.1 Execution Architecture — Decision Matrix

Goal: after CREATIVE_APPROVAL, production render runs with **zero routine Terminal**. Pick the
simplest option that genuinely removes routine terminal use (not the most elegant).

| Option | Zero routine terminal | Secret storage | No laptop dependency | Cost | Setup complexity | Auditable | Recovery |
|---|---|---|---|---|---|---|---|
| A. Hosted always-on worker (VPS) | Yes | env / secret file | Yes | $ monthly | Medium (provision, patch) | Yes | Medium |
| B. Serverless function/job (Lambda/Cloud Run job) | Yes | cloud secret mgr | Yes | ~free at this volume | Medium (IAM, packaging) | Yes | Good |
| **C. GitHub Actions (CI runner)** | **Yes** | **encrypted repo/env secret** | **Yes** | **free tier ample** | **Low (push repo + add secret)** | **Yes (run logs + artifacts)** | **Excellent (re-run job)** |
| D. Local launch agent (launchd) | Yes*, but laptop must be on | Keychain/env | No | free | Low | Weak | Manual |
| E. Existing connected env | n/a | n/a | — | — | — | — | — (no suitable always-on exec here) |

Notes:
- D depends on the laptop being on/awake → fails the "no permanent laptop dependency" preference.
- B is excellent but adds IAM + packaging overhead for a single low-frequency job.
- E: this Cowork environment cannot reach the Shotstack API (proxy) and is not an always-on executor.

## Decision: **Option C — GitHub Actions**
Simplest path that truly eliminates routine terminal: the render runs on GitHub's runner, triggered by
an event (`workflow_dispatch` / `repository_dispatch`) that the creative-approval step emits. The
production API key lives as an encrypted GitHub Actions secret entered **once**. Runs are logged and
artifacts uploaded, so it is auditable and trivially re-runnable. No laptop needs to stay on.

One-time setup (≤3 actions): (1) push this repo to GitHub, (2) add `SHOTSTACK_PRODUCTION_API_KEY`
(and a dispatch token) as encrypted secrets, (3) enable the workflow. After that, routine flow =
approvals only.

Portability: the executor is backend-agnostic (`HttpProductionBackend`), so the same code can move to
Option B later with no logic change — only the trigger/host differs.
