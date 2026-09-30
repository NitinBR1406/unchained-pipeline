import copy
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('host_audit', ROOT / 'p0e4/tools/local_receipts_gemini_audit.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.service = self.home / 'Library/Application Support/UnchainedTaskRunner'
        self.job = self.service / 'state/pr_2'; self.job.mkdir(parents=True)
        def source(path, ref='2b1cb07c57d2745c9b813aeb4f5e698cee21e911'):
            return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
        self.source = source
        self.result = json.loads(source(a.RESULT_PATH))
        self.task = json.loads(source(a.TASK_PATH))
        session = self.result['claude_session_id']
        self.transcript = self.home / '.claude/projects/test' / (session + '.jsonl')
        self.transcript.parent.mkdir(parents=True)
        self.transcript.write_text(json.dumps({'type':'assistant','sessionId':session,'message':{'content':[{'type':'text','text':'gho_'+'z'*40}]}})+'\n')
        events = [{'type':'thread.started','thread_id':self.result['codex_thread_id']},
                  {'type':'item.completed','item':{'type':'agent_message','text':'private text'}}, {'type':'turn.completed'}]
        for name, raw in [('claude.stdout', b'{"type":"result","result":"private answer"}\n'),
                          ('codex.stdout', ('\n'.join(map(json.dumps,events))+'\n').encode())]:
            (self.job/name).write_bytes(raw); self.result['raw_receipt_sha256'][name] = a.digest(raw)
        self.put('result.json', self.result)
        self.put('intent.json',{'task_sha256':a.digest(json.dumps(self.task,sort_keys=True).encode()),'merge_commit':self.result['merge_commit']})
        settings=json.loads(source('.claude/settings.json'))
        import shlex
        settings['hooks']['PreToolUse'].append({'matcher':'*','hooks':[{'type':'command','command':'/usr/bin/python3 '+shlex.quote(str(self.job/'checkout/p0e4/task_runner/tool_gate.py')),'timeout':10}]})
        settings['autoMemoryEnabled']=False
        self.args=[str(self.home/'.local/bin/claude'),'-p','--restricted','--tools','','--disable-slash-commands',
                   '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--settings',json.dumps(settings),
                   '--permission-mode','default','--permission-prompts','none','--max-turns','8','--output-format','json']
        self.put('claude_process.json',{'argv':self.args})
        self.put('codex_process.json',{'argv':['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-c','approval_policy="never"','--json','--output-last-message',str(self.job/'review.txt'),'-C',str(self.job/'review_workspace'),'-']})
        self.put('delivered.json',{'url':'https://github.com/'+a.REPO+'/pull/3'})
        pins={}
        for name in ('runner.py','tool_gate.py'):
            path='p0e4/task_runner/'+name; raw=source(path)
            out=self.service/'runtime'/name; out.parent.mkdir(exist_ok=True);out.write_bytes(raw)
            pins[path]=a.digest(raw)
        (self.service/'config.json').write_text(json.dumps({'codex':'codex','pins':pins,'baseline':'2b1cb07c57d2745c9b813aeb4f5e698cee21e911'}))
        self.apps=self.home/'Applications';self.apps.mkdir()
        app=self.apps/'Gemini Test.app/Contents';app.mkdir(parents=True)
        (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'test.gemini','CFBundleShortVersionString':'1.2'}))
        self.patch=mock.patch.object(a,'blob',side_effect=lambda repo,commit,path: json.dumps(self.result).encode() if path==a.RESULT_PATH else source(path,commit))
        self.patch.start();self.addCleanup(self.patch.stop)

    def put(self,name,data):
        (self.job/name).write_text(json.dumps(data))

    def report(self):
        return a.audit(self.home,[self.apps])

    def test_positive_receipts_and_known_limitations(self):
        report=self.report()
        for name in ('claude_receipt_hash','codex_receipt_hash','task_intent_binding','claude_recorded_argv',
                     'codex_execution_receipt','claude_no_recorded_tool_calls','installed_runtime_binding','state_sha256_binding','delivery_receipt'):
            self.assertEqual(report['checks'][name]['status'],'VERIFIED',name)
        self.assertEqual(report['checks']['state_version_label_consistency']['status'],'FAILED')
        self.assertEqual(report['checks']['effective_managed_permissions']['status'],'NIET BEWEZEN')
        self.assertFalse(report['gemini_inventory']['cli_executed'])

    def test_raw_conversation_and_secret_not_exported(self):
        raw=json.dumps(self.report())
        self.assertNotIn('gho_'+'z'*40,raw)
        self.assertNotIn('private answer',raw)
        self.assertNotIn('private text',raw)
        self.assertNotIn(str(self.home),raw)

    def test_modified_receipt_fails_hash(self):
        (self.job/'claude.stdout').write_text('changed')
        self.assertEqual(self.report()['checks']['claude_receipt_hash']['status'],'FAILED')

    def test_permission_expansion_fails_recorded_argv(self):
        self.put('claude_process.json',{'argv':self.args+['--allowedTools','Bash']})
        self.assertEqual(self.report()['checks']['claude_recorded_argv']['status'],'FAILED')

    def test_missing_transcript_is_unknown(self):
        self.transcript.unlink()
        self.assertEqual(self.report()['checks']['claude_no_recorded_tool_calls']['status'],'NIET BEWEZEN')

    def test_actual_tool_use_is_failed_not_quoted_text(self):
        data={'type':'assistant','sessionId':self.result['claude_session_id'],'message':{'content':[{'type':'tool_use','name':'Bash','input':{'command':'sensitive'}}]}}
        self.transcript.write_text(json.dumps(data)+'\n')
        report=self.report()
        self.assertEqual(report['checks']['claude_no_recorded_tool_calls']['status'],'FAILED')
        self.assertNotIn('sensitive',json.dumps(report))

    def test_fake_or_empty_transcript_cannot_pass(self):
        self.transcript.write_text(json.dumps({'type':'user','sessionId':self.result['claude_session_id'],'message':{'content':'I used no tools'}})+'\n')
        self.assertEqual(self.report()['checks']['claude_no_recorded_tool_calls']['status'],'FAILED')


if __name__=='__main__': unittest.main(verbosity=2)
