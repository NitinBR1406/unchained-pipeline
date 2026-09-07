# Zero-Terminal Production — One-Time Setup (V1.1)

Architecture: **GitHub Actions** (see DECISION_MATRIX.md). After this one-time setup, the routine
flow is approvals only — no Terminal, curl, key copy, polling, download or ffprobe by Nitin.

## One-time setup (≤ 3 actions)
1. **Push this repo to GitHub** (private).
2. **Add the encrypted secret** `SHOTSTACK_PRODUCTION_API_KEY` in
   Settings → Secrets and variables → Actions → New repository secret. (Rotate the key that was
   shared in chat and paste the new value here — entered once, never again.)
3. **Enable Actions** for the repo (and, if using auto-trigger, add a `PIPELINE_DISPATCH_TOKEN`
   fine-grained PAT secret so the approval step can fire `repository_dispatch`).

## Routine flow after setup
- Nitin **CREATIVE APPROVE** → the approval step emits `repository_dispatch: production-render`
  (or Nitin taps *Run workflow* in the GitHub mobile app / web UI for `workflow_dispatch`).
- GitHub Actions runs `prod_executor_entry.py`:
  submit → poll → download → SHA → register → tech QC → advance state, using the encrypted secret.
- Artifacts (master mp4, reports, updated state) are uploaded to the run and committed back.
- Nitin is notified only with actionable status ("passed technical QC — final video review ready"
  or "held automatically").

## Trigger the render
- Manual: GitHub → Actions → **production-render** → *Run workflow* → pick `campaign_id`.
- Automatic (recommended): the creative-approval integration sends
  `POST /repos/<owner>/<repo>/dispatches {"event_type":"production-render",
  "client_payload":{"campaign_id":"<id>"}}` with the dispatch token. This is emitted by the
  approval action, not typed by Nitin.

## Honest status
- The executor, job queue, idempotency, retry, env-safety and tech-QC chaining are
  **IMPLEMENTED + TESTED** (25/25 tests) with a fake backend (no paid renders).
- Making it live is **IMPLEMENTED_REQUIRES_ONE_TIME_DEPLOYMENT**: push repo + add secret + enable.
- Until deployed, production can still be run with the local runner (V1 path). This environment
  itself cannot reach the Shotstack API (proxy), which is exactly why execution is delegated to
  GitHub Actions.
