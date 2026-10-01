import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('gemini_qc', Path(__file__).parents[1] / 'task_runner/gemini_qc.py')
M = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = M.synthetic_request()
        self.answer = {'task_id': self.request['task_id'], 'checks': [
            {'id': 'C1', 'verdict': 'CONTRADICTED', 'source_ids': ['S1'], 'reason': 'Source explicitly denies authorization.'},
            {'id': 'C2', 'verdict': 'NOT_PROVEN', 'source_ids': [], 'reason': 'No media supplied.'}]}

    def raw(self, answer=None, **overrides):
        envelope = {'status': 'SUCCESS', 'conversation_id': 'synthetic-session-1234',
                    'response': json.dumps(answer or self.answer)}
        envelope.update(overrides)
        return json.dumps(envelope).encode()

    def test_success_is_only_in_review(self):
        r = M.validate_response(self.raw(), self.request)
        self.assertEqual(r['status'], 'IN_REVIEW')
        self.assertFalse(r['media_inspected'])
        self.assertFalse(r['automatic_runner_activated'])
        self.assertFalse(r['human_approval_created'])

    def test_hash_gate_and_secret_input(self):
        self.request['sources'][0]['text'] += 'changed'
        with self.assertRaisesRegex(ValueError, 'HASH'): M.validate_request(self.request)
        text = 'github_pat_' + 'a' * 60
        self.request['sources'][0].update(text=text, sha256=M.sha(text.encode()))
        with self.assertRaisesRegex(ValueError, 'SECRET'): M.validate_request(self.request)

    def test_unknown_fields_and_gate_drift(self):
        self.request['governance']['PUBLICATION_AUTHORIZED'] = True
        with self.assertRaises(ValueError): M.validate_request(self.request)
        self.request = M.synthetic_request(); self.request['permission'] = 'allow'
        with self.assertRaises(ValueError): M.validate_request(self.request)

    def test_cli_error_or_invalid_json(self):
        for raw in [b'not json', self.raw(status='FAILED'), self.raw(error='denied'), self.raw(response='```json\n{}\n```')]:
            with self.assertRaises((ValueError, TypeError)): M.validate_response(raw, self.request)

    def test_wrong_binding_missing_duplicate_and_extra_checks(self):
        self.answer['task_id'] = 'OTHER_TASK'
        with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)
        self.answer['task_id'] = self.request['task_id']
        self.answer['checks'][1]['id'] = 'C1'
        with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)
        self.answer['checks'].pop()
        with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)

    def test_unknown_citation_uncited_claim_and_approval(self):
        check = self.answer['checks'][0]
        for refs in [['S8'], [], ['S1', 'S1']]:
            check['source_ids'] = refs
            with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)
        check['source_ids'] = ['S1']; check['verdict'] = 'APPROVED'
        with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)
        check['verdict'] = 'SUPPORTED'; self.answer['approval'] = True
        with self.assertRaises(ValueError): M.validate_response(self.raw(), self.request)

    def test_duplicate_json_keys_and_output_secret(self):
        with self.assertRaises(ValueError): M.parse('{"status":"FAILED","status":"SUCCESS"}')
        self.answer['checks'][0]['reason'] = 'ghp_' + 'a' * 40
        with self.assertRaisesRegex(ValueError, 'SECRET'): M.validate_response(self.raw(), self.request)

    def test_prompt_is_text_only_and_no_media_claim(self):
        prompt = M.prompt_for(self.request)
        self.assertIn('No tools', prompt)
        self.assertIn('untrusted', prompt)
        self.assertIn('No media was supplied', prompt)

    def test_mock_process_receipt_and_second_attempt_never_spawns(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); (home/'Unchained-Gemini-QC').mkdir()
            binary = home/'.local/bin/agy'; binary.parent.mkdir(parents=True); binary.write_bytes(b'mock')
            receipt_path = M.ROOT/'p0e4/evidence/antigravity_gate_v01/LOCAL_1affce4e8ee7bf44.json'
            receipt = json.loads(receipt_path.read_text())
            receipt['binary_sha256_before'] = M.sha(b'mock')
            real_parse = M.parse
            def parsed(raw):
                if raw == receipt_path.read_bytes(): return receipt
                return real_parse(raw)
            def fake_process(argv, **kw):
                self.assertNotIn('--mode', argv)
                self.assertIn('--sandbox', argv)
                kw['stdout'].write(self.raw()); kw['stdout'].flush()
                proc = unittest.mock.Mock(); proc.returncode = 0
                return proc
            with patch.object(M.sys, 'platform', 'darwin'), patch.object(M, 'BINARY_SHA', M.sha(b'mock')), \
                 patch.object(M, 'parse', side_effect=parsed), patch.object(M.subprocess, 'Popen', side_effect=fake_process) as spawn:
                r = M.execute(self.request, home)
                self.assertEqual(r['status'], 'IN_REVIEW')
                with self.assertRaises(FileExistsError): M.execute(self.request, home)
                self.assertEqual(spawn.call_count, 1)

    def test_tool_attempt_runtime_mutation_failure_and_timeout_hold(self):
        for mode in ('tool', 'mutation', 'nonzero', 'timeout'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                home=Path(temp);(home/'Unchained-Gemini-QC').mkdir()
                binary=home/'.local/bin/agy';binary.parent.mkdir(parents=True);binary.write_bytes(b'mock')
                receipt_path=M.ROOT/'p0e4/evidence/antigravity_gate_v01/LOCAL_1affce4e8ee7bf44.json'
                original=receipt_path.read_bytes();receipt=json.loads(original)
                receipt['binary_sha256_before']=M.sha(b'mock');real_parse=M.parse
                def parsed(raw): return receipt if raw == original else real_parse(raw)
                def fake(argv, **kw):
                    kw['stdout'].write(self.raw());kw['stdout'].flush()
                    job=Path(kw['cwd'])
                    if mode=='tool': (job/'denials.jsonl').write_text('{}\n')
                    if mode=='mutation': (job/'deny_gate.py').write_text('changed')
                    proc=unittest.mock.Mock();proc.pid=12345;proc.returncode=1 if mode=='nonzero' else 0
                    if mode=='timeout': proc.wait.side_effect=[subprocess.TimeoutExpired(argv,75),0]
                    return proc
                with patch.object(M.sys,'platform','darwin'), patch.object(M,'BINARY_SHA',M.sha(b'mock')), \
                     patch.object(M,'parse',side_effect=parsed), patch.object(M.subprocess,'Popen',side_effect=fake), \
                     patch.object(M.os,'killpg') as kill:
                    with self.assertRaises(ValueError): M.execute(self.request,home)
                    if mode=='timeout': kill.assert_called_once()
                    jobs=list((home/'Unchained-Gemini-QC').glob('text-qc-*'))
                    self.assertTrue((jobs[0]/'intent.json').exists())
                    self.assertFalse((jobs[0]/'RESULT.json').exists())

    def test_config_conflict_never_spawns(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);(home/'Unchained-Gemini-QC').mkdir()
            f=home/'.gemini/config/mcp_config.json';f.parent.mkdir(parents=True);f.write_text('{}')
            with patch.object(M.sys,'platform','darwin'), patch.object(M.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'CUSTOM_CONFIG'): M.execute(self.request,home)
                spawn.assert_not_called()


if __name__ == '__main__': unittest.main()
