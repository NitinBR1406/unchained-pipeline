"""Optional V02 entry point. Only GEMINI_TEXT_QC tasks add the Gemini stage."""
import json
import re
from pathlib import Path
import sys

import runner as legacy
import gemini_qc as qc

KIND = 'GEMINI_TEXT_QC'
POLICY_PATH = 'p0e4/tasks/GEMINI_TEXT_QC_POLICY_V02.md'
EXTRA_PINS = ['p0e4/task_runner/runner_gemini.py', 'p0e4/task_runner/gemini_qc.py',
              'p0e4/tools/antigravity_gate_acceptance.py', POLICY_PATH,
              'p0e4/evidence/antigravity_gate_v01/LOCAL_1affce4e8ee7bf44.json',
              'p0e4/evidence/gemini_text_qc_v01/LOCAL_0c98c5b60693c538.json']
ORIGINAL_EXECUTE = legacy.execute_task
ORIGINAL_VALIDATE = legacy.validate_task


def validate_task(task, filename):
    identity = ORIGINAL_VALIDATE(task, filename)
    if task['task_type'] == KIND:
        legacy.require(len(task['acceptance_criteria']) <= 10, 'GEMINI_MAX_10_CRITERIA')
    return identity


def request_for(task, evidence, result):
    parts = [json.dumps({'goal': task['goal'], 'base_commit': task['base_commit']}),
             evidence, result['claude_result'], result['codex_review']]
    request = {'schema': 'GEMINI_TEXT_QC_V01',
               'task_id': task['task_id'] + '_R' + str(task['revision']),
               'criteria': [{'id': 'C' + str(i+1), 'question': question}
                            for i, question in enumerate(task['acceptance_criteria'])],
               'sources': [{'id': 'S' + str(i+1), 'text': text, 'sha256': qc.sha(text.encode())}
                           for i, text in enumerate(parts)], 'governance': legacy.GATES.copy()}
    qc.validate_request(request)
    return request


def execute_task(root, commit, task, job, config):
    if task['task_type'] != KIND:
        return ORIGINAL_EXECUTE(root, commit, task, job, config)
    legacy.require(config.get('gemini_text_qc_enabled') is True, 'GEMINI_NOT_ENABLED')
    # Preserve source identity, but do not forward full global history or local files.
    sources = []
    for item in task['inputs']:
        raw = legacy.regular_blob(root, task['base_commit'], item['path'])
        legacy.require(qc.sha(raw) == item['sha256'], 'GEMINI_SOURCE_HASH')
        sources.append(dict(item, text=raw.decode()))
    evidence = json.dumps(sources, ensure_ascii=False)
    legacy.require(len(evidence.encode()) <= 12000, 'GEMINI_SOURCE_BUDGET')
    request_for(task, evidence, {'claude_result': '', 'codex_review': ''})
    result = ORIGINAL_EXECUTE(root, commit, task, job, config)
    legacy.atomic(job / 'claude_codex_result.json', result)
    # A Gemini-stage failure must not discard completed Claude/Codex output.
    try:
        review = qc.execute(request_for(task, evidence, result), Path.home())
        result['gemini_text_qc'] = review
        result['status'] = 'IN_REVIEW'
    except Exception as exc:
        result['status'] = 'PARTIAL_REVIEW_GEMINI_HOLD'
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[A-Z0-9_,:]{1,160}', str(exc)) else type(exc).__name__
        result['gemini_text_qc'] = {'status': 'HOLD', 'reason': reason,
                                   'automatic_retry': False, 'media_inspected': False}
    result['review_scope'] = 'Claude output, Codex technical review, optional Gemini TEXT review; no media QC or human approval'
    return result


def install_overrides():
    legacy.KINDS.add(KIND)
    for path in EXTRA_PINS:
        if path not in legacy.PINNED:
            legacy.PINNED.append(path)
    legacy.validate_task = validate_task
    legacy.execute_task = execute_task


if __name__ == '__main__':
    install_overrides()
    legacy.main()
