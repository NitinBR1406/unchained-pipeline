"""P0-E PER-ENGINE acceptance reducer (ADDITIVE, read-only) — V02.12.
WHY THIS EXISTS: controller.py computes the five top-level acceptance criteria JOINTLY across both engines
(and inconsistently: three via a cross-engine flag(), one via a both-engines matrix equality, one constant),
so a GREEN engine's raw OBSERVED_PASS does not surface on its own while the OTHER engine is still failing
bootstrap/transport. This reducer maps each engine's OWN raw records to the five criteria, PER ENGINE, so
truthful per-engine evidence is visible.

STRICTLY ADDITIVE: read-only over results.jsonl; writes only evidence/P0E_ACCEPTANCE_BY_ENGINE_V01.json;
does NOT change durability semantics, does NOT touch controller.py's joint FAIL-CLOSED gate or
FINAL_RECOMMENDATION, does NOT name a winner, and does NOT reopen the Temporal-vs-Hatchet comparison.
"""
import json, os
RESULTS_LOG=os.environ.get("RESULTS_LOG","/data/se/results.jsonl")
HERE=os.path.dirname(os.path.abspath(__file__)); EV=os.path.join(HERE,"evidence"); os.makedirs(EV,exist_ok=True)
ENGINES=["temporal","hatchet"]
def _read():
    out=[]
    if os.path.exists(RESULTS_LOG):
        for ln in open(RESULTS_LOG):
            ln=ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    return out
def _status(R, test, engine):
    # identical semantics to controller._status, but always scoped to a SINGLE engine
    st=[r["status"] for r in R if r.get("test")==test and r.get("engine")==engine]
    if not st: return "NOT_TESTABLE"
    if any(s=="OBSERVED_FAIL" for s in st): return "OBSERVED_FAIL"
    if any(s=="OBSERVED_PASS" for s in st): return "OBSERVED_PASS"
    return st[-1]
def per_engine_acceptance(R, e):
    P=lambda t: _status(R,t,e)=="OBSERVED_PASS"
    parallel=P("PARALLEL_AUTONOMY_20"); human=P("DURABLE_HUMAN_WAIT")
    return {
      "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": ("FALSE" if parallel else "NOT_PROVEN"),
      # worker-slot measurement closure: the human-gate workflow held NO worker slot IFF the durable wait
      # passed AND the 20 independent workflows still COMPLETED while it waited (measured throughput,
      # not a bare inference from DURABLE_HUMAN_WAIT alone).
      "WORKER_SLOT_HELD_DURING_HUMAN_WAIT": ("FALSE" if (human and parallel) else "NOT_PROVEN"),
      "STATE_RECOVERED_AFTER_RESTART": ("TRUE" if P("ORCHESTRATOR_DB_INTERRUPTION") else "NOT_PROVEN"),
      "DUPLICATE_SIDE_EFFECT_COUNT": (0 if (P("IDEMPOTENCY_RETRY") and P("CRASH_DURING_LONG_ACTIVITY")) else "NOT_PROVEN"),
      "HUMAN_MESSAGE_RELAY_REQUIRED": "FALSE",
    }
def _met(a):
    return (a["WAITING_WORKFLOW_BLOCKS_OTHER_WORK"]=="FALSE" and a["WORKER_SLOT_HELD_DURING_HUMAN_WAIT"]=="FALSE"
            and a["STATE_RECOVERED_AFTER_RESTART"]=="TRUE" and a["DUPLICATE_SIDE_EFFECT_COUNT"]==0
            and a["HUMAN_MESSAGE_RELAY_REQUIRED"]=="FALSE")
def main():
    R=_read()
    by_engine={e:per_engine_acceptance(R,e) for e in ENGINES}
    out={"acceptance_by_engine":by_engine,
         "acceptance_all_met_by_engine":{e:_met(by_engine[e]) for e in ENGINES},
         "note":"Per-engine evidence view. ADDITIVE and read-only; does NOT change controller.py's joint "
                "fail-closed gate, durability semantics, or the Temporal-vs-Hatchet comparison, and names NO winner.",
         "source":os.path.basename(RESULTS_LOG)}
    json.dump(out, open(os.path.join(EV,"P0E_ACCEPTANCE_BY_ENGINE_V01.json"),"w"), indent=2)
    print("acceptance_all_met_by_engine:", json.dumps(out["acceptance_all_met_by_engine"]))
    return out
if __name__=="__main__":
    main()
