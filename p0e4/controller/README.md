# P0-E4 Execution Controller — minimum vertical slice

Actual surface: locally installed `codex exec` (0.155.0-alpha.2.6), authenticated
with the existing ChatGPT login. The probe in evidence/controller_v10/probe executed
before this controller was implemented. No invented Work/Claude/Gemini API.
[Official non-interactive docs](https://learn.chatgpt.com/docs/non-interactive-mode)
and local `codex exec --help` establish JSONL, output schema and final-message flags.

Scope: one host, one controller directory, read-only evidence audits, no model tools.
The immutable READY_TASKS_V01.json is committed before real execution. It binds the
V09 Master State and source bytes to authoritative commit 63a7fd1. Runtime source
hashes and governance are checked, then task observations are passed to real Codex.
The first task checks governance; the second dependency-ready task checks eight
RIGHTS_HOLD decisions. These are real engineering evidence audits, not renders.

## Claim, execution and recovery

1. Nonblocking OS flock encloses reload/claim/lease/dispatch/receipt/reduce/persist.
   Competing processes return BUSY; expired leases alone cannot race another writer.
2. Frozen P0-E3 DurableControlLoop creates leases and immutable job IDs, schedules
   dependencies, appends events, invokes its executor and calls the frozen reducer.
   Additive subclass records Codex provenance and parks uncertain dispatches.
3. Dispatcher fsyncs intent BEFORE CLI spawn. Each job path can spawn only once.
   Schema and prompt are fixed. Child sandbox read-only, approvals never, user config
   excluded, ephemeral session, bounded 120-second invocation. No keys are copied.
4. Successful JSONL turn + exact final response + task/input/job binding are verified.
   Unexpected tool events, errors, nonzero exit, wrong hash, wrong result or malformed
   bytes cannot produce a receipt. Model self-reported PASS is insufficient.
5. Receipt is atomically persisted before the frozen side-effect cache/TASK_RESULT.
   Crash after CLI completion or receipt: harvest the SAME artifacts, no re-dispatch.
   Cached results are revalidated against their CLI artifact hashes on every run.
6. Crash before intent: lease expires, safe deterministic retry with same job ID.
   Intent exists but no provable completion: BLOCKED, no blind retry. Independent
   READY work continues. A later completed receipt can be reconciled on restart.
   Remote exactly-once invocation cannot be promised: CLI exposes no proven server
   idempotency API. At-most-one local spawn and exactly-once result application are
   the verified boundaries. Ambiguity is deliberately a hold, not an automatic retry.
7. Persisted runtime state must equal deterministic frozen reducer replay. Master
   V10 records scoped acceptance as append-only evidence, not human approval.

Process-crash durability and one-host concurrency only; no multi-host failover,
automatic daemon installation, power-loss/filesystem durability certification,
production deploy, editing agent or external publication capability is claimed.
Temporal remains the selected control plane; this is its executor boundary, not a
replacement scheduler deployment. Runtime outputs are staging until archived and
read-back verified in the Shared Drive.

Run with the approved host execution context (child remains sandboxed):

    python p0e4/controller/runner.py --seed p0e4/controller/READY_TASKS_V01.json --output <new-controller-directory>

Never delete intent files to force a retry. Do not copy an active controller directory
to another host and run it there. Keep any ambiguous attempt held for reconciliation.
No production task can be added merely by changing a READY status: this slice only
allows the pinned V09 evidence files, read-only scope and absent human gates.

## V11 bounded engineering writer

`engineering.py` adds a single-host write path. The committed READY list permits
only the receipt-schema engineering fixture under `p0e4/generated/`. It is not a
general-purpose production/code executor. The child uses the existing actual
Codex CLI with `workspace-write`, no approval escalation, isolated disposable cwd
and no repository credentials handed into its prompt. No UI adapter is used.

The parent holds a repository-wide lock plus a durable task-to-job registration.
It persists claim, lease, intent, RUNNING and heartbeat events, independently
checks exact output paths/content and execution evidence, creates a deterministic
commit object with an alternate Git index, runs the full offline regression on a
clean detached candidate checkout, then fast-forwards and CAS-pushes that commit.
A crash can repeat object computation or validation but cannot create an extra
commit or re-dispatch an existing intent. A pre-intent expired claim can retry;
an ambiguous post-intent attempt is HOLD. Remote divergence is HOLD, never reset.
Only the parent promotes allowed bytes. Remote exactly-once execution, multi-host
coordination, daemon installation and arbitrary engineering are not claimed.

Runtime must remain in the same durable job directory on recovery. Its repository
Git metadata registration is required and is not a portable queue. Child workspace
sandboxing is OS-enforced; the output allowlist independently protects repository
promotion. This is not a security boundary for hostile model/runtime compromise.
Failures in execution or promotion produce machine-readable HOLD receipts.
The full regression receipt records the exact candidate commit, including generated
outputs, rather than only its pre-execution source commit.
