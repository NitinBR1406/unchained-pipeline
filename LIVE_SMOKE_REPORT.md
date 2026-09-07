# Live HTTP smoke (localhost, dry dispatch) — 2026-09-07T19:58:31Z
PASS  1_health
PASS  2_page_loads
PASS  3_approve
PASS  4_dispatch_fired
PASS  5_replay_idempotent
PASS  6_expired_rejected
PASS  7_tampered_rejected
PASS  8_unauthorized_rejected
PASS  9_reject_no_dispatch
PASS  10_replay_after_restart
PASS  11_secrets_absent

NOTE: real HTTP over a running server socket with restart-persistence. This is NOT a
public phone HTTPS URL — that requires hosting on your cloud account (see DEPLOY_HOSTING.md).
LIVE_HTTP_SMOKE = PASS
