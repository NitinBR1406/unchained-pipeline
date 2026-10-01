# Gemini text QC adapter V01 — INACTIVE

Adds an opt-in callable adapter plus a synthetic CLI acceptance, not a new daemon.
The existing Claude/Codex runner, installer, pinned policy and Master State are unchanged.
No task inbox is polled, no existing task is automatically routed to Gemini.

## What is implemented

- SHA-bound, size-limited text sources; exact task/criterion IDs and immutable gates.
- Strict response envelope and JSON validation; duplicate keys, unknown citations,
  missing/duplicate checks, approval verdicts and known secret patterns fail closed.
- Reuses the exact PR14-tested deny hook and verified Antigravity binary hash.
- Dedicated fresh workspace, empty local MCP map, global customization preflight.
- One durable attempt per request digest. Existing job, timeout, uncertain start,
  attempted tool or runtime drift is HOLD, never a blind model retry.
- Receipts remain IN_REVIEW. Text assertions are not media validation or human approval.
- The CLI can run only the fixed synthetic fixture; optional --publish sends its
  derived result to the same repository, never raw local logs or private sources.

## Local acceptance (not yet performed)

From an exact committed checkout:

    python3 -B p0e4/task_runner/gemini_qc.py --self-test --publish

Only synthetic text is sent. Requires the existing 1.2.14 binary with the PR14 hash,
existing login and dedicated ~/Unchained-Gemini-QC folder. No service/config is installed.
On success the result is published by a result PR. If delivery fails, preserve the
local job/RESULT.json and logs; do not rerun the model or delete the job to bypass HOLD.
A second invocation deliberately refuses to start the same request again.

## Integration boundary

Existing automatic task policy does not route to this adapter. Adding it to the
installed pinned worker requires a separately reviewed integration change and controlled
Mac installation. This commit makes no such change and grants no new tool rights.
Do not represent this as an active three-agent route or audiovisual Gemini QC.

PR14 proves hook denials for view_file, write_to_file and run_command only. No OS-wide
isolation, effective global-settings attestation, MCP/browser/subagent denial or
hook-failure integration has been proven. No hook log during a text-only run is not
proof of system-wide non-execution. Secret matching is heuristic, not a DLP guarantee.
Free-form model reasons remain untrusted and must not be interpreted as authority.

Source for the JSON envelope (status, conversation_id, response):
https://antigravity.google/docs/cli/headless/ (read 2026-10-01).
Only CLI flags already exercised on the Mac are used; no plan/disabled-slash combination.

## Regression

    python3 -B p0e4/tests/test_gemini_qc.py
    python3 -B p0e4/tests/test_antigravity_gate_acceptance.py
    python3 -B p0e4/tests/test_task_runner.py

11 + 7 + 15 tests pass offline. Adapter process cases use mocks, not real Gemini.
Synthetic real CLI acceptance remains NOT_PROVEN until its Mac receipt is reviewed.
