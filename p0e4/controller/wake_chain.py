"""Verify one observed scheduler-to-CLI chain; no general always-on claim."""
import json
import tempfile
from pathlib import Path
from datetime import datetime
from jsonschema import Draft202012Validator
from integration.contracts import require, verify_refs, digest, canonical
from controller.engineering import projection
from control_plane.ledger import EventLedger


def verify_chain(receipt, resolver):
    require(receipt['trigger']=='ACTUAL_NATIVE_HEARTBEAT' and receipt['idle_to_wake_observed'] is True,'actual wake required')
    require(receipt['always_on_dispatcher_proven'] is False and receipt['publication_authorized'] is False,'scope escalation')
    require(receipt['restart_dispatches']==0 and receipt['runtime_ledgers_unchanged_on_restart'] is True,'duplicate dispatch')
    refs=receipt['refs'];verify_refs(list(refs.values()),resolver)
    require(set(refs)=={'completion','events','exit','ledger','state','schema','validation','prior_next_ready','task','regression'},'chain refs')
    get=lambda k:json.loads(resolver(refs[k]['uri']))
    completion=get('completion');task=get('task')
    require(completion['status']=='COMPLETED' and completion['task_id']==task['task_id'],'completion identity')
    require(completion['task_sha256']==digest(canonical(task)),'task hash')
    require(any(t['task_id']==task['task_id'] and t['status']=='READY' for t in get('prior_next_ready')['tasks']),'task not previously READY')
    require(completion['events_sha256']==refs['events']['sha256'] and completion['exit_sha256']==refs['exit']['sha256'],'execution hash')
    require(get('exit')['exit_code']==0 and get('exit')['terminated'] is True,'execution failed')
    events=[json.loads(x) for x in resolver(refs['events']['uri']).splitlines() if x.strip()]
    require(any(e['type']=='thread.started' and e['thread_id']==completion['thread_id'] for e in events),'thread identity')
    require(any(e['type']=='turn.completed' for e in events),'turn incomplete')
    require(refs['schema']['sha256']==completion['outputs'][refs['schema']['uri']],'output hash')
    schema=get('schema');Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(get('validation'))
    regression=get('regression');require(regression['passed']==regression['total'] and regression['total']>0 and regression['tested_sha']==completion['commit'],'candidate regression')
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'ledger';path.write_bytes(resolver(refs['ledger']['uri']));ledger=EventLedger(str(path))
        require(projection(ledger)==get('state'),'runtime reducer drift')
        records=ledger.read_all()
    phases=[r['inputs']['phase'] for r in records]
    require(phases[0]=='CLAIMED' and phases[-1]=='COMPLETED' and phases.count('RUNNING')==1 and 'HEARTBEAT' in phases and 'VERIFIED' in phases,'lifecycle incomplete')
    require(datetime.fromisoformat(receipt['trigger_at'].replace('Z','+00:00'))<=datetime.fromisoformat(records[0]['timestamp'].replace('Z','+00:00')),'dispatch before wake')
    require(all(records[-1]['inputs'].get(k)==v for k,v in completion.items()),'ledger completion drift')
    return dict(status='PASS',scope='ONE_NATIVE_WAKE_ONE_ALLOWLISTED_CLI_TASK',task_id=completion['task_id'],thread_id=completion['thread_id'],commit=completion['commit'],heartbeat_count=phases.count('HEARTBEAT'),runtime_replay=True,schema_validation=True,duplicate_dispatches=0,always_on_dispatcher_proven=False)
