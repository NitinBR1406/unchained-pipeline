# Task package — field guide (P0E4_TASK_PACKAGE_V01)

Copy `TASK_TEMPLATE.json` to `inbox/<TASK_ID>_R<revision>.json` and fill it in. This file
explains the fields. The JSON is the canonical task record; there is no second Markdown
copy of a task. Minimum contents follow "Minimale opdracht en berichten" in
`p0e4/governance/AI_ROLES_AND_COMMUNICATION_V01.md`.

| Field | Filled by | Meaning |
|---|---|---|
| `task_id`, `revision`, `parent_task_id` | creator | ID convention `<DOMAIN>_<SUBJECT>_<YYYYMMDD>_V<NN>`. Revision starts at 1. A new revision is a new file. |
| `task_type` | creator | `READ_ONLY`, `BUILD`, `REPAIR` or `VERIFICATION`. Anything other than `READ_ONLY` counts as build work and needs NITIN_APPROVAL. |
| `status` | lifecycle | Governance labels: `DRAFT`, `READY`, `SENT`, `ACKNOWLEDGED`, `RUNNING`, `BUILT`, `IN_REVIEW`, `REPAIR_REQUIRED`, `BLOCKED`, `WAITING_FOR_NITIN`, `REVIEWED_READY_FOR_NITIN`. For closed tasks also `REJECTED`, `WITHDRAWN` or `SUPERSEDED`. |
| `created_by`, `created_at_utc` | creator | Creator and role (ChatGPT/orchestrator, Work/Codex/technical verifier, Nitin/owner). UTC date and time. |
| `goal` | creator | One observable outcome. |
| `scope` | creator | What is in and out of scope. Exact Resolve project/timeline identity. Whether an isolated copy is required. |
| `limits_and_forbidden_actions` | creator | Explicit limits. The standard lines stay; add task-specific ones. |
| `required_rights` | creator | MCP tools, pinned probes, render yes/no, write paths. If `within_current_settings` is false, the task is blocked until a separate NITIN_CHANGE_APPROVAL and a reviewed settings change exist. |
| `inputs` | creator | Base commit, Master State reference with SHA256, source files with SHA256. |
| `acceptance_criteria` | creator | Checkable criteria with a method and the person who checks. Never weakened in order to pass. |
| `evidence` | creator | Evidence path `p0e4/evidence/<task_id_lowercase>/` and the required proof. Never secrets. |
| `reviewers`, `human_gates`, `budget` | creator | Review roles; separate Nitin gates (such as creative or final approval), which this task never implies; render/attempt budget. |
| `nitin_approval` | **Nitin only** (or verbatim-recorded) | `NITIN_APPROVAL: true` plus `granted_at_local`, `covers_task_id`/`covers_revision`, verbatim quote and source. Without it, no build work. Claude Code never writes this block. |
| `claude_code.ack` | Claude Code | Session ID, client version, the verbatim start instruction, precondition results. |
| `claude_code.result` | Claude Code | Outputs with SHA256, readback of actual settings, self-check per AC (`PROVEN` / `NOT_PROVEN` / `FAILED`), defects, limitations, evidence manifest. |
| `codex_verification` | Work/Codex | Status and links to `REVIEW_RESULT` files (`REVIEW_RESULT_TEMPLATE.json`). |
| `events` | everyone, append-only | One entry per message (REQUEST, ACK, PROGRESS, RESULT, DEFECT, BLOCKED, REVIEW_RESULT) with UTC timestamp and artifact references. |
| `governance` | fixed | Deployment and publication false; First Real Poster paused. |

Examples: see `examples/`. Those files are marked EXAMPLE and are never executed.
