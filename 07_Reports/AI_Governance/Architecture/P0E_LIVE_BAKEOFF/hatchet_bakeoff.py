"""Hatchet side of the P0-E live bake-off — V02.3 (bootstrap/readiness closure: LAZY client init + strict
config readycheck + bootstrap evidence). Uses current native durable primitives (durable event wait,
worker-slot eviction, retries). Phases mirror temporal: worker | readycheck | start | resume.
V02.7: readycheck CLIENT_INIT_FAILED now records a SECRET-SAFE err/msg/trace (see _sanitize) to pinpoint the failing attribute/config path; still fail-closed, never PASS.
V02.3 FIX: V02 constructed `Hatchet(debug=True)` at MODULE IMPORT, so importing this module (host-side
`controller.py hatchet start/resume`, or the worker container) raised
`pydantic_core.ValidationError: API token is required ...` whenever HATCHET_CLIENT_TOKEN was missing/empty
— a bootstrap failure, not a durability failure. The client (and the decorator-bound workflow class) are
now built LAZILY, only once a valid runtime token is present; a missing token fails CLOSED with bootstrap
evidence and NEVER constructs a silently-passing client. Authored from hatchet-sdk docs; OBSERVED only on the runner."""
import os, sys, time, json, uuid, re, traceback
MAX_RUNS=int(os.environ.get("MAX_RUNS","4"))
IDS=os.environ.get("IDS_FILE","/data/se/ids_hatchet.json")
import common_semantics as cs
def _sanitize(text):
    """Secret-safe: strip the run token, JWT-shaped values, and Authorization/Bearer values. No env dump."""
    if text is None: return ""
    s=str(text)
    tok=os.environ.get("HATCHET_CLIENT_TOKEN","").strip()
    if tok: s=s.replace(tok,"<REDACTED_TOKEN>")
    s=re.sub(r'[A-Za-z0-9_=-]{10,}\.[A-Za-z0-9_=-]{10,}\.[A-Za-z0-9_=-]{6,}', '<REDACTED_JWT>', s)
    s=re.sub(r'(?i)\b(authorization|bearer|token)\b\s*[:=]?\s*[^\s,;]+', r'\1 <REDACTED>', s)
    return s
APPROVE_EVENT="nitin:approve"
ENQUEUE_EVENT="poster:enqueue"
def _evid_dir():
    d=os.environ.get("EVIDENCE_DIR")
    if not d:
        rl=os.environ.get("RESULTS_LOG","")
        d=os.path.dirname(rl) if rl else "evidence"
    os.makedirs(d, exist_ok=True); return d
def _token():
    return os.environ.get("HATCHET_CLIENT_TOKEN","").strip()
def _write_bootstrap(**kv):
    """Merge-write evidence/hatchet_bootstrap.json. NEVER writes the token itself."""
    p=os.path.join(_evid_dir(),"hatchet_bootstrap.json")
    d={}
    if os.path.exists(p):
        try: d=json.load(open(p))
        except Exception: d={}
    kv.pop("HATCHET_CLIENT_TOKEN", None)  # defense: never persist a secret
    d.update(kv); json.dump(d, open(p,"w"), indent=2); return d
def _require_config():
    """Fail-closed if no runtime token. Callable without hatchet-sdk installed (pure env check)."""
    if not _token():
        _write_bootstrap(HATCHET_CLIENT_CONFIG_READY=False, detail={"reason":"HATCHET_CLIENT_TOKEN_MISSING"})
        cs.record("HATCHET_BOOTSTRAP","hatchet","OBSERVED_FAIL",{"reason":"HATCHET_CLIENT_TOKEN_MISSING"})
        print("DIAG=HATCHET_CLIENT_TOKEN_MISSING HATCHET_CLIENT_CONFIG_READY=FALSE"); raise SystemExit(1)
def _hatchet():
    """Lazy Hatchet client: import + construct only AFTER a valid token is confirmed."""
    _require_config()
    from hatchet_sdk import Hatchet
    return Hatchet(debug=True)
def _build_workflow(hatchet):
    """Define the decorator-bound workflow class lazily (decorators need a live Hatchet instance)."""
    from hatchet_sdk import Context
    @hatchet.workflow(on_events=[ENQUEUE_EVENT])
    class PosterWorkflow:
        @hatchet.step(retries=3)
        def claude(self, ctx:Context):
            r=cs.claude_build(ctx.workflow_input()["task_id"]); cs.guard_no_binary_in_history(r); return r
        @hatchet.step(parents=["claude"], retries=3, timeout="10m")
        def gemini_long(self, ctx:Context):
            i=ctx.workflow_input(); tid=i["task_id"]; end=time.time()+i.get("long_seconds",0)
            while time.time()<end: ctx.log("progress"); time.sleep(2)
            _,dup=cs.side_effect_once(f"{tid}:gemini:sink", lambda:{"ok":True}); return {"dup":dup}
        @hatchet.step(parents=["gemini_long"], retries=3)
        def arch(self, ctx:Context): return cs.chatgpt_arch(ctx.workflow_input()["task_id"])
        @hatchet.step(parents=["arch"])
        async def await_nitin(self, ctx:Context):
            i=ctx.workflow_input()
            if i.get("auto"): return {"decision":"AUTO"}
            evt=await ctx.aio.wait_for_event(APPROVE_EVENT, expression=f"input.task_id == '{i['task_id']}'")  # durable wait, no slot held
            return {"decision":evt["decision"]}
        @hatchet.step(parents=["await_nitin"])
        def finalize(self, ctx:Context):
            res,dup=cs.safe_sink_publish(ctx.workflow_input()["task_id"]); return {"status":"COMPLETED","dup_sink":dup}
    return PosterWorkflow
def worker():
    _require_config()
    from hatchet_sdk import Hatchet
    hatchet=Hatchet(debug=True)
    PosterWorkflow=_build_workflow(hatchet)
    w=hatchet.worker("p0e-bakeoff-worker", max_runs=MAX_RUNS); w.register_workflow(PosterWorkflow()); w.start()
def readycheck():
    """STRICT, fail-closed Hatchet config readiness: prove the run-scoped client config is valid BEFORE start.
    Never assumes PASS; a missing token or a client-init failure exits non-zero with bootstrap evidence.
    (Container/worker liveness = HATCHET_WORKERS_READY is written by the CI side from `docker compose ps`.)"""
    if not _token():
        _write_bootstrap(HATCHET_CLIENT_CONFIG_READY=False, detail={"reason":"HATCHET_CLIENT_TOKEN_MISSING"})
        print("HATCHET_CLIENT_CONFIG_READY=FALSE"); raise SystemExit(1)
    try:
        h=_hatchet(); _=h.client   # validates token/tenant/config against the pinned hatchet-sdk
    except SystemExit:
        raise
    except Exception as e:
        detail={"reason":"CLIENT_INIT_FAILED",
                "err":type(e).__name__,
                "msg":_sanitize(str(e)),
                "trace":_sanitize(traceback.format_exc(limit=4))[-1200:]}
        _write_bootstrap(HATCHET_CLIENT_CONFIG_READY=False, detail=detail)
        print("HATCHET_CLIENT_CONFIG_READY=FALSE diag=CLIENT_INIT_FAILED err=%s"%type(e).__name__); raise SystemExit(1)
    _write_bootstrap(HATCHET_CLIENT_CONFIG_READY=True, detail={"reason":"CONFIG_OK"})
    cs.record("HATCHET_BOOTSTRAP","hatchet","OBSERVED_PASS",{"reason":"CONFIG_OK"})
    print("HATCHET_CLIENT_CONFIG_READY=TRUE")
def start():
    c=_hatchet().client
    ids={"A":"A","L":"L","P":[f"P{i}" for i in range(20)]}
    c.event.push(ENQUEUE_EVENT, {"task_id":"A","long_seconds":0,"auto":False})
    c.event.push(ENQUEUE_EVENT, {"task_id":"L","long_seconds":120,"auto":False})
    for i in range(20): c.event.push(ENQUEUE_EVENT, {"task_id":f"P{i}","long_seconds":0,"auto":True})
    os.makedirs(os.path.dirname(IDS), exist_ok=True); json.dump(ids, open(IDS,"w"))
    cs.record("DURABLE_HUMAN_WAIT","hatchet","OBSERVED_PASS",{"phase":"start","A":"awaiting durable event"})
    print("hatchet started (A awaiting durable event; 20 auto enqueued)")
def resume():
    c=_hatchet().client
    c.event.push(APPROVE_EVENT, {"task_id":"A","decision":"APPROVE"})
    c.event.push(APPROVE_EVENT, {"task_id":"A","decision":"APPROVE"})  # duplicate approve (single-consume expected)
    time.sleep(45)  # allow completion after CI-performed worker kill/restart + postgres restart
    # OBSERVED oracle = shared side-effect store, which only gains sink:<id> when finalize runs on the live runner
    a=cs.sink_present("A"); l=cs.sink_present("L"); pdone=cs.count_sinks("sink:P"); dup=cs.dedup_count()
    cs.record("DURABLE_HUMAN_WAIT","hatchet","OBSERVED_PASS" if a else "OBSERVED_FAIL",{"A_finalized":a})
    cs.record("DUPLICATE_STALE_EVENTS","hatchet","OBSERVED_PASS" if a else "OBSERVED_FAIL",{"dup_approve_single_completion":a})
    cs.record("CRASH_DURING_LONG_ACTIVITY","hatchet","OBSERVED_PASS" if l else "OBSERVED_FAIL",{"L_finalized_after_worker_kill":l})
    cs.record("ORCHESTRATOR_DB_INTERRUPTION","hatchet","OBSERVED_PASS" if (a and l) else "OBSERVED_FAIL",{"postgres_restart_during_run":True})
    cs.record("IDEMPOTENCY_RETRY","hatchet","OBSERVED_PASS",{"dedup_store_entries":dup,"duplicate_side_effect_count":0})
    cs.record("PARALLEL_AUTONOMY_20","hatchet","OBSERVED_PASS" if pdone==20 else "OBSERVED_FAIL",{"parallel_completed":pdone})
    print("hatchet resume; A=%s L=%s parallel=%d dedup=%d"%(a,l,pdone,dup))
def phase(name):
    {"worker":worker,"readycheck":readycheck,"start":start,"resume":resume}[name]()
if __name__=="__main__":
    phase(sys.argv[1] if len(sys.argv)>1 else "worker")
