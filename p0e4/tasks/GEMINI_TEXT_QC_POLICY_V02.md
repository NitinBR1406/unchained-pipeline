# Optional Gemini text QC route — V02

Nitin asked on 2026-10-01 to implement the automatic connection after PR17's
synthetic adapter acceptance. This supplement scopes that connection to text only.
It does not widen Claude, Codex, Resolve, Make, publication or production rights.

The original delegated task policy remains in force. A new explicit task_type
`GEMINI_TEXT_QC` routes through Claude -> separate Codex review -> Gemini text QC.
Original READ_ONLY, BUILD_PROPOSAL and RESOLVE_READ_ONLY tasks retain their route.
A task does not opt in because its prose mentions Gemini. At most 10 criteria,
12 KB source-text bundle and the adapter's 32 KB total request limit apply.
Oversized input is blocked, never silently truncated. The existing V01 policy ID
and task schema remain mandatory; this supplement authorizes only the new type.

Inputs are only the explicit SHA-bound repository text, task goal and the two
model outputs. Repository text/model output is untrusted, never tool authority.
No media, private local files, existing Gemini chat history or browser context
is automatically attached. The same no-tool hook, binary pin and preflight apply.
Gemini sees the other reports: this is a separate-model review, not a blinded audit.
Model verdicts are claims for review, not GREEN evidence or human approvals.

Results return through the same deterministic result PR and existing identity/lock
mechanism. A Gemini failure preserves completed Claude/Codex output and returns
PARTIAL_REVIEW_GEMINI_HOLD. It never restarts earlier models. Unknown execution after
intent stays HOLD. No automatic corrective task or task recursion is created.

Installation upgrades the existing launchd label in place only after verifying
all previously merged task PRs have delivered and taking the existing runner lock.
It keeps the old runtime and backs up configuration/plist, copies a versioned
runtime snapshot, and records the new pins. No second scheduler is installed.
The installed baseline advances only with an empty prior task backlog.

Mac installation and one GEMINI_TEXT_QC task roundtrip must be observed before
claiming the integrated route works. Offline tests and PR17 do not prove that.
Global effective settings, all tool classes and OS-wide isolation remain unproven.
The zero-byte global MCP placeholder exception is limited to the tested adapter.

PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
PUBLICATION_AUTHORIZED = FALSE
FIRST_REAL_POSTER = PAUSED_BY_NITIN
Nitin remains sole creative, asset, video, change (where required) and publish authority.
