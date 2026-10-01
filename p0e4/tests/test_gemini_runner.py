import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'task_runner'))
import runner as r
import runner_gemini as v2
import upgrade_gemini as upgrade


def task(kind=v2.KIND):
    return {'schema':'P0E4_AUTOMATED_TASK_V01','task_id':'SYNTHETIC_CHAIN_V02','revision':1,
            'parent_task_id':None,'status':'READY','task_type':kind,'policy':r.POLICY,
            'goal':'Assess supplied text only.','base_commit':'a'*40,
            'inputs':[{'path':'p0e4/example.json','sha256':r.sha(b'{"synthetic":true}')}],
            'acceptance_criteria':['Is publication authorized?'],
            'budget':{'max_attempts':1,'timeout_seconds':300,'max_turns':8},'governance':r.GATES.copy()}


class RouteTests(unittest.TestCase):
    def test_legacy_types_never_invoke_gemini(self):
        for kind in ('READ_ONLY','BUILD_PROPOSAL','RESOLVE_READ_ONLY'):
            with patch.object(v2,'ORIGINAL_EXECUTE',return_value={'status':'IN_REVIEW'}) as original, \
                 patch.object(v2.qc,'execute') as gemini:
                v2.execute_task(None,None,task(kind),None,{})
                original.assert_called_once();gemini.assert_not_called()

    def test_success_preserves_reviews_and_bound_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            result={'status':'IN_REVIEW','claude_result':'Builder report','codex_review':'Technical review',
                    'governance':r.GATES.copy()}
            with patch.object(v2,'ORIGINAL_EXECUTE',return_value=result), \
                 patch.object(r,'regular_blob',return_value=b'{"synthetic":true}'), \
                 patch.object(v2.qc,'execute',return_value={'status':'IN_REVIEW','media_inspected':False}) as gemini:
                out=v2.execute_task(Path(temp),'b'*40,task(),Path(temp),{'gemini_text_qc_enabled':True})
                request=gemini.call_args.args[0]
                self.assertEqual(request['task_id'],'SYNTHETIC_CHAIN_V02_R1')
                self.assertEqual(len(request['sources']),4)
                self.assertEqual(request['sources'][2]['text'],'Builder report')
                self.assertEqual(out['status'],'IN_REVIEW')
                self.assertTrue((Path(temp)/'claude_codex_result.json').is_file())

    def test_gemini_failure_preserves_claude_codex_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            result={'status':'IN_REVIEW','claude_result':'Builder','codex_review':'Reviewer'}
            with patch.object(v2,'ORIGINAL_EXECUTE',return_value=result) as original, \
                 patch.object(r,'regular_blob',return_value=b'{"synthetic":true}'), \
                 patch.object(v2.qc,'execute',side_effect=ValueError('tool attempt')) as gemini:
                out=v2.execute_task(Path(temp),'b'*40,task(),Path(temp),{'gemini_text_qc_enabled':True})
                self.assertEqual(out['status'],'PARTIAL_REVIEW_GEMINI_HOLD')
                self.assertEqual(out['claude_result'],'Builder')
                original.assert_called_once();gemini.assert_called_once()
                self.assertFalse(out['gemini_text_qc']['automatic_retry'])

    def test_disabled_hash_drift_or_oversize_stops_before_models(self):
        for config,raw in [({},b'{"synthetic":true}'),({'gemini_text_qc_enabled':True},b'changed'),
                           ({'gemini_text_qc_enabled':True},b'x'*13000)]:
            t=task()
            if len(raw)>12000:t['inputs'][0]['sha256']=r.sha(raw)
            with patch.object(v2,'ORIGINAL_EXECUTE') as original, patch.object(r,'regular_blob',return_value=raw):
                with self.assertRaises(ValueError):v2.execute_task(None,None,t,None,config)
                original.assert_not_called()

    def test_new_type_schema_and_criterion_limit(self):
        t=task();path=r.INBOX+t['task_id']+'_R1.json'
        with patch.object(r,'KINDS',r.KINDS|{v2.KIND}):
            self.assertEqual(v2.validate_task(t,path),'SYNTHETIC_CHAIN_V02_R1')
            t['acceptance_criteria']=['x']*11
            with self.assertRaisesRegex(ValueError,'MAX_10'):v2.validate_task(t,path)

    def test_request_budget_never_truncates(self):
        with self.assertRaises(ValueError):
            v2.request_for(task(),'source',{'claude_result':'x'*32000,'codex_review':'y'*32000})


class UpgradeTests(unittest.TestCase):
    def test_installed_snapshot_imports_adapter_from_its_own_root(self):
        source=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for path in upgrade.RUNTIME_PATHS:
                output=root/path;output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes((source/path).read_bytes())
            code="import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); import runner_gemini as v; assert v.qc.ROOT == Path(sys.argv[2]); v.install_overrides(); assert v.KIND in v.legacy.KINDS; print('OK')"
            run=subprocess.run([sys.executable,'-B','-c',code,str(root/'p0e4/task_runner'),str(root)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)

    def test_pending_task_blocks_baseline_advance(self):
        with tempfile.TemporaryDirectory() as temp:
            gh=Mock()
            gh.pages.side_effect=[[{'merged_at':'today','merge_commit_sha':'a'*40,'number':7}],
                                  [{'filename':r.INBOX+'task.json'}]]
            with patch.object(upgrade.subprocess,'run',return_value=Mock(returncode=1)),patch.object(r,'git'):
                self.assertEqual(upgrade.pending_tasks(gh,Path(temp),{'baseline':'b'*40,'state':temp},'c'*40),[7])
            p=Path(temp)/'pr_7';p.mkdir();(p/'delivered.json').write_text('{}')
            gh.pages.side_effect=[[{'merged_at':'today','merge_commit_sha':'a'*40,'number':7}],
                                  [{'filename':r.INBOX+'task.json'}]]
            with patch.object(upgrade.subprocess,'run',return_value=Mock(returncode=1)),patch.object(r,'git'):
                self.assertEqual(upgrade.pending_tasks(gh,Path(temp),{'baseline':'b'*40,'state':temp},'c'*40),[])

    def test_failed_activation_restores_exact_old_files(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'config.json';plist=Path(temp)/'runner.plist'
            config.write_bytes(b'{"old":true}\n');plist.write_bytes(plistlib.dumps({'Label':upgrade.LABEL}))
            oldc=config.read_bytes();oldp=plist.read_bytes()
            with patch.object(r,'run',side_effect=[b'',ValueError('bootstrap failed'),b'']) as run, \
                 patch.object(upgrade.subprocess,'run'):
                with self.assertRaisesRegex(ValueError,'RESTORED'):
                    upgrade.activate(config,plist,{'new':True},{'Label':upgrade.LABEL},501)
                self.assertEqual(config.read_bytes(),oldc);self.assertEqual(plist.read_bytes(),oldp)
                self.assertEqual(run.call_count,3)

    def test_success_reuses_same_label(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'config.json';plist=Path(temp)/'runner.plist'
            config.write_text('{}');plist.write_bytes(plistlib.dumps({'Label':upgrade.LABEL}))
            with patch.object(r,'run',return_value=b'') as run:
                upgrade.activate(config,plist,{'gemini_text_qc_enabled':True},{'Label':upgrade.LABEL},501)
                self.assertEqual(run.call_args_list[0].args[0][-1],'gui/501/'+upgrade.LABEL)
                self.assertTrue(json.loads(config.read_text())['gemini_text_qc_enabled'])
                self.assertEqual(plistlib.loads(plist.read_bytes())['Label'],upgrade.LABEL)


if __name__ == '__main__':unittest.main()
