"""P0-E3 Slice-2 NEGATIVE security matrix: every listed defect MUST force the live gate to FAIL closed."""
import os, json, tempfile, shutil
from _harness import Counter, live_shaped_drive_contract
from control_loop import live_evidence as LE
import live_acceptance_p0e3 as G
c = Counter("NEG")

# one hermetic PASS bundle (explicit live-shaped drive contract; no proof file), cloned per negative case
BASE = tempfile.mkdtemp()
LE.build_pass_bundle(BASE, drive=live_shaped_drive_contract())
# sanity: base is PASS
c.ok("base_bundle_is_PASS", G.verify(BASE)["FINAL"] == "PASS")


def clone():
    d = tempfile.mkdtemp()
    shutil.copytree(BASE, os.path.join(d, "e"))
    return os.path.join(d, "e")


def edit(dirp, name, mutate):
    p = os.path.join(dirp, name)
    obj = json.load(open(p))
    obj = mutate(obj)
    json.dump(obj, open(p, "w"), indent=2)


def case(label, mutate_dir, expect_crit):
    d = clone()
    mutate_dir(d)
    v = G.verify(d)
    failed = v["FINAL"] == "FAIL" and (expect_crit is None or expect_crit in v["failed_criteria"])
    c.ok(label, failed)


# 1. missing workflow IDs
case("missing_workflow_ids_FAIL",
     lambda d: os.remove(os.path.join(d, LE.F_WORKFLOWS)), "REAL_TEMPORAL_WORKFLOWS_OBSERVED")

# 2. missing central-persistence evidence (remove central store dir)
case("missing_central_persistence_FAIL",
     lambda d: shutil.rmtree(os.path.join(d, LE.CENTRAL_DIR)), "REAL_CENTRAL_PERSISTENCE_OBSERVED")

# 3. empty readback hash (blank the committed HEAD sha256)
def _blank_head_sha(d):
    hp = os.path.join(d, LE.CENTRAL_DIR, "HEAD.json")
    h = json.load(open(hp)); h["sha256"] = ""; json.dump(h, open(hp, "w"))
case("empty_readback_hash_FAIL", _blank_head_sha, "CENTRAL_READBACK_SHA_MATCH")

# 4. SHA mismatch (requested != checked-out, both 40-hex)
case("sha_mismatch_FAIL",
     lambda d: edit(d, LE.F_CHECKOUT, lambda o: {**o, "CHECKED_OUT_SHA": "b" * 40}),
     "CHECKED_OUT_SHA_MATCHES_REQUEST")

# 5. stale write accepted
case("stale_write_accepted_FAIL",
     lambda d: edit(d, LE.F_CENTRAL, lambda o: {**o, "STALE_WRITE_REJECTED": False}),
     "STALE_WRITE_REJECTED")

# 6. double claim > 0
case("double_claim_nonzero_FAIL",
     lambda d: edit(d, LE.F_CONCURRENCY, lambda o: {**o, "CONCURRENT_DOUBLE_CLAIM_COUNT": 1}),
     "CONCURRENT_DOUBLE_CLAIM_COUNT_IS_ZERO")

# 7. duplicate side effect > 0
def _dup(d):
    p = os.path.join(d, LE.F_CRASH); m = json.load(open(p))
    k = next(iter(m)); m[k]["DUPLICATE_SIDE_EFFECT_COUNT"] = 1; json.dump(m, open(p, "w"))
case("duplicate_side_effect_FAIL", _dup, "DUPLICATE_SIDE_EFFECT_COUNT_IS_ZERO")

# 8. WAITING blocks independent work
case("waiting_blocks_FAIL",
     lambda d: edit(d, LE.F_AUTONOMY, lambda o: {**o, "WAITING_WORKFLOW_BLOCKS_OTHER_WORK": True}),
     "WAITING_WORKFLOW_BLOCKS_OTHER_WORK_IS_FALSE")

# 9. human relay required
case("human_relay_required_FAIL",
     lambda d: edit(d, LE.F_AUTONOMY, lambda o: {**o, "HUMAN_MESSAGE_RELAY_REQUIRED": True}),
     "HUMAN_MESSAGE_RELAY_REQUIRED_IS_FALSE")

# 10. fabricated approval
case("fabricated_approval_FAIL",
     lambda d: edit(d, LE.F_AUTONOMY, lambda o: {**o, "NO_APPROVAL_FABRICATED": False}),
     "NO_APPROVAL_FABRICATED")

# 11. missing crash scenario (drop one case)
def _drop_case(d):
    p = os.path.join(d, LE.F_CRASH); m = json.load(open(p)); m.pop(LE.CRASH_CASES[0]); json.dump(m, open(p, "w"))
case("missing_crash_scenario_FAIL", _drop_case, "CRASH_RECOVERY_MATRIX")

# 12. failed crash recovery (a cell did not reconcile)
def _fail_recovery(d):
    p = os.path.join(d, LE.F_CRASH); m = json.load(open(p))
    k = LE.CRASH_CASES[0]; m[k]["STATE_RECONCILED"] = False; m[k]["PASS"] = False; json.dump(m, open(p, "w"))
case("failed_crash_recovery_FAIL", _fail_recovery, "CRASH_RECOVERY_MATRIX")

# 13. POC infra remains
case("poc_infra_remains_FAIL",
     lambda d: edit(d, LE.F_POC, lambda o: {"POC_INFRA_REMAINING": True}), "POC_INFRA_REMAINING_IS_FALSE")

# 14. wrong checkout SHA (requested not a 40-hex commit)
case("wrong_checkout_sha_FAIL",
     lambda d: edit(d, LE.F_CHECKOUT, lambda o: {"requested": "main", "CHECKED_OUT_SHA": "main"}),
     "CHECKED_OUT_SHA_MATCHES_REQUEST")

# 15. null decision-critical evidence (corrupt/emty the live ledger -> nothing to derive)
def _null_ledger(d):
    open(os.path.join(d, LE.LEDGER), "w").write("")   # empty ledger
case("null_decision_critical_FAIL", _null_ledger, "EVENT_LEDGER_APPEND_ONLY")

# bonus: tampered ledger (broken chain) also fails closed
def _tamper_ledger(d):
    p = os.path.join(d, LE.LEDGER); lines = open(p).read().splitlines()
    if lines:
        rec = json.loads(lines[0]); rec["agent"] = "attacker"; lines[0] = json.dumps(rec)
        open(p, "w").write("\n".join(lines) + "\n")
case("tampered_ledger_chain_FAIL", _tamper_ledger, "EVENT_LEDGER_CHAIN_VALID")

# aggregate boolean cannot substitute for missing underlying central evidence:
# force aggregate to claim all-good but delete the central store -> still FAIL
def _agg_lies(d):
    edit(d, LE.F_AGG, lambda o: {**o, "REAL_CENTRAL_PERSISTENCE_OBSERVED": True})
    shutil.rmtree(os.path.join(d, LE.CENTRAL_DIR))
case("aggregate_cannot_mask_missing_central_FAIL", _agg_lies, "REAL_CENTRAL_PERSISTENCE_OBSERVED")

c.done()
