# V1.1.2 — Approval Surface Decision

Goal: one artist-facing tap (APPROVE/REJECT) on the phone that produces the **authoritative,
SHA-bound pipeline approval record** and triggers the existing auto-dispatch — with no second human
gate.

| Option | One authoritative SHA-bound record | One tap (no 2nd gate) | Mobile | Server-side secret | Reusable for 3 gates | Infra |
|---|---|---|---|---|---|---|
| A. GitHub Environment required-reviewer | ❌ produces a GitHub *deployment* approval, not our campaign/SHA record; happens AFTER dispatch → a second, disconnected gate | ❌ (creative approve + deploy approve) | ✅ (GitHub app) | ✅ | ⚠️ deployment-only, not our model | none |
| **B. Minimal signed-link approval service** | ✅ calls `orchestrator.approve()` → our exact record | ✅ single tap = the record + dispatch | ✅ mobile HTML | ✅ (dispatch + signing secret stay server-side) | ✅ same `decide(gate,…)` for all 3 gates | tiny stdlib http service |
| C. GitHub Issue checkbox + Action | ⚠️ possible but brittle parsing; identity/replay harder | ⚠️ | ✅ | ✅ | ⚠️ | Action wiring |

## Decision: **Option B — minimal signed-link approval service**
Option A is rejected exactly as the brief warns: it creates a second approval concept
(GitHub deployment approval) disconnected from our campaign/artifact/SHA model, and it lands *after*
dispatch → a double gate. Option C is fragile. Option B is a ~single-file stdlib service: it renders
a mobile page with APPROVE/REJECT, and on tap records the authoritative SHA-bound approval via the
existing `Campaign.approve()` (which already auto-dispatches for creative). The same `decide()` path
serves all three gates with different downstream consequences.

Design:
- **Capability link**: an HMAC-signed, expiring, single-use token encodes
  `{campaign_id, gate, asset_id, sha, exp, nonce}`. The client only ever holds this opaque token —
  never a GitHub PAT, Shotstack key, or the signing secret.
- **Auth**: approver must be in a server-side allowlist; identity is recorded as `approved_by`.
- **Replay/double-tap**: nonce is single-use (consumed store); a repeat returns the cached decision,
  no second render. Production idempotency (campaign+sha+profile) is the backstop.
- **SHA re-check at tap time**: if the current frozen SHA no longer matches the token SHA →
  REAPPROVAL_REQUIRED / HOLD, no dispatch.
- **Deployment**: `approval_service.py` (pure logic, unit-tested) + `approval_server.py` (thin
  stdlib `http.server` wrapper) run on the same minimal server that already holds
  `GITHUB_DISPATCH_TOKEN`. No web framework, reusable for gates 1–3.
