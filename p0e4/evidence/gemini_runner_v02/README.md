# Optional Gemini text review in the existing task runner — V02

Implementation is ready for controlled Mac installation and one real task roundtrip.
It is NOT yet live-accepted. PR17 proved only the standalone synthetic adapter.

The new runner_gemini.py entrypoint calls the unchanged V01 worker for ordinary
tasks. Only explicit GEMINI_TEXT_QC tasks add the separate Gemini text review.
Result is IN_REVIEW or PARTIAL_REVIEW_GEMINI_HOLD, never approval or production GREEN.
Already completed Claude/Codex outputs remain available if Gemini fails.

## Controlled upgrade

Use an exact clean merged repository checkout (sparse checkout is supported):

    python3 -B p0e4/task_runner/upgrade_gemini.py --repo "$PWD" --activate-gemini-text-qc

The installer requires the existing service, existing identity and unchanged old
pins/runtime. It stops before changes if the worker lock is busy or any prior
merged inbox task lacks delivered.json. Do not remove job state to force an upgrade.
It backs up config/plist, copies a versioned runtime, reuses the SAME launchd label,
and preserves all prior task identities and results. The install baseline advances
only after the prior backlog is verified delivered. Failure during activation restores
old config/plist and attempts to restart the old service; old runtime remains intact.

Expected output: INSTALLED_INTEGRATED_ROUTE_UNPROVEN. Then offer ONE small task of
type GEMINI_TEXT_QC in a one-file inbox PR, using the existing task schema/policy,
<=10 criteria and <=12 KB input bundle. Do not queue this type before the upgrade:
the old worker correctly rejects it. Observe Claude session, Codex review, Gemini
conversation ID and result PR. Re-poll must not restart the task. No new scheduler.

## Evidence limits

10 new tests + 13 adapter + 7 gate + 15 old runner tests = 45 offline tests.
Processes/launchd/remote operations in tests are mocked; actual three-stage task
execution and actual Mac upgrade/rollback are NOT_PROVEN until observed.
Neither text review nor successful transport proves audiovisual quality.
Global effective-settings/OS-wide isolation limits from the prior adapter still apply.

Production/publication stay false, First Real Poster stays paused. No Resolve tools,
Make, public posting, media edits, or final creative approval are introduced.
The master pointer is not modified. This is subordinate implementation evidence.
