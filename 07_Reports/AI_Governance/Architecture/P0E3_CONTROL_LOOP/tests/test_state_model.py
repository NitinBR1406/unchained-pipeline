"""P0-E3 versioned state model: replay==master, monotonic versions, hash binding, tamper fail-closed."""
import os, json, tempfile
from _harness import Counter
from control_loop import scenarios as S, state_model
from control_plane.ledger import EventLedger
from control_plane import events as E
c = Counter("SM")

hp = S.happy_path()
ledger, persisted = hp["loop"].ledger, hp["persisted"]

ok, detail = state_model.verify_replay(ledger, persisted)
c.ok("replay_matches_master", ok)
c.ok("persisted_has_state_hash", isinstance(persisted.get("state_hash"), str) and len(persisted["state_hash"]) == 64)
c.ok("persisted_has_ledger_head_hash", isinstance(persisted.get("ledger_head_hash"), str))
c.ok("state_version_positive", persisted["state_version"] > 0)

# derive is a pure function: deriving twice yields identical pure state
d1 = state_model.derive(ledger)
d2 = state_model.derive(ledger)
c.ok("derive_is_deterministic", d1 == d2)

# state_hash is bound to state_version + ledger_head_hash
recomputed = state_model.compute_state_hash(
    {k: v for k, v in d1.items() if k not in ("ledger_head_hash", "state_hash")},
    d1["state_version"], d1["ledger_head_hash"])
c.ok("state_hash_binds_version_and_head", recomputed == d1["state_hash"])

# monotonic helper
c.ok("monotonic_true", state_model.is_monotonic(3, 4) and state_model.is_monotonic(4, 4))
c.ok("monotonic_regress_false", not state_model.is_monotonic(5, 4))

# replay fails closed if the persisted state is doctored (state_version bumped)
tampered = dict(persisted); tampered["state_version"] = persisted["state_version"] + 1
ok2, _ = state_model.verify_replay(ledger, tampered)
c.ok("replay_rejects_version_tamper", not ok2)

# replay fails closed if a core field is doctored
tampered2 = dict(persisted); tampered2["phase"] = "PRODUCTION"
ok3, _ = state_model.verify_replay(ledger, tampered2)
c.ok("replay_rejects_core_tamper", not ok3)

# persist metadata (previous_state_hash etc.) is excluded from replay equality
withmeta = dict(persisted); withmeta["previous_state_hash"] = "abc"; withmeta["persisted_by"] = "x"
ok4, _ = state_model.verify_replay(ledger, withmeta)
c.ok("replay_ignores_persist_metadata", ok4)

# derive fails closed on a tampered (broken-chain) ledger
d = tempfile.mkdtemp()
lp = os.path.join(d, "L.jsonl")
lg = EventLedger(lp)
lg.append(E.make_event("e1", "ARCH_DECISION", "t", "claude", decision={"winner": "TEMPORAL"}))
lg.append(E.make_event("e2", "RUNNER_HEARTBEAT", "t", "claude"))
# corrupt the file
lines = open(lp).read().splitlines()
rec = json.loads(lines[0]); rec["agent"] = "attacker"; lines[0] = json.dumps(rec)
open(lp, "w").write("\n".join(lines) + "\n")
try:
    state_model.derive(EventLedger(lp))
    c.ok("derive_fail_closed_on_tamper", False)
except Exception:
    c.ok("derive_fail_closed_on_tamper", True)

c.done()
