"""Bounded single-host write executor. Child writes only disposable workspace.

Host verifies an explicit output allowlist before deterministic Git promotion.
An ambiguous dispatch is held, never respawned; verified work resumes promotion.
No production, network service, UI, human approval or multi-host execution.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import handoff as h
from controller.dispatch import atomic,utc
from integration.contracts import canonical,digest,require
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

BRANCH='p0e4/slice1-production-handoff'


def git(root,*args,env=None,input=None):
    return subprocess.check_output(['git',*args],cwd=root,env=env,input=input).decode().strip()


def append(ledger,phase,details):
    ledger.append(h.make_event('write-%06d'%len(ledger.read_all()),'EVIDENCE_REGISTERED',utc(),'codex',
                              inputs={'phase':phase,**details}))
    with open(ledger.path,'rb') as f:os.fsync(f.fileno())


def projection(ledger):
    reduced=derive(ledger,keyring={})
    return {'reducer':reduced,'phase':ledger.read_all()[-1]['inputs']['phase'] if ledger.read_all() else 'READY'}


class WriteCLI:
    def __init__(self,executable,timeout=120):
        self.executable=executable;self.timeout=timeout
        require(0<timeout<=300,'timeout must be bounded')

    def invoke(self,job,workspace,prompt,heartbeat):
        command=[self.executable,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                 '--sandbox','workspace-write','-c','approval_policy="never"','--json','--color','never',
                 '--output-last-message',str(job/'last.txt'),'-C',str(workspace),'-']
        with (job/'events.jsonl').open('xb') as out,(job/'stderr.txt').open('xb') as err:
            p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
            atomic(job/'process.json',{'pid':p.pid,'started_at':utc()})
            p.stdin.write(prompt.encode());p.stdin.close()
            start=time.monotonic();timed_out=False
            while p.poll() is None:
                heartbeat()
                if time.monotonic()-start>=self.timeout:
                    timed_out=True;os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
                    break
                time.sleep(.5)
            p.wait();out.flush();os.fsync(out.fileno());err.flush();os.fsync(err.fileno())
        atomic(job/'exit.json',{'exit_code':124 if timed_out else p.returncode,'terminated':True})


def inspect_outputs(workspace,task):
    paths=sorted(p for p in workspace.rglob('*') if p.is_file() or p.is_symlink())
    require(all(not p.is_symlink() for p in workspace.rglob('*')),'symlink forbidden')
    actual={str(p.relative_to(workspace)) for p in paths}
    require(actual==set(task['outputs']),'unexpected or missing child output')
    result={}
    for name,rule in task['outputs'].items():
        raw=(workspace/name).read_bytes();require(len(raw)<=32768,'output too large')
        value=json.loads(raw)
        require(value==rule,'independent expected contract validation failed')
        result[name]=digest(raw)
    return result


def verify_execution(job,workspace,task):
    require(json.loads((job/'intent.json').read_text())=={'task_sha256':digest(canonical(task)),'base_sha':task['base_sha']},'intent identity drift')
    exit_record=json.loads((job/'exit.json').read_text())
    require(exit_record=={'exit_code':0,'terminated':True},'execution failure or timeout')
    events=[json.loads(x) for x in (job/'events.jsonl').read_text().splitlines()]
    require(events[0]['type']=='thread.started' and events[-1]['type']=='turn.completed','incomplete CLI receipt')
    require(sum(x['type']=='turn.completed' for x in events)==1,'ambiguous turn')
    require(not any(x['type'] in ('error','turn.failed') for x in events),'failed CLI turn')
    require(any(x.get('item',{}).get('type') in ('command_execution','file_change') for x in events),'no actual write tool evidence')
    for x in events:
        item=x.get('item',{})
        require(item.get('type') not in ('mcp_tool_call','web_search'),'external tool outside engineering scope')
        if x['type']=='item.completed' and item.get('type')=='command_execution':
            require(item.get('exit_code')==0,'child command failed')
    return {'status':'VERIFIED','task_id':task['task_id'],'thread_id':events[0]['thread_id'],
            'outputs':inspect_outputs(workspace,task),'events_sha256':digest((job/'events.jsonl').read_bytes()),
            'exit_sha256':digest((job/'exit.json').read_bytes()),'model':None}


def promote(root,job,workspace,task,base,push,crash,regression):
    """Deterministic commit object; CAS branch and remote prevent duplicate commits."""
    paths=task['outputs'];index=job/'git-index'
    if index.exists():index.unlink() # disposable alternate index, no user's staging affected
    env=dict(os.environ,GIT_INDEX_FILE=str(index),GIT_AUTHOR_NAME='P0E4 Engineering Executor',
             GIT_AUTHOR_EMAIL='p0e4-executor@localhost',GIT_COMMITTER_NAME='P0E4 Engineering Executor',
             GIT_COMMITTER_EMAIL='p0e4-executor@localhost',GIT_AUTHOR_DATE=task['commit_time'],GIT_COMMITTER_DATE=task['commit_time'])
    git(root,'read-tree',base,env=env)
    for path in paths:
        obj=git(root,'hash-object','-w','--stdin',input=(workspace/path).read_bytes())
        git(root,'update-index','--add','--cacheinfo','100644',obj,path,env=env)
    tree=git(root,'write-tree',env=env)
    commit=git(root,'commit-tree',tree,'-p',base,env=env,input=('feat(p0e4): '+task['task_id']+' [skip ci]\n').encode())
    atomic(job/'commit.json',{'base':base,'commit':commit,'tree':tree})
    crash('after_commit_object')
    report=job/'regression.json'
    if report.exists():
        tested=json.loads(report.read_text())
        require(tested['tested_sha']==commit and tested['passed']==tested['total'] and tested['tracked_worktree_clean'] is True,'regression receipt invalid')
    else:
        regression(root,job,commit)
        tested=json.loads(report.read_text())
        require(tested['tested_sha']==commit and tested['passed']==tested['total'] and tested['total']>0 and tested['tracked_worktree_clean'] is True,'candidate regression failed')
    crash('after_regression')
    head=git(root,'rev-parse','HEAD');require(head in (base,commit),'branch moved; reconciliation required')
    require(git(root,'branch','--show-current')==BRANCH,'wrong branch')
    require(not git(root,'status','--porcelain','--untracked-files=no'),'tracked worktree dirty')
    if head==base:
        for path in paths:require(not (root/path).exists(),'destination already exists')
        git(root,'merge','--ff-only',commit)
    crash('after_commit')
    if push:
        remote=git(root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]
        require(remote in (base,commit),'remote moved; no force overwrite')
        if remote==base:git(root,'push','--force-with-lease=refs/heads/'+BRANCH+':'+base,'origin',commit+':refs/heads/'+BRANCH)
        require(git(root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]==commit,'remote commit not verified')
    crash('after_push')
    return {'commit':commit,'remote_verified':bool(push)}


def full_regression(root,job,commit):
    candidate=job/'candidate'
    if not candidate.exists():git(root,'clone','--quiet','--no-hardlinks',str(root),str(candidate))
    git(candidate,'checkout','--quiet','--detach',commit)
    require(not git(candidate,'status','--porcelain'),'candidate not clean')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONWARNINGS='ignore::ResourceWarning')
    subprocess.run([sys.executable,str(candidate/'p0e4/integration/verify.py'),str(job/'regression.json')],cwd=candidate,env=env,check=True,timeout=240)


def run(root,task,directory,transport,push=False,crash=lambda point:None,now=time.time,regression=full_regression,require_authority=True):
    root=Path(root).resolve();job=Path(directory).resolve();job.mkdir(parents=True,exist_ok=True)
    if require_authority:
        seed_path='p0e4/controller/READY_WRITES_V01.json'
        seed_raw=(root/seed_path).read_bytes()
        require(seed_raw==subprocess.check_output(['git','show','HEAD:'+seed_path],cwd=root),'uncommitted authority')
        seed=json.loads(seed_raw)
        require({k:v for k,v in task.items() if k!='base_sha'} in seed['tasks'],'task not in committed READY list')
        require(digest((root/seed['master_state_path']).read_bytes())==seed['master_state_sha256'],'V10 authority drift')
    require(task['status']=='READY' and task['human_gate_required'] is None,'task not authorized')
    require(task['scope']=='p0e4_nonproduction_contract_fixture','unsupported write scope')
    require(set(task)=={'task_id','status','human_gate_required','scope','base_sha','commit_time','outputs'},'unknown task fields')
    require(task['outputs'] and all(p.startswith('p0e4/generated/') and '..' not in Path(p).parts and p.endswith('.json') for p in task['outputs']),'unsafe output scope')
    require(len(task['outputs'])<=3,'bounded output count')
    require(task['task_id'].replace('_','').isalnum(),'unsafe task identity')
    common=Path(git(root,'rev-parse','--git-common-dir'))
    if not common.is_absolute():common=root/common
    with (common/'p0e4-write.lock').open('a') as global_lock,(job/'executor.lock').open('a') as lock:
        try:
            fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'BUSY'}
        ledger=EventLedger(str(job/'EVENT_LEDGER.jsonl'));ledger.verify_chain()
        identity=digest(canonical(task));base=task['base_sha']
        registry=common/'p0e4-executor'/('task-'+task['task_id']+'.json')
        binding={'task_sha256':identity,'job_directory':str(job)}
        if registry.exists():require(json.loads(registry.read_text())==binding,'task already bound to another durable job')
        else:atomic(registry,binding)
        if (job/'task.json').exists():require(json.loads((job/'task.json').read_text())==task,'task drift')
        else:atomic(job/'task.json',task)
        if (job/'completion.json').exists():
            receipt=json.loads((job/'completion.json').read_text())
            require(receipt['task_sha256']==identity,'receipt identity drift')
            require(verify_execution(job,job/'workspace',task)==json.loads((job/'verified.json').read_text()),'receipt evidence drift')
            require(git(root,'rev-parse',receipt['commit'])==receipt['commit'],'commit missing')
            for path,sha in receipt['outputs'].items():require(digest(subprocess.check_output(['git','show',receipt['commit']+':'+path],cwd=root))==sha,'committed bytes drift')
            return receipt
        workspace=job/'workspace';workspace.mkdir(exist_ok=True)
        if not (job/'intent.json').exists():
            require(git(root,'rev-parse','HEAD')==base,'base moved before dispatch')
            require(not git(root,'status','--porcelain','--untracked-files=no'),'source dirty before dispatch')
            require(all(not (root/p).exists() for p in task['outputs']),'task outputs already exist')
            if (job/'lease.json').exists() and json.loads((job/'lease.json').read_text())['expires_at']>now():return {'status':'LEASE_ACTIVE'}
            atomic(job/'lease.json',{'task_sha256':identity,'expires_at':now()+10})
            append(ledger,'CLAIMED',{'task_sha256':identity});crash('after_claim')
            prompt=('Non-production bounded engineering fixture task. Write exactly the JSON files specified below relative to cwd. '
                    'Use local file tools only. No network, MCP, Git, publication, approvals, other files or installation. '
                    'Do not wrap output JSON in markdown. No additional keys. Then finish.\n'+json.dumps(task['outputs'],sort_keys=True))
            atomic(job/'intent.json',{'task_sha256':identity,'base_sha':base});append(ledger,'RUNNING',{'task_sha256':identity});crash('after_intent')
            def heartbeat():
                atomic(job/'lease.json',{'task_sha256':identity,'expires_at':now()+10})
                append(ledger,'HEARTBEAT',{'task_sha256':identity})
            transport.invoke(job,workspace,prompt,heartbeat);crash('after_dispatch')
        try:verified=verify_execution(job,workspace,task)
        except (ValueError,OSError,KeyError,IndexError) as exc:
            receipt={'status':'HOLD','task_sha256':identity,'reason':type(exc).__name__,'blind_retry_permitted':False}
            atomic(job/'failure.json',receipt)
            if not ledger.read_all() or ledger.read_all()[-1]['inputs']['phase']!='HOLD':append(ledger,'HOLD',receipt)
            atomic(job/'state.json',projection(ledger));return receipt
        if (job/'verified.json').exists():require(json.loads((job/'verified.json').read_text())==verified,'verified receipt drift')
        else:atomic(job/'verified.json',verified);append(ledger,'VERIFIED',verified)
        crash('after_verified')
        try:promotion=promote(root,job,workspace,task,base,push,crash,regression)
        except (ValueError,subprocess.SubprocessError,OSError) as exc:
            receipt={'status':'HOLD','task_sha256':identity,'reason':'PROMOTION_OR_REGRESSION_'+type(exc).__name__,'blind_retry_permitted':False}
            atomic(job/'failure.json',receipt)
            append(ledger,'HOLD',receipt);atomic(job/'state.json',projection(ledger));return receipt
        receipt={'status':'COMPLETED','task_sha256':identity,**verified,**promotion};receipt['status']='COMPLETED'
        if not any(r['inputs']['phase']=='COMPLETED' for r in ledger.read_all()):append(ledger,'COMPLETED',receipt)
        atomic(job/'state.json',projection(ledger));crash('after_result')
        atomic(job/'completion.json',receipt)
        return receipt

def run_ready(root,directory,transport,push=False,**kwargs):
    """Drain the committed bounded READY list; completed jobs do not redispatch."""
    root=Path(root).resolve();directory=Path(directory).resolve();results=[]
    seed=json.loads((root/'p0e4/controller/READY_WRITES_V01.json').read_text())
    common=Path(git(root,'rev-parse','--git-common-dir'))
    if not common.is_absolute():common=root/common
    for entry in seed['tasks']:
        registry=common/'p0e4-executor'/('task-'+entry['task_id']+'.json')
        if registry.exists():
            job=Path(json.loads(registry.read_text())['job_directory'])
            task=json.loads((job/'task.json').read_text())
            require({k:v for k,v in task.items() if k!='base_sha'}==entry,'READY definition changed')
        else:
            task={**entry,'base_sha':git(root,'rev-parse','HEAD')};job=directory/entry['task_id']
        results.append(run(root,task,job,transport,push,**kwargs))
    return {'status':'QUIESCENT','results':results,'completed':sum(r['status']=='COMPLETED' for r in results),
            'held':sum(r['status']!='COMPLETED' for r in results)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--task');p.add_argument('--output',required=True);p.add_argument('--push',action='store_true')
    a=p.parse_args();transport=WriteCLI('/Applications/ChatGPT.app/Contents/Resources/codex')
    result=(run(a.root,json.loads(Path(a.task).read_text()),a.output,transport,a.push) if a.task else run_ready(a.root,a.output,transport,a.push))
    print(json.dumps(result))
