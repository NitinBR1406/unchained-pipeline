# P0-E4 task inbox

## Actuele automatische route

Nitin heeft PR-merge door ChatGPT/Codex gedelegeerd. Gebruik voor de nieuwe route
[`AUTOMATION_POLICY_V01.md`](AUTOMATION_POLICY_V01.md) en
`AUTOMATED_TASK_TEMPLATE_V01.json`. Deze policy vervangt de onderstaande historische
handmatige startregels uitsluitend voor het nieuwe schema. De bestaande V01-taken
blijven handmatig en worden door de runner geweigerd.

## Historisch V01-contract (handmatige taken)

One fixed place where ChatGPT (orchestrator) and Work/Codex (technical verification) put
task packages and findings for the local Claude Code builder. The inbox implements the
task and message contract in
[`p0e4/governance/AI_ROLES_AND_COMMUNICATION_V01.md`](../governance/AI_ROLES_AND_COMMUNICATION_V01.md).
It does not replace that contract. Field names, message types (REQUEST, ACK, PROGRESS,
RESULT, DEFECT, BLOCKED, REVIEW_RESULT) and status labels come from there.

## What this inbox is not

- **Not Master State.** Task files are coordination records. Anything that changes
  project state still goes through the append-only ledger/reducer. Nobody edits the
  Master State pointer directly.
- **Not the Codex controller queue.** `p0e4/controller/READY_TASKS_V01.json` is the
  immutable seed of the existing `codex exec` controller, with its own narrow read-only
  or fixture scope. Tasks here are never fed to that controller. The controller never
  reads this folder.
- **Not evidence storage.** Evidence stays in `p0e4/evidence/<task_id_lowercase>/`,
  following the existing per-work-package convention with a `SHA256SUMS.txt`. The task
  file only points to it.
- **Not an automatic trigger.** See "No autonomous triggers" below.

## Layout

```
p0e4/tasks/
  README.md                     this file: lifecycle and rules
  TASK_TEMPLATE.md              field guide for task packages
  TASK_TEMPLATE.json            copy this to create a task
  REVIEW_RESULT_TEMPLATE.json   Codex verification report / finding (REVIEW_RESULT)
  inbox/                        DRAFT or READY; waiting for Nitin to start it
  active/                       started by Nitin; ACKNOWLEDGED .. IN_REVIEW / REPAIR_REQUIRED / BLOCKED / WAITING_FOR_NITIN
  done/                         REVIEWED_READY_FOR_NITIN, or closed after Nitin's decision
  rejected/                     rejected, withdrawn or superseded (never deleted)
  examples/                     EXAMPLE tasks only; never executed
```

## Naming

- Task ID: `<DOMAIN>_<SUBJECT>_<YYYYMMDD>_V<NN>`, UPPER_SNAKE_CASE. This matches existing
  IDs such as `CLAUDE_CODE_READONLY_ACCEPTANCE_20260930_V01`. Example:
  `RESOLVE_CAPTION_LOGO_OFFSET_20261001_V01`.
- File name: `<TASK_ID>_R<revision>.json`, for example
  `RESOLVE_CAPTION_LOGO_OFFSET_20261001_V01_R1.json`.
- A change to goal, scope, limits, rights, inputs or acceptance criteria is a new
  revision in a new file. The old revision moves to `rejected/` with status
  `SUPERSEDED`. Dedup key: `task_id` + `revision` + input SHA256 set.
- Codex reports: `<TASK_ID>_R<revision>_REVIEW_<NN>.json`, stored next to the task file.

## Lifecycle

| Step | Who | Folder | Status (governance label) |
|---|---|---|---|
| 1. Create the package from `TASK_TEMPLATE.json` | ChatGPT (or Codex for a verification task) | `inbox/` | `DRAFT` |
| 2. Complete it within the authorised scope | ChatGPT | `inbox/` | `READY` |
| 3. Approve build work: fill `nitin_approval` | Nitin (or ChatGPT recording Nitin's verbatim words, with source) | `inbox/` | `READY` |
| 4. Start a session: *"Voer taak `<TASK_ID>` uit volgens `p0e4/tasks/inbox/<file>`"* | Nitin | — | `SENT` |
| 5. Check preconditions, `git mv` to `active/`, write `claude_code.ack` | Claude Code | `active/` | `ACKNOWLEDGED` → `RUNNING` |
| 6. Execute; write evidence; fill `claude_code.result` | Claude Code | `active/` | `BUILT` or `BLOCKED` |
| 7. Verify; add a REVIEW_RESULT file; fill `codex_verification` | Work/Codex (Gemini separately for media) | `active/` | `IN_REVIEW` → `REVIEWED_READY_FOR_NITIN` or `REPAIR_REQUIRED` |
| 8. Repair loop (same task, new `events` entries) or a new revision | ChatGPT / Claude Code | `active/` | `REPAIR_REQUIRED` → `RUNNING` → `BUILT` → `IN_REVIEW` |
| 9. Close | ChatGPT after Nitin's decision | `done/` or `rejected/` | as recorded |

Each status change appends one entry to the task's `events` array: `event_id`,
`message_type`, sender, UTC timestamp, artifact references. Existing entries are never
edited or removed. Folder moves use `git mv`, so history is preserved.

## Execution rules for Claude Code

Claude Code starts a task only when **all** of the following hold:

1. Nitin started the session with the explicit instruction
   *"Voer taak `<TASK_ID>` uit volgens `<path>`"*, and the path and task ID match the file.
2. The file is in `p0e4/tasks/inbox/` with status `READY`, or it is a repair re-entry
   in `active/` with status `REPAIR_REQUIRED`.
3. For any build work, meaning anything beyond read-only inspection:
   `nitin_approval.NITIN_APPROVAL == true` with a date, the source of Nitin's words and a
   scope that covers this revision. **Without NITIN_APPROVAL there is no build work.**
   Read-only tasks can run without it. Their `task_type` must then be `READ_ONLY`.
4. Base commit, Master State reference, input SHA256 values and project/timeline
   identity all verify. The requested rights are within the technical limits in
   `.claude/settings.json`. The task file cannot widen those limits. Widening them
   needs a separate NITIN_CHANGE_APPROVAL and a reviewed configuration change.
5. No other ACK or RUNNING entry exists for the same dedup key. One writer per Resolve
   project or candidate.

If any check fails, Claude Code writes a `BLOCKED` event naming the concrete missing
item and stops. It never fills or changes `nitin_approval`. It never marks its own work
as independently verified.

## No autonomous triggers — a deliberate choice

There are no watchers, cron jobs, hooks, scheduled tasks or `claude -p` automation on
this folder. Claude Code does not poll the inbox and does not start tasks by itself.
Every execution begins with a session that Nitin starts himself. The reasons:

- The governance contract keeps Nitin as the only human approval authority. An
  automatic start would turn a file commit by another AI into an execution
  authorisation.
- Autostart and duplicate suppression are not yet proven for Claude Code (see
  `p0e4/evidence/claude_code_local_builder_setup_v02/ACCEPTANCE_RESULT_V01.json`).
- The heartbeat change still needs a separate NITIN_CHANGE_APPROVAL.

Adding any automation later is a separate task with its own approval and acceptance
evidence.

## Unchanged limits

`PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE` · `PUBLICATION_AUTHORIZED = FALSE` ·
`FIRST_REAL_POSTER = PAUSED_BY_NITIN`. No Make activation, purchases, heartbeat changes
or publication through this inbox.
