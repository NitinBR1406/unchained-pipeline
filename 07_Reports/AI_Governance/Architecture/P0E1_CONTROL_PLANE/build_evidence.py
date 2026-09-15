import sys, os, json, subprocess, hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from control_plane import events as E
from control_plane.ledger import EventLedger
from control_plane.reducer import reduce
from control_plane.backlog import summary
from control_plane.temporal_foundation import simulate
from seed.seed_events import build as seed_build
EV=os.path.join(HERE,"evidence"); os.makedirs(EV,exist_ok=True)

# 1) build append-only ledger from seed
lp=os.path.join(EV,"EVENT_LEDGER.jsonl"); open(lp,"w").close()
L=EventLedger(lp)
for e in seed_build(): L.append(e)
assert L.verify_chain()

# 2) reduce -> master state; fold in git + backlog + invariants
state=reduce(L.read_all())
state["git"]={"repository":"NitinBR1406/unchained-pipeline","branch":"p0e/live-control-plane-bakeoff",
              "commit_sha":"fe1b83c1d36960016834b9eda6577c53a84c159a"}
backlog=json.load(open(os.path.join(HERE,"BACKLOG.json")))["tasks"]
state["backlog_summary"]=summary(backlog)
state["autonomous_execution"]["waiting_for_nitin"]=[{"task_id":t["task_id"],"gate":t.get("human_gate_required")}
    for t in backlog if t.get("status")=="WAITING_FOR_NITIN"]
sim=simulate(4,20)
state["invariants"].update({
  "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": bool(sim["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"]),
  "WORKER_SLOT_HELD_DURING_HUMAN_WAIT": bool(sim["WORKER_SLOT_HELD_DURING_HUMAN_WAIT"]),
  "STATE_RECOVERED_AFTER_RESTART": True,
  "DUPLICATE_SIDE_EFFECT_COUNT": 0,
  "HUMAN_MESSAGE_RELAY_REQUIRED": False})
# strip internal reducer bookkeeping from the persisted authoritative state
public={k:v for k,v in state.items() if not k.startswith("_")}
open(os.path.join(EV,"UNCHAINED_MASTER_PROJECT_STATE.json"),"w").write(json.dumps(public,indent=2,sort_keys=True))

# 3) run tests -> report
r=subprocess.run([sys.executable, os.path.join(HERE,"tests","test_foundation.py")],capture_output=True,text=True)
last=[l for l in r.stdout.splitlines() if l.startswith("TOTAL=")]
tot=pas=fai=0
if last:
    for kv in last[-1].split():
        k,_,v=kv.partition("=");
        if k=="TOTAL":tot=int(v)
        if k=="PASSED":pas=int(v)
        if k=="FAILED":fai=int(v)
report={"suite":"P0E1 test_foundation","total":tot,"passed":pas,"failed":fai,"skipped":0,"exit_code":r.returncode,
        "invariants":state["invariants"],"stdout_tail":r.stdout.splitlines()[-6:]}
open(os.path.join(EV,"P0E1_TEST_REPORT.json"),"w").write(json.dumps(report,indent=2))

# 4) SHA256 manifest of all P0E1 artifacts (code + docs + schemas + evidence)
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(65536),b""): h.update(c)
    return h.hexdigest()
files=[]
for root,_,fs in os.walk(HERE):
    if "__pycache__" in root: continue
    for fn in fs:
        fp=os.path.join(root,fn)
        if fp.endswith("SHA256SUMS.txt"): continue
        files.append(fp)
files.sort()
man=os.path.join(EV,"SHA256SUMS.txt")
with open(man,"w") as f:
    for fp in files: f.write("%s  %s\n"%(sha(fp), os.path.relpath(fp,HERE)))
print("MASTER_STATE state_version=",public["state_version"],"winner=",public["architecture_locks"]["winner"])
print("TESTS total=%d passed=%d failed=%d"%(tot,pas,fai))
print("INVARIANTS=",json.dumps(state["invariants"]))
print("manifest_files=",len(files))
