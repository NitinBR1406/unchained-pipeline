"""Hatchet side of the P0-E live bake-off. Authored from Hatchet Python SDK / self-host docs; NOT
executed in the sandbox. Run on a Docker-capable host after `docker compose -f docker-compose.hatchet.yml
up -d`, issue a client token from the dashboard (:8888), `export HATCHET_CLIENT_TOKEN=...`, and
`pip install hatchet-sdk`.

Usage:
  python hatchet_bakeoff.py --worker    # run the worker (start >=2 for parallel-autonomy test)
  python hatchet_bakeoff.py --tests     # drive programmatic tests; do kill/restart steps per README
Uses Hatchet's CURRENT native durable primitives: durable tasks, durable sleep, WaitForEvent, worker-slot
eviction, retries. Mock agents, safe sink, explicit idempotency. Never touches P1/177455/verifier/creds.
"""
import sys, time, uuid
import common_semantics as cs
from hatchet_sdk import Hatchet, Context

hatchet = Hatchet(debug=True)
APPROVE_EVENT = "nitin:approve"   # durable event key; payload carries {task_id, decision, token}

@hatchet.workflow(on_events=["poster:enqueue"])
class PosterWorkflow:
    @hatchet.step(retries=3)
    def claude(self, ctx: Context):
        r = cs.claude_build(ctx.workflow_input()["task_id"]); cs.guard_no_binary_in_history(r); return r

    @hatchet.step(parents=["claude"], retries=3, timeout="10m")
    def gemini_long(self, ctx: Context):
        tid = ctx.workflow_input()["task_id"]; secs = ctx.workflow_input().get("long_seconds", 0)
        end = time.time() + secs
        while time.time() < end:
            ctx.log("progress"); time.sleep(2)   # heartbeat/progress; worker-kill mid-step -> re-run on another slot
        _, dup = cs.side_effect_once(f"{tid}:gemini:sink", lambda: {"ok": True})  # explicit idempotency (no exactly-once assumed)
        r = cs.gemini_creative(tid, cs.MOCK_ASSET_SHA); r["_dup_side_effect"] = dup; return r

    @hatchet.step(parents=["gemini_long"], retries=3)
    def arch(self, ctx: Context):
        return cs.chatgpt_arch(ctx.workflow_input()["task_id"])

    # DURABLE HUMAN WAIT via native durable event; no worker slot held while waiting
    @hatchet.step(parents=["arch"])
    async def await_nitin(self, ctx: Context):
        tid = ctx.workflow_input()["task_id"]
        evt = await ctx.aio.wait_for_event(APPROVE_EVENT, expression=f"input.task_id == '{tid}'")  # durable wait (days ok)
        return {"decision": evt["decision"], "token": evt["token"]}

    @hatchet.step(parents=["await_nitin"])
    def finalize(self, ctx: Context):
        d = ctx.step_output("await_nitin")
        if d["decision"] == "REJECT": return {"task_id": ctx.workflow_input()["task_id"], "status": "GATE_REJECTED"}
        res, dup = cs.safe_sink_publish(ctx.workflow_input()["task_id"])   # safe sink; idempotent
        return {"task_id": ctx.workflow_input()["task_id"], "status": "COMPLETED", "dup_sink": dup}

def worker():
    w = hatchet.worker("p0e-bakeoff-worker", max_runs=5)
    w.register_workflow(PosterWorkflow()); w.start()

def tests():
    c = hatchet.client
    # T1 durable human wait
    c.event.push("poster:enqueue", {"task_id": "T-wait", "long_seconds": 0})
    time.sleep(5)  # (kill+restart worker per README), then:
    c.event.push(APPROVE_EVENT, {"task_id": "T-wait", "decision": "APPROVE", "token": "TOK"})
    c.event.push(APPROVE_EVENT, {"task_id": "T-wait", "decision": "APPROVE", "token": "TOK"})  # dup approve (single-consume)
    # T2 crash-during-long-activity
    c.event.push("poster:enqueue", {"task_id": "T-long", "long_seconds": 180})
    print("started long run -> hard-kill worker mid gemini_long, restart; confirm resume + dup_side_effect False")
    # T5 parallel autonomy
    for i in range(20):
        c.event.push("poster:enqueue", {"task_id": f"P{i}", "long_seconds": 0})
    print("started 20 parallel; measure via Hatchet dashboard :8888 and docker stats")

if __name__ == "__main__":
    (worker if "--worker" in sys.argv else tests)()
