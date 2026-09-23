"""Fail-closed prompt optimization governed by immutable execution context refs.

Optimization proposes a candidate. It never dispatches, rewrites the source contract,
or promotes a candidate without semantic-equivalence acceptance.
"""
from copy import deepcopy
import hashlib
import json
import re

PROMPT_CLASSES = ('MICRO_PROMPT', 'TASK_PROMPT', 'RESEARCH_PROMPT',
                  'HUMAN_GATE_PROMPT', 'FULL_CONTRACT_PROMPT')
ACTORS = ('CODEX', 'CLAUDE', 'GEMINI', 'NITIN')
PROTECTED = ('human_gates', 'acceptance_criteria', 'provenance',
             'rights_source_binding', 'evidence_requirements', 'governance')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_ref(ref):
    require(set(ref) == {'uri', 'sha256'}, 'context ref fields')
    require(isinstance(ref['uri'], str) and ref['uri'], 'context ref uri')
    require(re.fullmatch('[0-9a-f]{64}', ref['sha256']) is not None, 'context ref sha')


def validate_context(context):
    expected = {'schema', 'schema_version', 'context_id', 'repository', 'branch',
                'tested_sha', 'master_state_ref', 'task_state_refs', 'authority',
                'allowed_operations', 'forbidden_operations', 'budgets'}
    require(set(context) == expected, 'execution context fields')
    require(context['schema'] == 'EXECUTION_CONTEXT_GOVERNANCE_V01', 'context schema')
    require(context['schema_version'] == 1, 'context version')
    require(re.fullmatch('[0-9a-f]{40}', context['tested_sha']) is not None, 'tested sha')
    validate_ref(context['master_state_ref'])
    require(isinstance(context['task_state_refs'], list), 'task refs')
    for ref in context['task_state_refs']:
        validate_ref(ref)
    require(context['authority']['production_deployment_authorized'] is False, 'production authority drift')
    require(context['authority']['publication_authorized'] is False, 'publication authority drift')
    require(context['authority']['first_real_poster'] == 'PAUSED_BY_NITIN', 'poster gate drift')
    require('PUBLISH' in context['forbidden_operations'], 'publish must be forbidden')
    require(all(isinstance(context['budgets'][x], int) and context['budgets'][x] >= 0
                for x in ('max_input_tokens', 'max_output_tokens', 'max_retries', 'max_latency_ms')),
            'invalid budgets')
    return context


def validate_prompt(prompt):
    expected = {'schema', 'schema_version', 'prompt_id', 'prompt_class', 'actor',
                'objective', 'context_refs', 'instructions', 'protected_semantics',
                'output_contract', 'metrics_contract'}
    require(set(prompt) == expected, 'prompt contract fields')
    require(prompt['schema'] == 'GOVERNED_PROMPT_V01' and prompt['schema_version'] == 1, 'prompt version')
    require(prompt['prompt_class'] in PROMPT_CLASSES, 'prompt class')
    require(prompt['actor'] in ACTORS, 'actor')
    require(isinstance(prompt['instructions'], list) and prompt['instructions'], 'instructions')
    require(set(prompt['protected_semantics']) == set(PROTECTED), 'protected semantic fields')
    for value in prompt['protected_semantics'].values():
        require(isinstance(value, list) and value, 'protected semantics cannot be empty')
    require(isinstance(prompt['context_refs'], list) and prompt['context_refs'], 'context refs')
    for ref in prompt['context_refs']:
        validate_ref(ref)
    require(prompt['metrics_contract'] == ['input_tokens', 'output_tokens', 'cost', 'latency_ms',
                                            'retries', 'failures', 'semantic_drift',
                                            'accepted_green'], 'metrics contract drift')
    return prompt


def lint(prompt):
    validate_prompt(prompt)
    findings = []
    instructions = prompt['instructions']
    normalized = [re.sub(r'\s+', ' ', x.strip()).lower() for x in instructions]
    for i, value in enumerate(normalized):
        if not value:
            findings.append({'severity': 'ERROR', 'code': 'EMPTY_INSTRUCTION', 'index': i})
        if any(x in value for x in ('it goes without saying', 'please note that', 'in order to')):
            findings.append({'severity': 'WARN', 'code': 'FILLER', 'index': i})
    for i, value in enumerate(normalized):
        if value in normalized[:i]:
            findings.append({'severity': 'WARN', 'code': 'DUPLICATION', 'index': i})
        if re.search(r'\b(it|this|that|they)\b', value) and len(value.split()) < 8:
            findings.append({'severity': 'WARN', 'code': 'AMBIGUITY', 'index': i})
    protected_text = canonical(prompt['protected_semantics']).decode()
    for token in ('approval', 'acceptance', 'evidence', 'rights', 'source', 'provenance'):
        if token not in protected_text.lower():
            findings.append({'severity': 'ERROR', 'code': 'MISSING_CONSTRAINT_' + token.upper()})
    return {'status': 'FAIL' if any(x['severity'] == 'ERROR' for x in findings) else 'PASS',
            'findings': findings}


def candidate(prompt):
    """Remove exact instruction duplicates only; protected data is byte-equivalent."""
    validate_prompt(prompt)
    result = deepcopy(prompt)
    seen = set()
    result['instructions'] = [x for x in prompt['instructions']
                              if not (re.sub(r'\s+', ' ', x.strip()).lower() in seen
                                      or seen.add(re.sub(r'\s+', ' ', x.strip()).lower()))]
    result['prompt_id'] = prompt['prompt_id'] + ':candidate:' + digest(result)[:12]
    return result


def equivalence(source, optimized):
    validate_prompt(source); validate_prompt(optimized)
    checks = {
        'objective_equal': source['objective'] == optimized['objective'],
        'context_refs_equal': source['context_refs'] == optimized['context_refs'],
        'protected_semantics_equal': canonical(source['protected_semantics']) == canonical(optimized['protected_semantics']),
        'output_contract_equal': source['output_contract'] == optimized['output_contract'],
        'metrics_contract_equal': source['metrics_contract'] == optimized['metrics_contract'],
        'actor_equal': source['actor'] == optimized['actor'],
        'prompt_class_equal': source['prompt_class'] == optimized['prompt_class'],
        'instruction_set_equal': set(source['instructions']) == set(optimized['instructions']),
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'source_sha256': digest(source), 'candidate_sha256': digest(optimized)}


def result_metrics(attempts):
    """Primary objective: minimum total cost among accepted GREEN attempts only."""
    required = {'input_tokens', 'output_tokens', 'cost', 'latency_ms', 'retries',
                'failures', 'semantic_drift', 'accepted_green'}
    require(isinstance(attempts, list) and attempts, 'attempt metrics required')
    for item in attempts:
        require(set(item) == required, 'attempt metric fields')
        require(item['cost'] >= 0 and item['input_tokens'] >= 0 and item['output_tokens'] >= 0,
                'negative metrics')
    green = [x for x in attempts if x['accepted_green'] and not x['semantic_drift'] and not x['failures']]
    return {'objective': 'MINIMUM_TOTAL_COST_PER_ACCEPTED_GREEN_RESULT',
            'accepted_green_results': len(green),
            'total_cost': sum(x['cost'] for x in attempts),
            'total_cost_per_accepted_green': None if not green else sum(x['cost'] for x in attempts) / len(green),
            'status': 'NO_ACCEPTED_GREEN_RESULT' if not green else 'MEASURED'}
