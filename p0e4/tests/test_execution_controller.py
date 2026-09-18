import copy
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller.runner import run,load_seed
from controller.dispatch import Pending,atomic
from integration.contracts import canonical,digest
from control_loop.control_loop import CrashInjected

SEED=h.ROOT/'p0e4/controller/READY_TASKS_V01.json'


class TestTransport:
    name='TEST_ONLY_CLI_DOUBLE'
    def __init__(self, malformed=False):self.calls=0;self.malformed=malformed
    def invoke(self,directory,prompt):
        self.calls+=1
        data=json.loads((directory/'intent.json').read_text())['binding']
        message={'task_id':data['task_id'],'input_sha256':data['input_sha256'],'result':'PASS','status':'COMPLETED'}
        if self.malformed:message['input_sha256']='wrong'
        text=json.dumps(message,separators=(',',':'))
        (directory/'last.json').write_text(text)
        events=[{'type':'thread.started','thread_id':'TEST_ONLY_'+data['task_id']},
                {'type':'turn.started'},{'type':'item.completed','item':{'type':'agent_message','text':text}},
                {'type':'turn.completed','usage':{'input_tokens':0,'output_tokens':0}}]
        (directory/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        atomic(directory/'exit.json',{'exit_code':0})


def hold_lock(path,ready,release):
    with open(path,'a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);ready.set();release.wait(10)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)/'runtime';self.transport=TestTransport()
    def call(self,now=1000,**kwargs):
        return run(SEED,self.out,self.transport,h.Clock(now),require_committed=False,**kwargs)

    def test_two_ready_tasks_dependency_order_replay_restart_no_duplicate(self):
        result=self.call();self.assertEqual(result['backlog_summary']['completed'],2)
        self.assertTrue(result['replay_verified']);self.assertEqual(self.transport.calls,2)
        before=(self.out/'EVENT_LEDGER.jsonl').read_bytes()
        self.call(2000);self.assertEqual(self.transport.calls,2)
        self.assertEqual(before,(self.out/'EVENT_LEDGER.jsonl').read_bytes())
        rows=[json.loads(x) for x in before.splitlines()]
        self.assertEqual([r['task_id'] for r in rows if r['event_type']=='TASK_RESULT'],['EC_V10_GOVERNANCE_AUDIT','EC_V10_RIGHTS_HOLD_AUDIT'])
        self.assertFalse(any(r['event_type']=='HUMAN_GATE_GRANTED' for r in rows))
        self.assertTrue(all(r['agent']=='codex' for r in rows))

    def test_atomic_process_lock(self):
        self.out.mkdir();ctx=multiprocessing.get_context('fork');ready=ctx.Event();release=ctx.Event()
        proc=ctx.Process(target=hold_lock,args=(str(self.out/'controller.lock'),ready,release));proc.start()
        try:
            self.assertTrue(ready.wait(5));result=self.call()
            self.assertEqual(result['status'],'BUSY');self.assertEqual(self.transport.calls,0)
        finally:release.set();proc.join(5)
        self.assertEqual(proc.exitcode,0);self.assertEqual(self.call()['backlog_summary']['completed'],2)

    def test_crash_before_dispatch_safe_lease_expiry_retry(self):
        def crash(boundary,ctx):
            if boundary=='after_started':raise CrashInjected()
        with self.assertRaises(CrashInjected):self.call(crash_hook=crash)
        self.assertEqual(self.transport.calls,0)
        self.call(1001);self.assertEqual(self.transport.calls,0) # live lease not stolen
        self.assertEqual(self.call(2000)['backlog_summary']['completed'],2)
        self.assertEqual(self.transport.calls,2)

    def test_crash_after_intent_is_ambiguous_never_redispatched(self):
        def crash(point):
            if point=='after_intent':raise CrashInjected()
        with self.assertRaises(CrashInjected):self.call(dispatch_crash_hook=crash)
        self.assertEqual(self.transport.calls,0)
        result=self.call(2000);self.assertEqual(self.transport.calls,0)
        self.assertEqual(result['backlog_summary']['blocked'],1)
        self.assertEqual(result['backlog_summary']['completed'],0)

    def test_crash_matrix_receipt_result_persistence(self):
        for boundary in ('after_transport','after_receipt','after_side_effect','after_result_append','after_persist'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as directory:
                self.out=Path(directory);self.transport=TestTransport()
                def dc(point):
                    if point==boundary:raise CrashInjected()
                def lc(point,ctx):
                    if point==boundary:raise CrashInjected()
                with self.assertRaises(CrashInjected):self.call(crash_hook=lc,dispatch_crash_hook=dc)
                result=self.call(2000)
                self.assertEqual(result['backlog_summary']['completed'],2)
                self.assertEqual(self.transport.calls,2)
                self.assertTrue(result['replay_verified'])

    def test_malformed_receipt_no_task_result(self):
        self.transport=TestTransport(malformed=True);result=self.call()
        self.assertEqual(result['backlog_summary']['blocked'],1)
        self.assertEqual(result['backlog_summary']['completed'],0)
        self.call(2000);self.assertEqual(self.transport.calls,1)
        events=(self.out/'EVENT_LEDGER.jsonl').read_text()
        self.assertNotIn('"event_type":"TASK_RESULT"',events)

    def test_seed_scope_gate_source_and_dependency_tampering(self):
        original=json.loads(SEED.read_text())
        changes=[lambda s:s['tasks'][0].update(human_gate_required='NITIN_PUBLISH_APPROVAL'),
                 lambda s:s['tasks'][0].update(allowed_scope=['publish']),
                 lambda s:s['tasks'][0]['source'].update(sha256='a'*64),
                 lambda s:s['tasks'][0].update(dependencies=['EC_V10_RIGHTS_HOLD_AUDIT']),
                 lambda s:s['tasks'][0]['checks'][0].update(expected=15),
                 lambda s:s.update(source_commit='a'*40)]
        path=Path(self.tmp.name)/'seed.json'
        for change in changes:
            seed=copy.deepcopy(original);change(seed);path.write_text(json.dumps(seed))
            with self.subTest(change=change),self.assertRaises(ValueError):load_seed(path)

    def test_backlog_tamper_is_rejected(self):
        self.call();path=self.out/'BACKLOG.json';rows=json.loads(path.read_text())
        rows[0]['input_hash']='a'*64;path.write_text(json.dumps(rows))
        with self.assertRaises(ValueError):self.call(2000)
        self.assertEqual(self.transport.calls,2)

    def test_uncertain_task_does_not_block_independent_ready(self):
        original=json.loads(SEED.read_text());original['tasks'][1]['dependencies']=[]
        path=Path(self.tmp.name)/'seed.json';path.write_text(json.dumps(original))
        transport=TestTransport()
        first=[True]
        def invoke(directory,prompt):
            transport.calls+=1
            if first[0]:first[0]=False;return
            transport.calls-=1;TestTransport.invoke(transport,directory,prompt)
        transport.invoke=invoke
        result=run(path,self.out,transport,h.Clock(1000),require_committed=False)
        self.assertEqual(result['backlog_summary']['blocked'],1)
        self.assertEqual(result['backlog_summary']['completed'],1)

    def test_completed_artifact_tampering_never_passes_cached_success(self):
        self.call()
        path=next((self.out/'dispatch').glob('*/last.json'))
        path.write_text('{}')
        with self.assertRaises(Pending):self.call(2000)
        self.assertEqual(self.transport.calls,2)

    def test_ledger_tamper_fails_closed(self):
        self.call();path=self.out/'EVENT_LEDGER.jsonl';path.write_text(path.read_text().replace('codex','forged',1))
        with self.assertRaises(Exception):self.call(2000)
        self.assertEqual(self.transport.calls,2)

if __name__=='__main__':unittest.main()
