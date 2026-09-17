"""P0E2-NB-001 (NON-BLOCKING maintenance) — normalize aggregate POC_INFRA_REMAINING.

Symptom carried forward from P0-E2: a P0E2_LIVE_RESULTS-style aggregate can report
POC_INFRA_REMAINING=null even though the authoritative, unconditional teardown evidence proves the
disposable infra was fully torn down (POC_INFRA_REMAINING=false).

This normalizer reconciles the aggregate to the authoritative teardown evidence. It is deliberately
fail-closed and additive — it does NOT touch or weaken the frozen P0-E2 acceptance gate, and it will only
ever set the aggregate to false when teardown evidence EXPLICITLY proves false. Anything else is left
untouched, so a genuinely un-torn-down or unproven state still fails closed downstream.

This does NOT reopen P0-E2 GREEN; the authoritative P0-E2 acceptance already proved teardown independently.
"""


def _is_explicit_false(v):
    if isinstance(v, bool):
        return v is False
    if isinstance(v, str):
        return v.strip().lower() == "false"
    return False


def teardown_proves_false(teardown_evidence):
    """Authoritative teardown proves POC_INFRA_REMAINING=false only on an EXPLICIT false signal."""
    if not isinstance(teardown_evidence, dict):
        return False
    for key in ("POC_INFRA_REMAINING", "poc_infra_remaining"):
        if key in teardown_evidence and _is_explicit_false(teardown_evidence[key]):
            return True
    # accept a structured teardown record: {"teardown":"COMPLETE","infra_remaining":false}
    if str(teardown_evidence.get("teardown", "")).upper() == "COMPLETE" \
            and _is_explicit_false(teardown_evidence.get("infra_remaining", None)):
        return True
    return False


def normalize_poc_infra(aggregate, teardown_evidence):
    """Return (normalized_aggregate, changed:bool, reason).

    Only normalizes POC_INFRA_REMAINING to false when authoritative teardown proves false AND the aggregate
    is currently null/absent/non-false. Never overwrites an explicit aggregate=true with false unless
    teardown proves false (teardown is the authority); never invents a false without proof.
    """
    agg = dict(aggregate) if isinstance(aggregate, dict) else {}
    cur = agg.get("POC_INFRA_REMAINING", None)
    proven = teardown_proves_false(teardown_evidence)

    if not proven:
        return agg, False, "TEARDOWN_NOT_PROVEN_FALSE_LEFT_UNCHANGED"

    if _is_explicit_false(cur):
        agg["POC_INFRA_REMAINING"] = False
        return agg, False, "ALREADY_FALSE"

    agg["POC_INFRA_REMAINING"] = False
    agg.setdefault("_normalized", {})["POC_INFRA_REMAINING"] = {
        "from": cur, "to": False, "authority": "teardown_evidence", "ticket": "P0E2-NB-001"}
    return agg, True, "NORMALIZED_NULL_TO_FALSE"
