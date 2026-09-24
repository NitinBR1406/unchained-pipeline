"""Build concise governed prompts from hash-bound repository context references."""
from copy import deepcopy

from prompt_governance import candidate, equivalence, lint, validate_context, validate_prompt
from prompt_templates import template


def build_context(tested_sha, master_ref, task_refs):
    context = {
        "schema": "EXECUTION_CONTEXT_GOVERNANCE_V01", "schema_version": 1,
        "context_id": "P0E4_SYNTHETIC_HARDENING_V01", "repository": "NitinBR1406/unchained-pipeline",
        "branch": "p0e4/slice1-production-handoff", "tested_sha": tested_sha,
        "master_state_ref": deepcopy(master_ref), "task_state_refs": deepcopy(task_refs),
        "authority": {"production_deployment_authorized": False, "publication_authorized": False,
                      "first_real_poster": "PAUSED_BY_NITIN"},
        "allowed_operations": ["SYNTHETIC_TEST", "REPO_EVIDENCE", "SHADOW_PROJECTION"],
        "forbidden_operations": ["REAL_RAW_DROP", "LIVE_MAKE_CUTOVER", "PUBLISH", "SCHEDULE", "PURCHASE"],
        "budgets": {"max_input_tokens": 3000, "max_output_tokens": 2000, "max_retries": 2, "max_latency_ms": 120000},
    }
    return validate_context(context)


def governed_task_prompt(actor, objective, refs):
    prompt = template("TASK_PROMPT", actor, "p0e4-synthetic-hardening", objective, refs)
    validate_prompt(prompt)
    optimized = candidate(prompt)
    report = {"source_lint": lint(prompt), "candidate_lint": lint(optimized),
              "semantic_equivalence": equivalence(prompt, optimized)}
    if report["candidate_lint"]["status"] != "PASS" or report["semantic_equivalence"]["status"] != "PASS":
        raise ValueError("prompt candidate not accepted")
    return {"source": prompt, "candidate": optimized, "acceptance": report}
