"""P0-E3 crash-recovery matrix: crash at boundaries A-F, restart, prove deterministic reconciliation."""
from _harness import Counter
from control_loop import scenarios as S
c = Counter("CR")

for name, boundary in S.BOUNDARY_MAP.items():
    r = S.crash_and_recover(boundary)
    c.ok("%s_crashed" % name, r["crashed"])
    c.ok("%s_no_duplicate_side_effect" % name, r["duplicate_side_effects"] == 0)
    c.ok("%s_no_lost_completed_work" % name, r["a_done"] and r["b_done"] and r["d_done"])
    c.ok("%s_independent_D_continues" % name, r["d_done"])
    c.ok("%s_C_stays_waiting" % name, r["c_waiting"])
    c.ok("%s_no_fabricated_approval" % name, r["no_fabricated_approval"])
    c.ok("%s_replay_matches_after_restart" % name, r["replay_matches"])

c.done()
