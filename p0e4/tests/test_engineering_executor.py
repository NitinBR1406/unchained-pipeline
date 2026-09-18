import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller.engineering import run,git,atomic,WriteCLI,projection
from control_plane.ledger import EventLedger


class Transport:
    def __init__(self,outputs):self.calls=0;self.outputs=outputs
    def invoke(self,job,workspace,prompt,heartbeat):
        self.calls+=1;heartbeat()
        for path,value in self.outputs.items():
            p=workspace/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value)+'\n')
        rows=[{'type':'thread.started','thread_id':'TEST_ONLY'},
              {'type':'item.completed','item':{'type':'command_execution','exit_code':0}}, {'type':'turn.completed'}]
        (job/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
        atomic(job/'exit.json',{'exit_code':0,'terminated':True})


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.root=self.home/'repo';self.root.mkdir()
        git(self.root,'init','--quiet','-b','p0e4/slice1-production-handoff')
        git(self.root,'config','user.name','Test');git(self.root,'config','user.email','test@localhost')
        (self.root/'base.txt').write_text('frozen');git(self.root,'add','base.txt');git(self.root,'commit','--quiet','-m','base')
        self.base=git(self.root,'rev-parse','HEAD');self.job=self.home/'job'
        self.task={'task_id':'TEST_ONLY','status':'READY','human_gate_required':None,'scope':'p0e4_nonproduction_contract_fixture',
                   'base_sha':self.base,'commit_time':'2026-09-18T21:10:00Z','outputs':{'p0e4/generated/test.json':{'safe':True}}}
        self.transport=Transport(self.task['outputs']);self.regressions=0
    def regression(self,root,job,commit):
        self.regressions+=1
        atomic(job/'regression.json',{'tested_sha':commit,'passed':1,'total':1,'tracked_worktree_clean':True,'TEST_ONLY':True})
    def call(self,**kw):
        return run(self.root,self.task,self.job,self.transport,regression=self.regression,require_authority=False,**kw)
    def test_completion_restart_one_dispatch_one_commit_replay(self):
        a=self.call();before=(self.job/'EVENT_LEDGER.jsonl').read_bytes();b=self.call()
        self.assertEqual(a,b);self.assertEqual(self.transport.calls,1);self.assertEqual(self.regressions,1)
        self.assertEqual(git(self.root,'rev-list','--count',self.base+'..HEAD'),'1')
        self.assertEqual(before,(self.job/'EVENT_LEDGER.jsonl').read_bytes())
        self.assertEqual(json.loads((self.job/'state.json').read_text()),projection(EventLedger(str(self.job/'EVENT_LEDGER.jsonl'))))
    def test_crash_matrix_no_duplicate_side_effect_or_commit(self):
        for boundary in ('after_dispatch','after_verified','after_commit_object','after_regression','after_commit','after_push','after_result'):
            with self.subTest(boundary=boundary):
                self.setUp()
                def crash(point):
                    if point==boundary:raise RuntimeError('TEST_CRASH')
                with self.assertRaises(RuntimeError):self.call(crash=crash)
                self.assertEqual(self.call()['status'],'COMPLETED');self.assertEqual(self.transport.calls,1)
                self.assertEqual(git(self.root,'rev-list','--count',self.base+'..HEAD'),'1')
    def test_stale_lease_predispatch_retry_and_live_lease_hold(self):
        def crash(point):
            if point=='after_claim':raise RuntimeError()
        with self.assertRaises(RuntimeError):self.call(crash=crash,now=lambda:100)
        self.assertEqual(self.call(now=lambda:105)['status'],'LEASE_ACTIVE');self.assertEqual(self.transport.calls,0)
        self.assertEqual(self.call(now=lambda:111)['status'],'COMPLETED');self.assertEqual(self.transport.calls,1)
    def test_ambiguous_intent_never_redispatched(self):
        def crash(point):
            if point=='after_intent':raise RuntimeError()
        with self.assertRaises(RuntimeError):self.call(crash=crash)
        self.assertEqual(self.call()['status'],'HOLD');self.assertEqual(self.call()['status'],'HOLD');self.assertEqual(self.transport.calls,0)
        self.assertEqual(git(self.root,'rev-parse','HEAD'),self.base)
    def test_output_allowlist_and_symlink_fail_closed(self):
        self.transport.outputs={'p0e4/generated/evil.json':{}}
        self.assertEqual(self.call()['status'],'HOLD');self.assertEqual(git(self.root,'rev-parse','HEAD'),self.base)
    def test_gate_and_traversal_rejected_before_dispatch(self):
        self.task['human_gate_required']='NITIN_APPROVAL'
        with self.assertRaises(ValueError):self.call()
        self.task['human_gate_required']=None;self.task['outputs']={'p0e4/generated/../../frozen.json':{}}
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(self.transport.calls,0)
    def test_regression_failure_cannot_promote(self):
        def failed(root,job,commit):atomic(job/'regression.json',{'tested_sha':commit,'passed':0,'total':1,'tracked_worktree_clean':True})
        self.assertEqual(run(self.root,self.task,self.job,self.transport,regression=failed,require_authority=False)['status'],'HOLD')
        self.assertEqual(git(self.root,'rev-parse','HEAD'),self.base)
    def test_push_crash_recovery_local_bare_remote(self):
        remote=self.home/'remote.git';git(self.root,'init','--bare','--quiet',str(remote));git(self.root,'remote','add','origin',str(remote))
        git(self.root,'push','--quiet','origin','HEAD')
        def crash(point):
            if point=='after_push':raise RuntimeError()
        with self.assertRaises(RuntimeError):self.call(push=True,crash=crash)
        result=self.call(push=True);self.assertTrue(result['remote_verified']);self.assertEqual(self.transport.calls,1)
        self.assertEqual(git(self.root,'ls-remote','origin','refs/heads/p0e4/slice1-production-handoff').split()[0],result['commit'])
    def test_receipt_and_ledger_tamper_rejected(self):
        self.call();p=self.job/'workspace/p0e4/generated/test.json';p.write_text('{}')
        with self.assertRaises(ValueError):self.call()
    def test_actual_timeout_terminates_child_without_commit(self):
        exe=self.home/'sleep.py';exe.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(20)\n');exe.chmod(0o700)
        self.transport=WriteCLI(str(exe),timeout=.1)
        self.assertEqual(self.call()['status'],'HOLD')
        self.assertEqual(json.loads((self.job/'exit.json').read_text())['exit_code'],124)
        self.assertEqual(self.call()['status'],'HOLD');self.assertEqual(git(self.root,'rev-parse','HEAD'),self.base)
    def test_alternate_output_directory_cannot_duplicate_dispatch(self):
        self.call();self.job=self.home/'different'
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(self.transport.calls,1)
    def test_competing_lock_no_dispatch(self):
        import fcntl
        self.job.mkdir()
        with (self.job/'executor.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(self.call()['status'],'BUSY');self.assertEqual(self.transport.calls,0)
    def test_branch_change_does_not_overwrite(self):
        def crash(point):
            if point=='after_verified':raise RuntimeError()
        with self.assertRaises(RuntimeError):self.call(crash=crash)
        (self.root/'other').write_text('independent');git(self.root,'add','other');git(self.root,'commit','--quiet','-m','other')
        self.assertEqual(self.call()['status'],'HOLD')
        self.assertEqual((self.root/'other').read_text(),'independent');self.assertEqual(self.transport.calls,1)

if __name__=='__main__':unittest.main()
