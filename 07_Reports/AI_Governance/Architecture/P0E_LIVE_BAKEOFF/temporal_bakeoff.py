"""Temporal side of the P0-E live bake-off. Authored from temporalio Python SDK docs; NOT executed in
the sandbox (no server/registry). Run on a Docker-capable host after `docker compose -f
docker-compose.temporal.yml up -d` and `pip install temporalio`.

Usage:
  python temporal_bakeoff.py --worker     # run the worker (start >=2 for parallel-autonomy test)
  python temporal_bakeoff.py --tests      # drive the programmatic tests; do the kill/restart steps per README
Safety: mock agents, safe sink, explicit idempotency. Never touches P1/177455/verifier/real creds.
"""
import asyncio, os, sys, time, uuid
from datetime import timedelta
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
import common_semantics as cs
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

TASK_QUEUE = "p0e-bakeoff"

@activity.defn
async def a_claude(task_id: str) -> dict:
    r = cs.claude_build(task_id); cs.guard_no_binary_in_history(r); return r

@activity.defn
async def a_gemini_long(task_id: str, asset_sha: str, seconds: float) -> dict:
    # long multimodal mock with heartbeats so a mid-activity worker kill is detected fast
    end = time.time() + seconds
    while time.time() < end:
        activity.heartbeat("progress")
        await asyncio.sleep(2)
    _, dup = cs.side_effect_once(f"{task_id}:gemini:sink", lambda: {"ok": True})  # explicit idempotency
    r = cs.gemini_creative(task_id, asset_sha); r["_dup_side_effect"] = dup; cs.guard_no_binary_in_history({"k":"v"}); return r

@activity.defn
async def a_arch(task_id: str) -> dict:
    return cs.chatgpt_arch(task_id)

@activity.defn
async def a_safe_sink(task_id: str) -> dict:
    res, dup = cs.safe_sink_publish(task_id); return {"res": res, "dup": dup}

@workflow.defn
class PosterWorkflow:
    def __init__(self): self._decision = None
    @workflow.signal
    def approve(self, token: str):
        if self._decision is None: self._decision = ("APPROVE", token)   # first wins (dup-approve safe)
    @workflow.signal
    def reject(self, token: str):
        if self._decision is None: self._decision = ("REJECT", token)
    @workflow.query
    def state(self) -> str: return "AWAITING_HUMAN_GATE" if self._decision is None else self._decision[0]

    @workflow.run
    async def run(self, task_id: str, long_seconds: float = 0.0) -> dict:
        rp = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(a_claude, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        await workflow.execute_activity(a_gemini_long, args=[task_id, cs.MOCK_ASSET_SHA, long_seconds],
                                        start_to_close_timeout=timedelta(minutes=10),
                                        heartbeat_timeout=timedelta(seconds=10), retry_policy=rp)
        await workflow.execute_activity(a_arch, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        # DURABLE HUMAN WAIT (survives worker/server restart; no worker slot held)
        await workflow.wait_condition(lambda: self._decision is not None)
        if self._decision[0] == "REJECT": return {"task_id": task_id, "status": "GATE_REJECTED"}
        await workflow.execute_activity(a_safe_sink, task_id, start_to_close_timeout=timedelta(minutes=1), retry_policy=rp)
        return {"task_id": task_id, "status": "COMPLETED"}

async def worker():
    client = await Client.connect(TEMPORAL_ADDRESS)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[PosterWorkflow],
                      activities=[a_claude, a_gemini_long, a_arch, a_safe_sink]):
        print("temporal worker up"); await asyncio.Future()

async def tests():
    client = await Client.connect(TEMPORAL_ADDRESS)
    # T1 durable human wait: start, (kill+restart worker per README), then approve
    h = await client.start_workflow(PosterWorkflow.run, args=["T-wait", 0.0], id="wf-wait-"+uuid.uuid4().hex[:6], task_queue=TASK_QUEUE)
    await asyncio.sleep(5); print("state before approve:", await h.query(PosterWorkflow.state))
    await h.signal(PosterWorkflow.approve, "TOK"); await h.signal(PosterWorkflow.approve, "TOK")  # dup approve
    print("result:", await h.result())
    # T2 crash-during-long-activity: start with long_seconds=180, hard-kill worker mid-run (README), observe resume + dup==False
    h2 = await client.start_workflow(PosterWorkflow.run, args=["T-long", 180.0], id="wf-long-"+uuid.uuid4().hex[:6], task_queue=TASK_QUEUE)
    print("started long workflow", h2.id, "-> kill worker now, then restart; then signal approve")
    # T5 parallel autonomy: 20 independent workflows while one awaits
    for i in range(20):
        await client.start_workflow(PosterWorkflow.run, args=[f"P{i}", 0.0], id=f"wf-par-{i}-"+uuid.uuid4().hex[:4], task_queue=TASK_QUEUE)
    print("started 20 parallel; measure via Temporal UI :8233 and docker stats")

if __name__ == "__main__":
    asyncio.run(worker() if "--worker" in sys.argv else tests())
