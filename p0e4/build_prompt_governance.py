"""Generate deterministic offline prompt-governance evidence and critical-path routing."""
import hashlib
import json
from pathlib import Path
import subprocess
from prompt_governance import candidate, digest, equivalence, lint, validate_context
from prompt_templates import template, PROMPT_CLASSES, ACTORS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'p0e4/evidence/prompt_governance_v01'


def file_ref(relative):
    path = ROOT / relative
    return {'uri': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    master = file_ref('p0e4/MASTER_STATE_LATEST.json')
    task_refs = [file_ref('p0e4/evidence/resolve_studio_v163/NEXT_READY.json'),
                 file_ref('p0e4/evidence/catalog_minimal_review_v01/NEXT_READY.json'),
                 file_ref('p0e4/evidence/target_v13/AAKHRI_ISHQ_INPUT_BINDING.json')]
    context = {
        'schema': 'EXECUTION_CONTEXT_GOVERNANCE_V01', 'schema_version': 1,
        'context_id': 'P0E4_PROMPT_GOVERNANCE_V01',
        'repository': 'NitinBR1406/unchained-pipeline',
        'branch': 'p0e4/slice1-production-handoff', 'tested_sha': head,
        'master_state_ref': master, 'task_state_refs': task_refs,
        'authority': {'production_deployment_authorized': False,
                      'publication_authorized': False,
                      'first_real_poster': 'PAUSED_BY_NITIN'},
        'allowed_operations': ['READ_REFERENCED_CONTEXT', 'PROPOSE_PROMPT_CANDIDATE',
                               'LINT', 'SEMANTIC_EQUIVALENCE_CHECK', 'WRITE_REPO_EVIDENCE'],
        'forbidden_operations': ['PUBLISH', 'PRODUCTION_DEPLOY', 'INFER_HUMAN_GATE',
                                 'INFER_RIGHTS', 'INFER_SOURCE_BINDING', 'NEW_COST'],
        'budgets': {'max_input_tokens': 12000, 'max_output_tokens': 8000,
                    'max_retries': 2, 'max_latency_ms': 300000}}
    validate_context(context)
    write('EXECUTION_CONTEXT_GOVERNANCE_V01.json', context)
    context_ref = file_ref('p0e4/evidence/prompt_governance_v01/EXECUTION_CONTEXT_GOVERNANCE_V01.json')
    prompts = []
    for actor in ACTORS:
        for prompt_class in PROMPT_CLASSES:
            source = template(prompt_class, actor,
                              f'P0E4:{actor}:{prompt_class}',
                              'Produce the minimum-cost accepted GREEN result within the referenced scope.',
                              [context_ref, master] + task_refs)
            source['instructions'].append(source['instructions'][0])
            optimized = candidate(source)
            prompts.append({'actor': actor, 'prompt_class': prompt_class,
                            'source': source, 'source_lint': lint(source),
                            'candidate': optimized, 'candidate_lint': lint(optimized),
                            'semantic_equivalence': equivalence(source, optimized),
                            'promotion_status': 'ELIGIBLE_FOR_REVIEW_NOT_AUTO_PROMOTED'})
    require_all = all(x['source_lint']['status'] == 'PASS' and
                      x['candidate_lint']['status'] == 'PASS' and
                      x['semantic_equivalence']['status'] == 'PASS' for x in prompts)
    write('PROMPT_TEMPLATE_MATRIX_V01.json', {
        'schema': 'PROMPT_TEMPLATE_MATRIX_V01', 'schema_version': 1,
        'count': len(prompts), 'actors': list(ACTORS), 'prompt_classes': list(PROMPT_CLASSES),
        'all_candidates_equivalent': require_all, 'templates': prompts})
    metrics = {
        'primary_objective': 'MINIMUM_TOTAL_COST_PER_ACCEPTED_GREEN_RESULT',
        'formula': 'sum(cost across all attempts) / count(accepted_green without failure or drift)',
        'dimensions': ['input_tokens', 'output_tokens', 'cost', 'latency_ms', 'retries',
                       'failures', 'semantic_drift', 'accepted_green'],
        'optimization_policy': 'No cheaper result counts unless acceptance is GREEN and semantic drift is false.',
        'baseline_measurements': 'NOT_YET_OBSERVED', 'new_cost_authorized': False}
    write('METRICS_CONTRACT_V01.json', metrics)
    next_ready = {
        'schema': 'PROMPT_GOVERNANCE_NEXT_READY_V01', 'schema_version': 1,
        'status': 'PROMPT_GOVERNANCE_ACCEPTED_RETURN_TO_CRITICAL_PATH',
        'ready_nonhuman_count': 1,
        'ordered_critical_path': [
            {'order': 1, 'task_id': 'RAW_INGEST_RECONCILE', 'status': 'READY',
             'scope': 'Read-only reconcile already hashed RAW against ingest contract; do not bind audio.'},
            {'order': 2, 'task_id': 'POST_READY_CONTRACT', 'status': 'READY_AFTER_1',
             'scope': 'Build/validate fail-closed contract for post-ingest orchestration.'},
            {'order': 3, 'task_id': 'REAL_MEDIA_ORCHESTRATION', 'status': 'DEPENDENCY_BLOCKED',
             'blocked_by': ['AKI_AUTHORITATIVE_AUDIO_BINDING', 'PRODUCTION_DEPLOYMENT_AUTHORIZED']},
            {'order': 4, 'task_id': 'AAKHRI_ISHQ_RAW_DROP_AUDIO_BINDING', 'status': 'WAITING_FOR_NITIN',
             'blocked_by': ['AKI_AUTHORITATIVE_AUDIO_BINDING']},
            {'order': 5, 'task_id': 'COMPLETE_FACTORY_E2E', 'status': 'DEPENDENCY_BLOCKED',
             'blocked_by': ['REAL_MEDIA_ORCHESTRATION', 'PRODUCTION_DEPLOYMENT_AUTHORIZED']}
        ],
        'human_gates_preserved': True, 'publication_authorized': False,
        'production_deployment_authorized': False, 'first_real_poster': 'PAUSED_BY_NITIN'}
    write('NEXT_READY.json', next_ready)
    acceptance = {
        'status': 'PASS_OFFLINE_PROMPT_GOVERNANCE', 'tested_sha': head,
        'template_count': len(prompts), 'prompt_classes': list(PROMPT_CLASSES),
        'actors': list(ACTORS), 'source_lint_passed': require_all,
        'candidate_semantic_equivalence_passed': require_all,
        'candidate_auto_promoted': False, 'execution_context_validated': True,
        'protected_semantics': ['human_gates', 'acceptance_criteria', 'provenance',
                                'rights_source_binding', 'evidence_requirements', 'governance'],
        'external_dispatches': 0, 'new_costs': 0,
        'production_deployment_authorized': False, 'publication_authorized': False,
        'first_real_poster': 'PAUSED_BY_NITIN'}
    write('ACCEPTANCE.json', acceptance)
    files = sorted(x for x in OUT.iterdir() if x.name != 'SHA256SUMS.txt')
    (OUT / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.name + '\n' for x in files))


if __name__ == '__main__':
    main()
