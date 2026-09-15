import sys, os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
from control_plane import events as E
def build():
    return [
     E.make_event("e001","ARCH_DECISION","2026-01-01T00:00:01Z","chatgpt",
        decision={"selected_control_plane":"TEMPORAL","architecture_bakeoff":"CLOSED","winner":"TEMPORAL",
                  "production_deployment_authorized":False,"adr_ref":"P0E_ADR_001_TEMPORAL_CONTROL_PLANE.md"},
        evidence=["github_run:34979288601","commit:fe1b83c1d36960016834b9eda6577c53a84c159a"]),
     E.make_event("e002","EVIDENCE_REGISTERED","2026-01-01T00:00:02Z","claude",
        inputs={"artifact":"P0E_CONTROL_PLANE_ARCHITECTURE_DECISION_V01.json","version":"V01"}),
     E.make_event("e003","RUNNER_HEARTBEAT","2026-01-01T00:00:03Z","claude"),
    ]
if __name__=="__main__":
    for e in build(): print(E.canonical(e))
