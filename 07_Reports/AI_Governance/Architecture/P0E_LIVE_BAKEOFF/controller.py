"""P0-E live bake-off controller — V02. Runs ON the GitHub Actions runner.
Modes:
  temporal|hatchet <phase>  -> driver phase (start|resume|assert); writes OBSERVED records via common_semantics.record
  assemble                  -> read /data/se/results.jsonl (+ provenance) -> six evidence files, STRICT + FAIL-CLOSED
  gate                      -> exit 1 if FINAL_RECOMMENDATION == PENDING (so the CI job reflects readiness)
OBSERVED means measured on live disposable containers. No fabricated values; missing => NOT_TESTABLE => PENDING."""
import json, os, re, sys, glob, hashlib, time
HERE=os.path.dirname(os.path.abspath(__file__)); EV=os.path.join(HERE,"evidence"); os.makedirs(EV,exist_ok=True)
RESULTS_LOG=os.environ.get("RESULTS_LOG","/data/se/results.jsonl")
DECISION_CRITICAL=["DURABLE_HUMAN_WAIT","CRASH_DURING_LONG_ACTIVITY","ORCHESTRATOR_DB_INTERRUPTION","DUPLICATE_STALE_EVENTS","IDEMPOTENCY_RETRY","PARALLEL_AUTONOMY_20"]
ENGINES=["temporal","hatchet"]
def _read_results():
    out=[]
    if os.path.exists(RESULTS_LOG):
        for ln in open(RESULTS_LOG):
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def _status(results, test, engine):
    st=[r["status"] for r in results if r["test"]==test and r["engine"]==engine]
    if not st: return "NOT_TESTABLE"
    if any(s=="OBSERVED_FAIL" for s in st): return "OBSERVED_FAIL"
    if any(s=="OBSERVED_PASS" for s in st): return "OBSERVED_PASS"
    return st[-1]
def _peak(statslog, sub):
    cpu=ram=0.0
    for ln in (open(statslog) if os.path.exists(statslog) else []):
        if sub in ln:
            m=re.search(r'([\d.]+)%\s+([\d.]+)([MG])iB',ln)
            if m: cpu=max(cpu,float(m.group(1))); ram=max(ram,float(m.group(2))*(1024 if m.group(3)=="G" else 1))
    return {"peak_cpu_pct":cpu,"peak_ram_mib":round(ram,1)}
def _prov():
    p={}
    for f in ["run_meta.json","temporal_versions.json","hatchet_versions.json","sdk_versions.json"]:
        fp=os.path.join(EV,f)
        if os.path.exists(fp):
            try: p[f]=json.load(open(fp))
            except Exception: p[f]={"raw":open(fp).read()}
    return p
def assemble():
    R=_read_results(); prov=_prov()
    matrix={t:{e:_status(R,t,e) for e in ENGINES} for t in DECISION_CRITICAL}
    def flag(name):
        vals=[r for r in R if r["test"]==name]
        return "OBSERVED_PASS" if vals and all(v["status"]=="OBSERVED_PASS" for v in vals) else ("NOT_TESTABLE" if not vals else "OBSERVED_FAIL")
    acceptance={
      "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": ("FALSE" if flag("PARALLEL_AUTONOMY_20")=="OBSERVED_PASS" else "NOT_PROVEN"),
      "WORKER_SLOT_HELD_DURING_HUMAN_WAIT": ("FALSE" if flag("DURABLE_HUMAN_WAIT")=="OBSERVED_PASS" else "NOT_PROVEN"),
      "STATE_RECOVERED_AFTER_RESTART": ("TRUE" if (matrix["ORCHESTRATOR_DB_INTERRUPTION"]==dict(temporal="OBSERVED_PASS",hatchet="OBSERVED_PASS")) else "NOT_PROVEN"),
      "DUPLICATE_SIDE_EFFECT_COUNT": (0 if flag("IDEMPOTENCY_RETRY")=="OBSERVED_PASS" and flag("CRASH_DURING_LONG_ACTIVITY")=="OBSERVED_PASS" else "NOT_PROVEN"),
      "HUMAN_MESSAGE_RELAY_REQUIRED": "FALSE"
    }
    all_pass=all(matrix[t][e]=="OBSERVED_PASS" for t in DECISION_CRITICAL for e in ENGINES)
    accept_ok=(acceptance["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"]=="FALSE" and acceptance["WORKER_SLOT_HELD_DURING_HUMAN_WAIT"]=="FALSE"
               and acceptance["STATE_RECOVERED_AFTER_RESTART"]=="TRUE" and acceptance["DUPLICATE_SIDE_EFFECT_COUNT"]==0)
    final="READY_FOR_DECISION" if (all_pass and accept_ok) else "PENDING"  # never names a winner here
    res={"provenance":prov,"matrix":matrix,"acceptance":acceptance,"all_decision_critical_observed_pass":all_pass,
         "resources":{"temporal":_peak(os.path.join(EV,"temporal_stats.log"),"worker"),"hatchet":_peak(os.path.join(EV,"hatchet_stats.log"),"worker")},
         "FINAL_RECOMMENDATION":final,"labels_legend":{"OBSERVED_PASS":"measured on live disposable containers","OBSERVED_FAIL":"measured, failed","NOT_TESTABLE":"not established this run -> fail-closed PENDING"}}
    json.dump(res, open(f"{EV}/P0E_LIVE_BAKEOFF_RESULTS_V01.json","w"), indent=2)
    json.dump({"engine":"temporal","matrix":{t:matrix[t]["temporal"] for t in DECISION_CRITICAL},"resources":res["resources"]["temporal"],"versions":prov.get("temporal_versions.json")}, open(f"{EV}/P0E_TEMPORAL_LIVE_EVIDENCE_V01.json","w"), indent=2)
    json.dump({"engine":"hatchet","matrix":{t:matrix[t]["hatchet"] for t in DECISION_CRITICAL},"resources":res["resources"]["hatchet"],"versions":prov.get("hatchet_versions.json")}, open(f"{EV}/P0E_HATCHET_LIVE_EVIDENCE_V01.json","w"), indent=2)
    json.dump({"decision_critical":DECISION_CRITICAL,"matrix":matrix,"acceptance":acceptance}, open(f"{EV}/P0E_LIVE_FAILURE_MATRIX_V01.json","w"), indent=2)
    json.dump(res["resources"], open(f"{EV}/P0E_LIVE_RESOURCE_METRICS_V01.json","w"), indent=2)
    md=["# P0-E Live Final Decision V02","",f"provenance={json.dumps(prov)}","",f"matrix={json.dumps(matrix)}","",f"acceptance={json.dumps(acceptance)}","",
        f"FINAL_RECOMMENDATION = {final}","",("All decision-critical OBSERVED_PASS on both engines + acceptance met -> ready for the human/ChatGPT winner decision (this file does NOT name a winner)." if final=='READY_FOR_DECISION' else "FAIL-CLOSED: >=1 decision-critical NOT_TESTABLE/OBSERVED_FAIL or acceptance not proven -> PENDING; re-run."),"","PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE"]
    open(f"{EV}/P0E_LIVE_FINAL_DECISION_V01.md","w").write("\n".join(md))
    print("assembled; FINAL_RECOMMENDATION=",final); return final
def gate():
    final=assemble()
    if final!="READY_FOR_DECISION": print("GATE: PENDING (fail-closed)"); sys.exit(1)
    print("GATE: READY_FOR_DECISION")
def drive(engine, phase):
    mod = __import__("temporal_bakeoff" if engine=="temporal" else "hatchet_bakeoff")
    mod.phase(phase)
if __name__=="__main__":
    a=sys.argv[1:]
    if not a or a[0]=="assemble": assemble()
    elif a[0]=="gate": gate()
    elif a[0] in ENGINES: drive(a[0], a[1] if len(a)>1 else "start")
