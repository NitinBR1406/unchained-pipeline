# V1.1.3 — Hosting Decision + Deploy Guide

## Hosting comparison
| Platform | Public HTTPS/TLS | Encrypted secrets | Persistent disk | GitHub outbound | Sleep behavior | Complexity | Cost/mo | Logs |
|---|---|---|---|---|---|---|---|---|
| **Render (Starter web)** | ✅ auto TLS | ✅ dashboard | ✅ 1GB disk | ✅ | none on Starter | Low (Blueprint) | ~$7 | ✅ |
| Render (Free web) | ✅ | ✅ | ⚠️ no disk + cold sleep | ✅ | sleeps → slow first tap, loses ephemeral state | Low | $0 | ✅ |
| Fly.io | ✅ | ✅ | ✅ volume | ✅ | can scale-to-zero | Medium (flyctl) | ~$0–5 | ✅ |
| Railway | ✅ | ✅ | ✅ | ✅ | none | Low–Med | ~$5 | ✅ |
| Cloud Run | ✅ | ✅ (Secret Mgr) | ⚠️ needs GCS/DB for state | ✅ | scale-to-zero cold start | Medium | ~$0–3 | ✅ |

## Decision: **Render Starter web service** (`render.yaml` blueprint included)
Simplest reliable path: one Blueprint deploy, automatic HTTPS, a 1GB **persistent disk** for the
single-use nonce store (so replay protection survives restarts), and no cold-sleep so a tap is
instant. Free tier is avoided only because its cold-sleep + ephemeral disk materially weaken
reliability and replay-persistence. Everything is portable (plain Docker + stdlib) — Fly/Railway/
Cloud Run work with the same image if you prefer.

## One-time deploy (≈5 min, no terminal after this)
1. Repo is already on GitHub (`NitinBR1406/unchained-pipeline`). It now contains `Dockerfile` +
   `render.yaml`.
2. Render → New → **Blueprint** → select the repo → apply. It creates the web service + disk.
3. In the service **Environment**, set the two secrets (prompted, `sync:false`):
   - `APPROVAL_SIGNING_SECRET` = a long random string (e.g. `openssl rand -hex 32`)
   - `GITHUB_DISPATCH_TOKEN` = fine-grained PAT, **Actions: Read and write on this repo only**
4. Deploy. Your URL is `https://unchained-approval.onrender.com` (health: `/healthz`).

## Producing an approval link (the notification mechanism)
The notification layer calls `make_approval_link.create_link(...)` server-side and sends Nitin the
URL. Manually, once, to verify:
`python3 make_approval_link.py campaigns aakhri-ishq creative https://unchained-approval.onrender.com`
(For a live phone smoke, use the dry Cover-2 campaign, not Aakhri Ishq — do not re-trigger AKI.)

## Hardening in place (verified by run_live_smoke.py, 11/11 over real HTTP)
health endpoint (no state) · request-size cap (16KB) · per-IP rate limit (30/min) · security headers ·
secret-safe logging (no query/body/secret logging) · constant-time HMAC check · expiring links ·
single-use nonce persisted to disk (survives restart) · SHA re-check at tap time · rejects malformed/
expired/replayed/unauthorized · no credentials in URL · TLS provided by the host.

## Honest status
The service is hardened and proven over real HTTP locally (incl. restart-persistence). The remaining
step — a **public phone-accessible HTTPS URL** — requires deploying to your Render (or equivalent)
account, which needs your login; it cannot be created from the build environment. After you apply the
Blueprint + set the two secrets, ping me and I'll generate the first real approval link and we verify
from your phone.
