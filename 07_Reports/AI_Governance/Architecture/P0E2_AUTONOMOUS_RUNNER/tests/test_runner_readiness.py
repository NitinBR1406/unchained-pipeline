"""DEFECT-1: LiveRunner._client() must gate on bounded connect + namespace 'default' readiness (P0-E1
_connect_ready) so a post-restart resume never dispatches before Temporal is ready. Self-contained stub
temporalio; proves eventual-recovery returns a client and never-ready fail-closes (SystemExit)."""
import os, sys, json, asyncio, tempfile, textwrap, shutil
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
_stub=tempfile.mkdtemp(prefix="temporalio_stub_")
def _w(rel,body):
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
_w("temporalio/worker.py","class Worker:\n    def __init__(self,*a,**k): pass\n    async def __aenter__(self): return self\n    async def __aexit__(self,*a): return False\n")
_w("temporalio/client.py","""
    import os
    STATE={"connect":0,"ns":0}
    class _Svc:
        async def describe_namespace(self, req):
            STATE["ns"]+=1
            if STATE["ns"]<=int(os.environ.get("NS_FAIL_UNTIL","0")): raise RuntimeError("Namespace default is not found.")
            return object()
    class _Client:
        def __init__(self): self.workflow_service=_Svc()
    class Client:
        @classmethod
        async def connect(cls, addr, **k):
            STATE["connect"]+=1
            if STATE["connect"]<=int(os.environ.get("CONNECT_FAIL_UNTIL","0")): raise ConnectionRefusedError("refused")
            return _Client()
""")
_w("temporalio/api/__init__.py","")
_w("temporalio/api/workflowservice/__init__.py","")
_w("temporalio/api/workflowservice/v1/__init__.py","class DescribeNamespaceRequest:\n    def __init__(self,**k): pass\nclass DescribeTaskQueueRequest:\n    def __init__(self,**k): pass\n")
sys.path.insert(0,_stub); sys.path.insert(0, ROOT)
os.environ["WORKER_CONNECT_BACKOFF_S"]="0"; os.environ["WORKER_CONNECT_RETRIES"]="8"
import importlib, temporalio.client as C
import temporal_runner as TR
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)
d=tempfile.mkdtemp(); bl=os.path.join(d,"BACKLOG.json"); shutil.copy(os.path.join(ROOT,"seed","backlog_slice2.json"),bl)
r=TR.LiveRunner(bl, os.path.join(d,"L.jsonl"), os.path.join(d,"ev"))  # no client_factory -> real path -> _connect_ready
# eventual recovery: namespace absent 3x then visible -> returns a client (bounded)
C.STATE.update({"connect":0,"ns":0}); os.environ["CONNECT_FAIL_UNTIL"]="1"; os.environ["NS_FAIL_UNTIL"]="3"
cl=asyncio.run(r._client()); ok("post_restart_waits_for_namespace_then_ready", cl is not None and C.STATE["ns"]==4)
# never ready -> fail-closed SystemExit (no swallow, no unbounded loop)
C.STATE.update({"connect":0,"ns":0}); os.environ["CONNECT_FAIL_UNTIL"]="0"; os.environ["NS_FAIL_UNTIL"]="999"
try:
    asyncio.run(r._client()); ok("never_ready_fail_closed", False)
except SystemExit: ok("never_ready_fail_closed", True)
ok("bounded_not_infinite", C.STATE["ns"]<=8)
print("\nRR_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
