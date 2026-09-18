"""Single-host execution controller reusing the frozen P0-E3 loop.

An OS flock surrounds load -> claim -> dispatch -> receipt -> reduce -> persist.
Leases alone are not used as a multi-process compare-and-swap. No multi-host
coordination or production scheduling is claimed. All dispatch is read-only.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from integration.contracts import canonical,digest,require,keys,file_resolver
from controller.dispatch import CodexCLI,DurableDispatch,Pending,atomic
from control_loop.state_model import verify_replay

SOURCE_SHA='63a7fd1feefd7b498b0fe9a7ad6d965047c07fa6'
SCOPE='p0e4_readonly_evidence_audit'


class WallClock:
    def now(self):return time.time()
    def advance(self,dt=1):return self.now()


def load_seed(path,root=h.ROOT):
    seed=json.loads(Path(path).read_text())
    keys(seed,'schema_version source_commit source_master_state tasks')
    require(seed['schema_version']==1 and type(seed['schema_version']) is int,'seed schema')
    require(seed['source_commit']==SOURCE_SHA,'unexpected authoritative baseline')
    ref=seed['source_master_state'];keys(ref,'path sha256')
    resolve=file_resolver(root)
    raw=resolve(ref['path']);require(digest(raw)==ref['sha256'],'Master State drift')
    state=json.loads(raw)
    require(state['state_version']==14,'expected authoritative V09')
    require(all(state['authorizations'][k] is False for k in ('PRODUCTION_DEPLOYMENT_AUTHORIZED','PUBLICATION_AUTHORIZED')),'authorization drift')
    require(state['production_state']['first_real_poster']=='PAUSED_BY_NITIN','poster gate drift')
    require(type(seed['tasks']) is list and bool(seed['tasks']),'no task contract')
    ids=set();payloads={}
    for task in seed['tasks']:
        keys(task,'task_id priority status dependencies allowed_scope human_gate_required source checks')
        tid=task['task_id'];require(type(tid) is str and tid.startswith('EC_V10_') and tid not in ids,'task identity')
        require(type(task['priority']) is int and task['priority']>=0,'task priority')
        require(task['status']=='READY' and task['allowed_scope']==[SCOPE],'scope not authorized')
        require(task['human_gate_required'] is None,'human task cannot be dispatched')
        require(type(task['dependencies']) is list and all(d in ids for d in task['dependencies']),'dependencies must precede task')
        ids.add(tid)
        source=task['source'];keys(source,'path sha256')
        require(source['path'] in ('p0e4/evidence/integration_v09/UNCHAINED_MASTER_PROJECT_STATE_V09.json',
                                  'p0e4/evidence/integration_v09/RIGHTS_MATRIX.json'),'source outside audited V09 scope')
        data=resolve(source['path']);require(digest(data)==source['sha256'],'source bytes differ')
        committed=subprocess.check_output(['git','show',SOURCE_SHA+':'+source['path']],cwd=root)
        require(data==committed,'source is not authoritative commit bytes')
        obj=json.loads(data);observations=[]
        require(type(task['checks']) is list and bool(task['checks']),'checks missing')
        for check in task['checks']:
            keys(check,'pointer expected');pointer=check['pointer']
            require(type(pointer) is list and bool(pointer),'invalid JSON pointer')
            value=obj
            for key in pointer:value=value[key]
            require(type(value)==type(check['expected']) and value==check['expected'],'host check failed')
            observations.append({'pointer':pointer,'observed':value,'expected':check['expected']})
        payloads[tid]={'source_commit':SOURCE_SHA,'source':source,'observations':observations}
    return seed,payloads


class Loop(h.DurableControlLoop):
    """Additive provenance/hold adapter; frozen leasing/scheduling/reducer unchanged."""
    def _append(self,event_type,**kw):
        event=h.make_event('ec-%06d-%s'%(len(self.ledger.read_all()),event_type),event_type,
                           str(self.clock.now()),'codex',**kw)
        record=self.ledger.append(event)
        with open(self.ledger.path,'rb') as stream:os.fsync(stream.fileno())
        return record

    def reconcile_backlog_from_ledger(self):
        super().reconcile_backlog_from_ledger()
        # A pending intent is an execution boundary, never permission to spawn twice.
        for task in self.backlog.tasks:
            jid=self._recorded_job_id(task['task_id'])
            if not jid or self._has_event(task['task_id'],'TASK_RESULT'):continue
            if (self.executor.location(jid)/'intent.json').exists():
                lease=self.leases.get(task['task_id'])
                if lease and not lease.released and not lease.is_expired(self.clock.now()):continue
                task['status']='READY' if self.executor.recoverable(jid) else 'BLOCKED'
                task['blocked_reason']=None if task['status']=='READY' else 'DISPATCH_UNCONFIRMED_NO_BLIND_RETRY'
        self.backlog.save()

    def process_one(self,task,worker_id='worker-1'):
        try:return super().process_one(task,worker_id)
        except Pending:
            tid=task['task_id'];lease=self.leases.get(tid)
            self._append('EVIDENCE_REGISTERED',task_id=tid,inputs={'execution_status':'DISPATCH_UNCONFIRMED_NO_BLIND_RETRY'})
            if lease and not lease.released:
                self._append('LEASE_RELEASED',task_id=tid,lease_id=lease.lease_id);lease.release()
            self.backlog.set_status(tid,'BLOCKED',blocked_reason='DISPATCH_UNCONFIRMED_NO_BLIND_RETRY')
            self._persist_current()
            return 'BLOCKED'


def run(seed_path,directory,transport=None,clock=None,crash_hook=None,dispatch_crash_hook=None,require_committed=True):
    seed_path=Path(seed_path).resolve();directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    with (directory/'controller.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'BUSY','dispatch_count':0}
        # All authoritative input and mutable projections are reloaded after locking.
        seed,payloads=load_seed(seed_path)
        seed_raw=seed_path.read_bytes();seed_hash=digest(seed_raw)
        if require_committed:
            rel=str(seed_path.relative_to(h.ROOT))
            require(seed_raw==subprocess.check_output(['git','show','HEAD:'+rel],cwd=h.ROOT),'READY seed not committed')
            require(subprocess.run(['git','diff','--quiet','HEAD'],cwd=h.ROOT).returncode==0,'tracked source differs from committed execution SHA')
        receipt=directory/'seed.json'
        if receipt.exists():require(receipt.read_bytes()==canonical(seed)+b'\n','immutable READY-task seed changed')
        else:atomic(receipt,seed)
        transport=transport or CodexCLI(shutil.which('codex') or '')
        dispatch=DurableDispatch(directory/'dispatch',payloads,transport,dispatch_crash_hook)
        loop=Loop(str(directory),keyring={},clock=clock or WallClock(),executor=dispatch,crash_hook=crash_hook,ttl=180)
        loop.ledger.verify_chain()
        request=next((r for r in loop.ledger.read_all() if r['event_type']=='TASK_REQUEST'),None)
        if request:require(request['inputs']['seed_sha256']==seed_hash,'seed request hash conflict')
        else:loop._append('TASK_REQUEST',inputs={'seed_sha256':seed_hash,'source_commit':SOURCE_SHA,'scope':SCOPE})
        if not loop.backlog.tasks:
            loop.backlog.tasks=[h.task(t['task_id'],t['priority'],digest(canonical(payloads[t['task_id']])),
                                      deps=t['dependencies']) for t in seed['tasks']]
            for task in loop.backlog.tasks:
                task['allowed_scope']=[SCOPE];task['definition_of_done']='Verified actual Codex CLI receipt over pinned V09 evidence'
            loop.backlog.save()
        # Existing backlog may only contain the authoritative seed identities/inputs.
        require({t['task_id'] for t in loop.backlog.tasks}==set(payloads),'backlog task injection')
        for task,source in zip(loop.backlog.tasks,seed['tasks']):
            require(task['task_id']==source['task_id'] and task['input_hash']==digest(canonical(payloads[task['task_id']])),'backlog input drift')
            require(task['human_gate_required'] is None and task['dependencies']==source['dependencies'] and task['allowed_scope']==[SCOPE],'backlog authority drift')
        result=loop.run(worker_id='p0e4-codex-controller',max_iterations=len(seed['tasks'])+1)
        # Cached successes must still bind to durable transport artifacts. A cached
        # side-effect store or edited receipt alone cannot make acceptance GREEN.
        for task in loop.backlog.tasks:
            if task['status']=='COMPLETED':
                jid=loop._recorded_job_id(task['task_id']);location=dispatch.location(jid)
                verified=dispatch._verify(location,task,jid)
                require(json.loads((location/'receipt.json').read_text())==verified,'completed receipt tamper')
        replay,detail=verify_replay(loop.ledger,loop.persisted_state(),keyring={})
        require(replay,'replay mismatch: '+detail)
        result.update(status='QUIESCENT',replay_verified=True,seed_sha256=seed_hash,
                      implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip(),
                      publication_authorized=False,production_deployment_authorized=False,first_real_poster='PAUSED_BY_NITIN')
        atomic(directory/'CONTROLLER_RESULT.json',result)
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seed',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(run(args.seed,args.output),sort_keys=True))
