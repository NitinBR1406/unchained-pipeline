"""Offline bounded worker-readiness test for P0E1-TEMPORAL-LIVE-WIRE.
Builds a throwaway stub `temporalio` so it runs WITHOUT the real SDK, and proves ONLY the bounded
connect/namespace-ready retry + fail-closed behavior of temporal_live._connect_ready. It does NOT simulate
a passing live acceptance test. Place at tests/test_worker_readiness.py; run from the harness root."""
import os, sys, asyncio, tempfile, textwrap
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
# --- build a throwaway stub `temporalio` (import-time surface only; behavior controlled via env) ---
_stub=tempfile.mkdtemp(prefix="temporalio_stub_")
def _w(rel, body):
    p=os.path.join(_stub,rel); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,"w").write(textwrap.dedent(body))
_w("temporalio/__init__.py","""
    class _WF:
        def defn(self,c=None,**k): return c if c else (lambda x:x)
        def signal(self,f=None,**k): return f if f else (lambda x:x)
        def query(self,f=None,**k): return f if f else (lambda x:x)
        def run(self,f): return f
    workflow=_WF()
    class _ACT:
        def defn(self,f=None,**k): return f if f else (lambda x:x)
        def heartbeat(self,*a,**k): pass
    activity=_ACT()
""")
_w("temporalio/worker.py","""
    class Worker:
        def __init__(self,*a,**k): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): return False
""")
_w("temporalio/client.py","""
    import os
    STATE={"connect_calls":0,"ns_calls":0}
    class _Svc:
        async def describe_namespace(self, req):
            STATE["ns_calls"]+=1
            if STATE["ns_calls"] <= int(os.environ.get("NS_FAIL_UNTIL","0")):
                raise RuntimeError("Namespace default is not found.")
            return object()
    class _Client:
        def __init__(self): self.workflow_service=_Svc()
    class Client:
        @classmethod
        async def connect(cls, addr, **k):
            STATE["connect_calls"]+=1
            if STATE["connect_calls"] <= int(os.environ.get("CONNECT_FAIL_UNTIL","0")):
                raise ConnectionRefusedError("connection refused")
            return _Client()
""")
_w("temporalio/api/__init__.py","")
_w("temporalio/api/workflowservice/__init__.py","")
_w("temporalio/api/workflowservice/v1/__init__.py","""
    class DescribeNamespaceRequest:
        def __init__(self,**k): pass
    class DescribeTaskQueueRequest:
        def __init__(self,**k): pass
""")
sys.path.insert(0,_stub)

os.environ["WORKER_CONNECT_BACKOFF_S"]="0"; os.environ["WORKER_CONNECT_RETRIES"]="10"
import importlib, temporalio.client as C
import control_plane.temporal_live as TL; importlib.reload(TL)
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)

C.STATE.update({"connect_calls":0,"ns_calls":0}); os.environ["CONNECT_FAIL_UNTIL"]="2"; os.environ["NS_FAIL_UNTIL"]="0"
c=asyncio.run(TL._connect_ready()); ok("retries_past_connection_refused", c is not None and C.STATE["connect_calls"]==3)

C.STATE.update({"connect_calls":0,"ns_calls":0}); os.environ["CONNECT_FAIL_UNTIL"]="0"; os.environ["NS_FAIL_UNTIL"]="3"
c=asyncio.run(TL._connect_ready()); ok("tolerates_namespace_not_found_window", c is not None and C.STATE["ns_calls"]==4)

C.STATE.update({"connect_calls":0,"ns_calls":0}); os.environ["CONNECT_FAIL_UNTIL"]="999"; os.environ["NS_FAIL_UNTIL"]="0"
try:
    asyncio.run(TL._connect_ready()); ok("failclosed_when_never_ready",False)
except SystemExit:
    ok("failclosed_when_never_ready", C.STATE["connect_calls"]==10)
ok("bounded_retry_count", C.STATE["connect_calls"]==int(os.environ["WORKER_CONNECT_RETRIES"]))

print("\nWR_TOTAL=%d WR_PASSED=%d WR_FAILED=%d"%(P+F,P,F))
sys.exit(1 if F else 0)
