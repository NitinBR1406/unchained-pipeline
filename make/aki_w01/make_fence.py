"""Ownership fencing for Make placement scenarios (P3; P2 builds the same structure explicitly via guarded()/wb()).

Every datastore UpdateRecord on the placement store (except the claim itself) and every publish call is preceded by a
GetRecord of the placement; the write/call only runs while this execution still owns the claim
(claim_token = the per-bundle {{uuid}} owner token, same attempt, status PUBLISHING). Lock records are insert-only per attempt and
never deleted, so no execution can release another execution's lock. Residual: no compare-and-swap in Make data stores.
"""
OWN = "{{49.owner}}"   # {{var.execution.id}} is EMPTY in Make runs (T-lock v1); module 49 = SetVariables owner={{uuid}}
OFFSET = 1000


def mine(g):
    return [{"a": "{{%d.claim_token}}" % g, "b": OWN, "o": "text:equal"}, {"a": "{{%d.status}}" % g, "b": "PUBLISHING", "o": "text:equal"},
            {"a": "{{%d.attempt_count}}" % g, "b": "{{1.data.attempt_count + 1}}", "o": "number:equal"}]


def _and(flt, extra, name):
    if not flt:
        return {"name": name, "conditions": [extra]}
    return {"name": flt.get("name", "") + " + " + name, "conditions": [list(g) + extra for g in flt["conditions"]]}


def fence_flow(flow, ds, skip_ids=(50,), is_publish=lambda m: False):
    out = []
    for m in flow:
        if m.get("onerror"):
            m["onerror"] = fence_flow(m["onerror"], ds, skip_ids, is_publish)
        for r in m.get("routes") or []:
            r["flow"] = fence_flow(r["flow"], ds, skip_ids, is_publish)
        writes = m["module"] == "datastore:UpdateRecord" and m.get("parameters", {}).get("datastore") == ds and m["id"] not in skip_ids
        if writes or is_publish(m):
            g = m["id"] + OFFSET
            flt = m.pop("filter", None)
            out.append({"id": g, "mapper": {"key": "{{1.key}}", "returnWrapped": False}, "module": "datastore:GetRecord", "version": 1, "parameters": {"datastore": ds},
                        **({"filter": flt} if flt else {})})
            m["filter"] = _and(None, mine(g), "this execution still owns the claim")
        out.append(m)
    return out
