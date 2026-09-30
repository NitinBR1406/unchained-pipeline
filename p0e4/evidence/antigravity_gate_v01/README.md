# Antigravity gate acceptance — NOT ACTIVATED

2026-09-30. Scope: disposable synthetic tool-denial test; no task-runner update.

## Evidence correction

The earlier Gemini CLI research is historical. Nitin's installed Gemini CLI
rejected the individual account and instructed migration to Antigravity.
The supplied Mac screenshot subsequently showed Antigravity 1.2.14 returning
SUCCESS / GEMINI_QC_CONNECTION_OK. This establishes a headless response only.
The same screenshot warned that --mode plan has no effect with
--disable-slash-commands. Neither that combination nor a no-tools prompt is
accepted as a technical security control. Desktop Gemini chat continuity is
not established by Antigravity authentication.

## Candidate control and bounded test

Official source checked 2026-09-30: https://antigravity.google/docs/hooks/
documents workspace .agents/hooks.json, a PreToolUse wildcard, and a deny
decision. https://antigravity.google/docs/permissions/ describes explicit
denial priority and implicit workspace access. These docs are not evidence
that the installed binary enforces the control.

The one-shot helper creates a new private child directory of
~/Unchained-Gemini-QC. Its hook always returns deny, including malformed input
and failed logging. One model invocation is asked to attempt a synthetic file
read, disposable file write and harmless printf. No production files are
included. Absence of attempts stays NIET BEWEZEN. Timeout, modified canaries,
binary drift or missing evidence yields HOLD. Even the strongest result is
OBSERVED_GATE_TEST_ONLY, never automatic QC authorization.

The helper does not change global configuration, the installed runner, its
pins, Resolve, Make, Master State, or production/publication gates. Known
existing hook/MCP/plugin customizations stop the test for review; no override
or permission bypass is used. Configuration discovery is not exhaustive.
Runtime-created logs and disposable files remain local for inspection; only
a derived JSON report is published with --publish. Google receives synthetic
test instructions. One normal model request may consume the user's quota.

Remaining acceptance requirements: effective configuration/extension inventory,
MCP/browser/subagent denial, behavior on missing/crashed hooks, full receipt
inspection, and controlled runner integration/update. The hook is not an
OS-level security boundary; a compromised harness can invalidate local logs.

## Offline verification

Command: python3 -B -m unittest discover -s p0e4/tests -p test_antigravity_gate_acceptance.py -v

Tests cover malformed/unknown tool inputs, logging failures, wildcard and path
quoting, incomplete evidence, canary/process/binary failures and configuration
conflicts. Offline tests cannot certify Mac runtime enforcement.
