# Prompt Governance V01

Primary objective: minimize total cost per accepted GREEN result. Cost reduction
never weakens acceptance, evidence, provenance, rights/source binding, human gates,
or governance. A prompt optimizer emits a candidate only. The source prompt remains
authoritative until deterministic semantic-equivalence validation passes and a
reviewer explicitly selects the candidate for execution.

The five prompt classes are `MICRO_PROMPT`, `TASK_PROMPT`, `RESEARCH_PROMPT`,
`HUMAN_GATE_PROMPT`, and `FULL_CONTRACT_PROMPT`. Templates exist for Codex, Claude,
Gemini, and Nitin. Each prompt refers to hash-bound repository/state artifacts instead
of copying their content. Execution Context Governance binds branch, tested SHA,
authority, allowed/forbidden operations, refs, and token/output/retry/latency budgets.

Lint checks filler, exact duplication, ambiguity, missing protected constraints, and
contract shape. Automatic optimization is limited to exact duplicate removal.
Paraphrases are not automatically equivalent. Promotion fails closed if any protected
semantics, context refs, actor, class, objective, output or metrics contract drifts.

Metrics are recorded per attempt: input/output tokens, cost, latency, retries,
failures, semantic drift, and acceptance GREEN. Failed, drifted, or non-GREEN attempts
remain in total cost but never enter the GREEN denominator.

This is an offline governance and evaluation layer. It does not dispatch agents,
authorize cost, deploy production, bind audio, clear rights, approve assets, or publish.
