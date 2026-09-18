"""Disposable live E4 executor integration, reusing the frozen ControlPlaneTask.

No production endpoints. No signed approvals. TEST_ONLY gate is isolated from AKI.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from datetime import timedelta
import release
import handoff as h
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from control_plane.temporal_live import ControlPlaneTask, act_long, act_verify_approval

EXECUTOR = None
INVOCATIONS = []


@activity.defn(name='act_execute')
async def production_evidence(task: dict) -> dict:
    INVOCATIONS.append(task['task_id'])
    if task['task_id'] == 'TEST_ONLY_PUBLISH_GATE':
        return {'task_id': task['task_id'], 'test_only': True}
    return await asyncio.to_thread(EXECUTOR, task, task['job_id'], 1000)


async def run(package, output, temporal_cli=None):
    global EXECUTOR
    output = Path(output)
    if output.exists():
        raise ValueError('authoritative integration output already exists: do not duplicate run')
    output.mkdir(parents=True)
    EXECUTOR = release.ReleaseExecutor(output/'effects', package)
    loop = h.DurableControlLoop(str(output/'control'), keyring={})
    release.seed(loop, package)
    workflows = {}
    with tempfile.TemporaryDirectory(prefix='p0e4-temporal-') as server_dir:
        env = await WorkflowEnvironment.start_local(download_dest_dir=server_dir, ui=False,
            dev_server_existing_path=temporal_cli)
        try:
            client = env.client
            async with Worker(client, task_queue='p0e4-disposable', workflows=[ControlPlaneTask],
                activities=[production_evidence, act_long, act_verify_approval],
                workflow_runner=UnsandboxedWorkflowRunner(), max_concurrent_activities=1):
                async def dispatch(task, job_id):
                    wid = 'p0e4-'+job_id
                    payload = dict(task, job_id=job_id, human_gate_required=False, long_seconds=0)
                    try:
                        handle = await client.start_workflow(ControlPlaneTask.run, payload, id=wid,
                            task_queue='p0e4-disposable', id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
                    except WorkflowAlreadyStartedError:
                        handle = client.get_workflow_handle(wid)
                    result = await asyncio.wait_for(handle.result(), 60)
                    if result.get('status') != 'COMPLETED': raise ValueError('workflow not completed')
                    description = await handle.describe()
                    workflows[task['task_id']] = {'workflow_id':wid, 'run_id':description.run_id,
                                                  'status':result['status']}
                    # Require the real activity's durable output; never substitute a synthetic result.
                    target = output/'effects'/(task['task_id']+'.json')
                    content = target.read_bytes()
                    if json.loads(content)['job_id'] != job_id: raise ValueError('job mismatch')
                    return {'evidence':[target.name+'#sha256='+h.digest(content)]}
                running = asyncio.get_running_loop()
                loop.executor = lambda t,j,n: asyncio.run_coroutine_threadsafe(dispatch(t,j),running).result(90)
                gate = await client.start_workflow(ControlPlaneTask.run,
                    {'task_id':'TEST_ONLY_PUBLISH_GATE','human_gate_required':True,
                     'required_gate':'NITIN_PUBLISH_APPROVAL','content_fingerprint':'TEST_ONLY',
                     'input_hash':'TEST_ONLY','state_version':1},
                    id='p0e4-test-only-human-wait',task_queue='p0e4-disposable')
                for _ in range(100):
                    phase = await gate.query(ControlPlaneTask.phase)
                    if phase == 'AWAITING_HUMAN_GATE': break
                    await asyncio.sleep(.1)
                else: raise ValueError('gate failed to park')
                await asyncio.to_thread(loop.run)
                before = len(INVOCATIONS)
                task = loop.backlog.by_id('AKI_PACKAGE_DRAFT')
                jid = loop._recorded_job_id(task['task_id'])
                await dispatch(task,jid)
                duplicate_dispatch_no_activity = len(INVOCATIONS) == before
                if not duplicate_dispatch_no_activity: raise ValueError('duplicate activity')
                if await gate.query(ControlPlaneTask.phase) != 'AWAITING_HUMAN_GATE':
                    raise ValueError('gate did not remain parked')
                await gate.cancel()  # only this disposable TEST_ONLY workflow; no approval signal
                try: await gate.result()
                except Exception: pass
                replay,detail = h.verify_replay(loop.ledger,loop.persisted_state(),keyring={})
                if not replay: raise ValueError(detail)
                report = {'real_temporal_observed':True,'workflow_type':'frozen ControlPlaneTask',
                    'workflows':workflows, 'duplicate_dispatch_no_activity':duplicate_dispatch_no_activity,
                    'test_only_wait_nonblocking':True,'real_release_status':'BLOCKED',
                    'publication_side_effect_count':0,'approval_signals_sent':0,
                    'replay_verified':True,'backlog_summary':loop.backlog.summary(),
                    'live_shared_drive_runtime_persistence':False}
        finally:
            await env.shutdown()
        report['disposable_server_shutdown'] = True
        (output/'INTEGRATION.json').write_text(json.dumps(report,indent=2))
        return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--media',required=True); p.add_argument('--out',required=True)
    p.add_argument('--temporal-cli')
    args=p.parse_args()
    package=release.build(json.loads(Path(args.media).read_text()))
    print(json.dumps(asyncio.run(run(package,args.out,args.temporal_cli)),indent=2))
