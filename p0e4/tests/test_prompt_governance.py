import copy
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prompt_governance import (candidate, equivalence, lint, result_metrics,
                               validate_context, validate_prompt)
from prompt_templates import template

REF = {'uri': 'p0e4/MASTER_STATE_LATEST.json', 'sha256': 'a' * 64}


class PromptGovernance(unittest.TestCase):
    def prompt(self, cls='TASK_PROMPT', actor='CODEX'):
        return template(cls, actor, 'test', 'Produce accepted evidence', [REF])

    def test_all_twenty_template_dimensions(self):
        for cls in ('MICRO_PROMPT','TASK_PROMPT','RESEARCH_PROMPT','HUMAN_GATE_PROMPT','FULL_CONTRACT_PROMPT'):
            for actor in ('CODEX','CLAUDE','GEMINI','NITIN'):
                validate_prompt(self.prompt(cls, actor))

    def test_safe_duplicate_candidate(self):
        p = self.prompt(); p['instructions'].append(p['instructions'][0])
        self.assertEqual(lint(p)['status'], 'PASS')
        c = candidate(p)
        self.assertEqual(equivalence(p, c)['status'], 'PASS')
        self.assertLess(len(c['instructions']), len(p['instructions']))

    def test_human_gate_removal_fails(self):
        p = self.prompt(); c = copy.deepcopy(p); c['protected_semantics']['human_gates'] = ['none']
        self.assertEqual(equivalence(p, c)['status'], 'FAIL')

    def test_acceptance_provenance_rights_evidence_drift_each_fails(self):
        for key in ('acceptance_criteria','provenance','rights_source_binding','evidence_requirements','governance'):
            p=self.prompt();c=copy.deepcopy(p);c['protected_semantics'][key]=['weakened']
            with self.subTest(key=key):self.assertEqual(equivalence(p,c)['status'],'FAIL')

    def test_context_ref_drift_fails(self):
        p=self.prompt();c=copy.deepcopy(p);c['context_refs'][0]['sha256']='b'*64
        self.assertEqual(equivalence(p,c)['status'],'FAIL')

    def test_instruction_paraphrase_is_not_auto_accepted(self):
        p=self.prompt();c=copy.deepcopy(p);c['instructions'][0]+=' now'
        self.assertEqual(equivalence(p,c)['status'],'FAIL')

    def test_cost_denominator_requires_green_without_drift_or_failure(self):
        base={'input_tokens':1,'output_tokens':1,'cost':2.0,'latency_ms':1,'retries':0,'failures':False,'semantic_drift':False,'accepted_green':True}
        bad=copy.deepcopy(base);bad.update(cost=8.0,semantic_drift=True)
        r=result_metrics([base,bad]);self.assertEqual(r['accepted_green_results'],1);self.assertEqual(r['total_cost_per_accepted_green'],10.0)
        bad['accepted_green']=False;self.assertEqual(result_metrics([bad])['status'],'NO_ACCEPTED_GREEN_RESULT')

    def test_execution_context_governance_rejects_authority_drift(self):
        c={'schema':'EXECUTION_CONTEXT_GOVERNANCE_V01','schema_version':1,'context_id':'x',
           'repository':'NitinBR1406/unchained-pipeline','branch':'p0e4/slice1-production-handoff',
           'tested_sha':'a'*40,'master_state_ref':REF,'task_state_refs':[],
           'authority':{'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'},
           'allowed_operations':['READ','WRITE_REPO_EVIDENCE'],'forbidden_operations':['PUBLISH'],
           'budgets':{'max_input_tokens':1,'max_output_tokens':1,'max_retries':0,'max_latency_ms':1}}
        validate_context(c);c['authority']['publication_authorized']=True
        with self.assertRaises(ValueError):validate_context(c)

if __name__ == '__main__': unittest.main()
