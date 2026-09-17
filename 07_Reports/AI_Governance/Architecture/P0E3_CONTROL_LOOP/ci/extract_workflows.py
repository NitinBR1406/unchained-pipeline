"""Extract REAL Temporal workflow/run ids from the frozen P0-E2 LiveRunner evidence into workflows.json.

Never invents ids: reads only what the LiveRunner persisted (P0E2_LIVE_RESULTS.json). Missing ids stay
null so the fail-closed live gate rejects an incomplete run.
"""
import json, os, sys

TASKS = ("TASK_A", "TASK_B", "TASK_C", "TASK_D")


def main():
    p2 = sys.argv[sys.argv.index("--p0e2-results") + 1]
    out = sys.argv[sys.argv.index("--out") + 1]
    wf = {t: {"workflow_id": None, "run_id": None} for t in TASKS}
    if os.path.exists(p2):
        r = json.load(open(p2))
        ids = r.get("workflow_ids", {}) or {}
        runs = r.get("run_ids", {}) or {}
        for t in TASKS:
            wf[t] = {"workflow_id": ids.get(t), "run_id": runs.get(t)}
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(wf, open(out, "w"), indent=2, sort_keys=True)
    print("workflows.json:", json.dumps(wf))


if __name__ == "__main__":
    main()
