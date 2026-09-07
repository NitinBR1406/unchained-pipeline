# Capability Matrix — Unchained Nitin Autonomous Media Pipeline V1

Classification legend:
- **IMPL+TESTED** — implemented and covered by passing tests / acceptance.
- **IMPL (not e2e)** — implemented, not exercised end-to-end against the live external system.
- **ADAPTER** — interface ready; real external connection required to actually run.
- **DESIGNED** — designed, not implemented.
- **BLOCKED** — cannot run in this environment.

| Capability | Status | Notes |
|---|---|---|
| SOURCE INGESTION | IMPL (not e2e) | manifest-driven source registration + SHA; binary lives on Drive/GCS. |
| CAMPAIGN STATE MACHINE | IMPL+TESTED | deterministic transitions; illegal transitions rejected. |
| APPROVAL SYSTEM (3 gates) | IMPL+TESTED | SHA-bound; hash change invalidates approval; separate gates enforced. |
| SANDBOX PREVIEW | IMPL (not e2e) | proven manually via Shotstack MCP (stage); not yet wired into orchestrator run. |
| GEMINI REVIEW ADAPTER | ADAPTER | targeted-review interface; not connected here. |
| FROZEN JSON CONTRACT | IMPL+TESTED | master mode rejects output.range; SHA recorded. |
| PRODUCTION RENDER | IMPL / BLOCKED-here | runner wrapper complete; API unreachable from this env (proxy 403) → local run. |
| PRODUCTION EXECUTOR (V1.1) | IMPL+TESTED / needs 1-time deploy | event-driven executor + job queue; runs on GitHub Actions after creative approval; tested with fake backend (no paid renders). |
| ZERO-TERMINAL TRIGGER (V1.1) | IMPL, requires deployment | creative approval auto-queues job; GH Actions workflow runs executor with encrypted secret. |
| IDEMPOTENCY (renders) (V1.1) | IMPL+TESTED | job idempotency key (campaign+frozenSHA+profile); no duplicate paid renders; DONE job not re-run. |
| AUTO RETRY (V1.1) | IMPL+TESTED | bounded backoff on transient (429/5xx/timeout); material errors → HOLD. |
| APPROVAL AUTO-DISPATCH (V1.1.1) | IMPL+TESTED | creative APPROVE fires repository_dispatch; REJECT never does; SHA-bound; idempotent; auth-fail→HOLD; transient→retry→HOLD. Tested with mock (no network/paid render). |
| DISPATCH TOKEN (V1.1.1) | needs 1-time deploy | least-privilege fine-grained PAT (Actions:write, single repo) as GITHUB_DISPATCH_TOKEN, server-side. |
| ONE-TAP MOBILE APPROVAL (V1.1.2) | IMPL+TESTED / needs 1-time host | signed-link approval service: mobile APPROVE/REJECT → authoritative SHA-bound record → auto-dispatch. Reusable for all 3 gates. Server-side secrets, single-use links, idempotent, authorized. Tested with mock (12 tests). Needs the tiny service hosted once. |
| APPROVAL SERVICE HARDENING (V1.1.3) | IMPL+TESTED (real HTTP) | health endpoint, request-size cap, per-IP rate limit, security headers, secret-safe logging, disk-persisted single-use nonce (survives restart), dry-dispatch smoke mode. 11/11 live HTTP smoke over a running server. |
| PUBLIC HTTPS DEPLOY (V1.1.3) | REQUIRES 1-TIME HOST (your account) | Dockerfile + render.yaml blueprint ready; needs your Render/Fly/Railway login to get a public phone URL. Cannot be created from the build env. |
| PRODUCTION SECRET MGMT | IMPL+TESTED | env-var only; never printed/stored; missing-secret → safe HOLD. |
| AUTO POLLING | IMPL | in shotstack_production_render.sh (poll until done/failed/timeout). |
| AUTO DOWNLOAD | IMPL | runner downloads MP4 to production-renders/<id>/. |
| AUTO TECH QC | IMPL+TESTED | ffprobe wrapper; duration/geometry/fps/audio gates; missing tool → HOLD. |
| AUTO HASHING | IMPL+TESTED | SHA-256 on frozen JSON + master MP4 (registry + runner). |
| DRIVE ROUTING | DESIGNED | generic path plan documented; no destructive reorg; connector needed. |
| DERIVATIVE ENGINE | ADAPTER | plan generated for 7 targets; real ffmpeg cuts need connected engine + master binary. |
| PACKAGING ENGINE | ADAPTER | per-platform metadata records (not identical copy); fields to be filled. |
| RIGHTS GATE | IMPL+TESTED | RIGHTS_PASS required; AKI = RIGHTS_HOLD blocks publish. |
| PUBLISH GATE | IMPL+TESTED | requires final-video + publish approval + rights pass. |
| YOUTUBE PUBLISH ADAPTER | ADAPTER | not connected. |
| INSTAGRAM PUBLISH ADAPTER | ADAPTER | not connected. |
| FACEBOOK PUBLISH ADAPTER | ADAPTER | not connected. |
| TIKTOK PUBLISH ADAPTER | ADAPTER | not connected. |
| ANALYTICS | ADAPTER | 24h/72h/7d/14d/28d windows defined; not connected. |
| NOTIFICATIONS | IMPL+TESTED | actionable-only (approve/reject/hold); routine chatter suppressed. |
| AUDIT LOG | IMPL+TESTED | append-only JSONL; secrets redacted. |
| PARALLEL CAMPAIGNS | IMPL+TESTED | per-campaign isolated state dir; no global lock file. |
| RETRY / IDEMPOTENCY | IMPL+TESTED | publish op ledger prevents duplicate posts; material errors → HOLD (no blind retry). |

## Final flags
- AAKHRI_ISHQ_ACCEPTANCE_TEST = PASS
- CURRENT_AKI_STATE = AWAITING_PUBLISH_APPROVAL (video approved, publish false, rights hold)
- NITIN_TERMINAL_REQUIRED_NORMAL_FLOW = YES (only for the production render step, until the Shotstack
  production API is reachable from a hosted runner or a connector is added)
- NITIN_API_KEY_HANDLING_REQUIRED_NORMAL_FLOW = YES (one-time env-var export; never per-render in prompts)
- NITIN_MANUAL_RENDERING_REQUIRED = NO (runner automates submit/poll/download; Nitin only launches it)
- NITIN_MANUAL_POLLING_REQUIRED = NO
- NITIN_MANUAL_DERIVATIVE_EDITING_REQUIRED = NO (engine plans; real cuts need connected ffmpeg engine)

## Remaining automation debt (top 3)
1. **Hosted production execution** — move `shotstack_production_render.sh` to a hosted runner (or a
   Shotstack production connector) so the render step needs no local Terminal. Today: proxy blocks it here.
2. **Connect derivative/packaging/publish/analytics adapters** — wire real ffmpeg cutting + platform APIs
   (YouTube/IG/FB/TikTok) + analytics pulls.
3. **Preview + Gemini review inside the orchestrator** — wire SANDBOX_PREVIEW and targeted Gemini QC into
   `advance()` so the pre-creative-approval leg is automated too.
