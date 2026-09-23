# Prompt Governance V01

Offline governance layer accepted for the code at `c2a55ee`. It optimizes for
minimum total cost per accepted GREEN result, while failed, drifted and retried
attempts remain in total cost. No observed provider cost baseline exists yet, so
the metrics contract is ready but does not fabricate savings.

Twenty source/candidate pairs cover five prompt classes and Codex, Claude, Gemini
and Nitin. Candidates only remove exact duplicate instructions. Every candidate
passed structural lint and semantic-equivalence checks, but remains
`ELIGIBLE_FOR_REVIEW_NOT_AUTO_PROMOTED`.

Execution Context Governance binds the exact code SHA, branch, Master pointer,
current task states, authority, allowed/forbidden operations and budgets. Large
context blocks are replaced by SHA256 references. Human gates, acceptance criteria,
provenance, rights/source binding, evidence and governance are protected fields.

Adversarial tests prove that removing or changing any protected field, changing a
context ref, paraphrasing an instruction, mutating authority or counting a drifted
attempt as GREEN fails closed. Fifty focused tests covering prompt governance,
catalog, integration, handoff and V16.3 projection passed.

The broad discovery command reached 132 tests but had 18 import errors because the
existing environment lacks `jsonschema`; no assertion failure was observed in the
executed tests. No package was installed and no cost was incurred. Prior authoritative
V16.3 acceptance already preserves its own 74-suite evidence; this additive change
does not rewrite that evidence.

`NEXT_READY.json` returns execution to the parked critical path. Only read-only RAW
reconciliation is currently READY. The RAW bytes are already hash-observed, but no
authoritative audio binding is inferred. Real-media orchestration and Factory E2E
remain blocked by explicit audio/source binding and production authority. Publication
remains false.
