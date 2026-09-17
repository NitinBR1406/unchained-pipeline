"""P0E2-NB-001 live closure: aggregate POC_INFRA_REMAINING becomes boolean false when teardown proves false;
stays OPEN (and gate fails) otherwise. Frozen P0-E2 evidence is never modified by this path."""
import os, tempfile, json
from _harness import Counter, live_shaped_drive_contract
from control_loop import live_evidence as LE
import live_acceptance_p0e3 as G
c = Counter("NBL")

# teardown proves false -> aggregate normalized to boolean false -> NB-001 CLOSED, gate PASS
d = tempfile.mkdtemp()
LE.build_pass_bundle(d, drive=live_shaped_drive_contract())   # hermetic; no proof file
agg = json.load(open(os.path.join(d, LE.F_AGG)))
c.ok("aggregate_poc_boolean_false", agg.get("POC_INFRA_REMAINING") is False)
c.ok("aggregate_nb001_marked_closed", agg.get("_nb001", {}).get("P0E2_NB_001") == "CLOSED")
v = G.verify(d)
c.ok("gate_nb001_closed", v["P0E2_NB_001"] == "CLOSED")
c.ok("gate_pass_with_nb001", v["FINAL"] == "PASS")

# teardown NOT proven false -> aggregate not forced false -> NB-001 OPEN -> gate FAIL (fail-closed)
d2 = tempfile.mkdtemp()
loop2 = LE.run_durable_live(d2)
sha = "c" * 40
wf = {t: {"workflow_id": "w" + t, "run_id": "r" + t} for t in ("TASK_A", "TASK_B", "TASK_C", "TASK_D")}
drive = live_shaped_drive_contract()   # hermetic live-shaped contract; no recorded artifact
LE.build_bundle(d2, loop2, checkout={"requested": sha, "CHECKED_OUT_SHA": sha}, workflows=wf,
                poc={"TEMPORAL_POC_INFRA_REMAINING": True}, drive=drive)   # temporal infra remained
agg2 = json.load(open(os.path.join(d2, LE.F_AGG)))
c.ok("aggregate_poc_not_false_when_remaining", agg2.get("POC_INFRA_REMAINING") is not False)
v2 = G.verify(d2)
c.ok("gate_fails_when_infra_remains", v2["FINAL"] == "FAIL")
c.ok("gate_nb001_open_when_infra_remains", v2["P0E2_NB_001"] == "OPEN")

# frozen P0-E2 evidence is not touched by the P0-E3 normalizer (it operates on the P0-E3 aggregate only)
c.ok("no_frozen_p0e2_path_referenced", "P0E2_AUTONOMOUS_RUNNER" not in json.dumps(agg))

c.done()
