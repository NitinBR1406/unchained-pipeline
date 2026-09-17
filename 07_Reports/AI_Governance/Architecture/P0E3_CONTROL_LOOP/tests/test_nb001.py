"""P0E2-NB-001 regression: aggregate POC_INFRA_REMAINING normalized to false only when teardown proves it."""
from _harness import Counter
from control_loop.nb001_normalize import normalize_poc_infra, teardown_proves_false
c = Counter("NB")

TD_FALSE = {"POC_INFRA_REMAINING": False}
TD_STRUCT = {"teardown": "COMPLETE", "infra_remaining": False}
TD_UNPROVEN = {"teardown": "PARTIAL"}
TD_TRUE = {"POC_INFRA_REMAINING": True}

# null aggregate normalized to false when teardown proves false
agg, changed, reason = normalize_poc_infra({"POC_INFRA_REMAINING": None}, TD_FALSE)
c.ok("null_normalized_to_false", agg["POC_INFRA_REMAINING"] is False and changed)
c.ok("normalization_recorded", agg["_normalized"]["POC_INFRA_REMAINING"]["ticket"] == "P0E2-NB-001")

# absent key normalized to false when teardown proves false
agg2, changed2, _ = normalize_poc_infra({}, TD_STRUCT)
c.ok("absent_normalized_to_false", agg2["POC_INFRA_REMAINING"] is False and changed2)

# already-false left as false, no spurious change
agg3, changed3, reason3 = normalize_poc_infra({"POC_INFRA_REMAINING": False}, TD_FALSE)
c.ok("already_false_unchanged", agg3["POC_INFRA_REMAINING"] is False and not changed3 and reason3 == "ALREADY_FALSE")

# FAIL-CLOSED: teardown not proven -> never invent false
agg4, changed4, reason4 = normalize_poc_infra({"POC_INFRA_REMAINING": None}, TD_UNPROVEN)
c.ok("unproven_left_unchanged", agg4.get("POC_INFRA_REMAINING") is None and not changed4)
c.ok("unproven_reason", reason4 == "TEARDOWN_NOT_PROVEN_FALSE_LEFT_UNCHANGED")

# teardown_proves_false detector
c.ok("detect_explicit_false", teardown_proves_false(TD_FALSE))
c.ok("detect_struct_false", teardown_proves_false(TD_STRUCT))
c.ok("detect_true_is_not_false", not teardown_proves_false(TD_TRUE))
c.ok("detect_unproven_is_not_false", not teardown_proves_false(TD_UNPROVEN))
c.ok("detect_garbage_is_not_false", not teardown_proves_false(None) and not teardown_proves_false("nope"))

# string "false" also accepted from a stringly-typed aggregate
c.ok("detect_string_false", teardown_proves_false({"POC_INFRA_REMAINING": "false"}))

c.done()
