"""Canonical prompt templates. Repository/state refs replace copied context blocks."""
from copy import deepcopy
from prompt_governance import PROMPT_CLASSES, ACTORS

METRICS = ['input_tokens', 'output_tokens', 'cost', 'latency_ms', 'retries',
           'failures', 'semantic_drift', 'accepted_green']


def template(prompt_class, actor, prompt_id, objective, context_refs):
    if prompt_class not in PROMPT_CLASSES or actor not in ACTORS:
        raise ValueError('unknown template dimension')
    protected = {
        'human_gates': ['Never infer or fabricate Nitin approval.'],
        'acceptance_criteria': ['GREEN requires the referenced acceptance contract and exact evidence.'],
        'provenance': ['Preserve producer, run, source and model provenance.'],
        'rights_source_binding': ['Rights and authoritative source/audio binding remain explicit gates.'],
        'evidence_requirements': ['Bind evidence to the exact tested SHA and verify referenced hashes.'],
        'governance': ['PRODUCTION_DEPLOYMENT_AUTHORIZED=false', 'PUBLICATION_AUTHORIZED=false',
                       'FIRST_REAL_POSTER=PAUSED_BY_NITIN'],
    }
    actor_line = {
        'CODEX': 'Implement, test, replay, inspect the diff and persist exact-SHA evidence.',
        'CLAUDE': 'Execute only the explicitly scoped integration task and return a bounded receipt.',
        'GEMINI': 'Perform independent intelligence or QC without claiming execution or approval.',
        'NITIN': 'Decide only the named human gate; unknown or rejected are valid answers.',
    }[actor]
    class_line = {
        'MICRO_PROMPT': 'Perform one atomic deterministic action.',
        'TASK_PROMPT': 'Complete the bounded task through its acceptance checks.',
        'RESEARCH_PROMPT': 'Separate measured facts, estimates and hypotheses; cite provenance.',
        'HUMAN_GATE_PROMPT': 'Present the smallest concrete decision with exact affected artifacts.',
        'FULL_CONTRACT_PROMPT': 'Apply the full referenced contract without weakening constraints.',
    }[prompt_class]
    return {'schema': 'GOVERNED_PROMPT_V01', 'schema_version': 1,
            'prompt_id': prompt_id, 'prompt_class': prompt_class, 'actor': actor,
            'objective': objective, 'context_refs': deepcopy(context_refs),
            'instructions': [class_line, actor_line,
                             'Use repository and state references; do not copy large context blocks.',
                             'Stop at genuine human, credential, financial, rights or governance gates.'],
            'protected_semantics': protected,
            'output_contract': {'required': ['status', 'evidence_refs', 'metrics', 'limitations'],
                                'unknowns': 'EXPLICIT', 'semantic_drift': 'FAIL_CLOSED'},
            'metrics_contract': list(METRICS)}
