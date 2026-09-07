# V1.1.1 — Approval → Automatic Production Trigger

Creative APPROVE now fires the render itself. On a valid approval the orchestrator:
validate approval → SHA binding → campaign state → frozen JSON → idempotency → **dispatch** the
`production-render` workflow via GitHub `repository_dispatch`. Nitin never opens the Actions UI,
never clicks Run workflow, never types a campaign_id.

Guards (all tested with a mock dispatcher — no network, no paid render):
- REJECT never dispatches.
- Approval is SHA-bound; if the frozen JSON SHA changes, no render → HOLD.
- An existing DONE or in-progress job for `campaign_id + frozen_sha + profile` suppresses dispatch
  (no duplicate paid renders). Aakhri Ishq (already rendered) therefore never re-renders.
- Dispatch auth failure → HOLD (approval preserved). Transient failure → bounded retry, then HOLD.
- Secrets never logged/persisted.

## Least-privilege token (one-time, server-side)
The dispatch needs a token where approvals run — NOT in any client UI.
1. Create a **fine-grained PAT**: Settings → Developer settings → Fine-grained tokens.
   - Repository access: only `NitinBR1406/unchained-pipeline`.
   - Permissions: **Actions: Read and write** (that's all).
2. Store it as env var `GITHUB_DISPATCH_TOKEN` in the environment that runs the approval step
   (a small server/worker, or a secret manager). Never commit it, never put it in a client app.

```python
from unpipe.orchestrator import Campaign
from unpipe.dispatcher import GitHubDispatcher
disp = GitHubDispatcher(owner="NitinBR1406", repo="unchained-pipeline")  # reads GITHUB_DISPATCH_TOKEN
c = Campaign(workdir, manifest, dispatcher=disp)
c.approve("NITIN_CREATIVE_APPROVAL", asset_id, frozen_sha)   # -> auto-dispatch
```

If `dispatcher=None` (default), approval still queues the job but does not call out — a safe dry mode.

## Recovery only
`workflow_dispatch` stays on the workflow for admin/recovery (manual Run from the GitHub UI).
It is NOT part of Nitin's normal flow.

## Honest remaining gap
The dispatch (system side) is fully automated and tested. The one remaining routine touch is the
**approval input surface**: something must call `c.approve(...)`. Options, cheapest first:
1. **GitHub Environment required reviewer** on the render job — Nitin taps *Approve* in the GitHub
   mobile app on the waiting run (native, no terminal, no app to build). Recommended interim.
2. A minimal approval web/app that calls `approve()` server-side (removes GitHub entirely from the
   routine).
Until one of these is wired, approval is invoked via the CLI (`python -m unpipe.cli approve …`),
which is a terminal action. That is the only remaining automation debt.
