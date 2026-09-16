"""DEFECT-2 fix: emit evidence JSON with REAL Python booleans via json.dump. Values arrive as strings
(env) and are converted to bool here — never interpolated as bare tokens into Python. Used by the live
workflow to write failure_injection.json and poc_infra.json with the exact types acceptance_gate.py needs."""
import os, json, sys
FI_BOOLS=["worker_kill_observed","worker_recovery_observed","postgres_restart_observed",
          "temporal_restart_observed","temporal_recovery_observed","execution_recovered"]
def to_bool(v):
    if isinstance(v,bool): return v
    return str(v).strip().lower()=="true"
def write_failure_injection(path, obs):
    fi={k:to_bool(obs.get(k)) for k in FI_BOOLS}
    fi["timestamps"]={"worker_kill":obs.get("worker_kill_ts",""),"worker_recovery":obs.get("worker_recovery_ts",""),
                      "duplicate_dispatch":obs.get("duplicate_dispatch_ts","")}
    json.dump(fi, open(path,"w"), indent=2); return fi
def write_poc(path, remaining):
    d={"POC_INFRA_REMAINING": to_bool(remaining)}; json.dump(d, open(path,"w"), indent=2); return d
def _env(*names): return {n.lower(): os.environ.get(n,"") for n in names}
def main(argv):
    cmd=argv[0] if argv else ""
    out=argv[argv.index("--out")+1] if "--out" in argv else None
    if cmd=="failure_injection":
        obs={k:os.environ.get("FI_"+k.upper(),"false") for k in FI_BOOLS}
        obs.update({"worker_kill_ts":os.environ.get("FI_WORKER_KILL_TS",""),
                    "worker_recovery_ts":os.environ.get("FI_WORKER_RECOVERY_TS",""),
                    "duplicate_dispatch_ts":os.environ.get("FI_DUPLICATE_DISPATCH_TS","")})
        print(json.dumps(write_failure_injection(out, obs)))
    elif cmd=="poc":
        print(json.dumps(write_poc(out, os.environ.get("POC_INFRA_REMAINING","false"))))
    else:
        raise SystemExit("usage: evidence_json.py [failure_injection|poc] --out PATH")
if __name__=="__main__":
    main(sys.argv[1:])
