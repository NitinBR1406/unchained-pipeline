"""Unchained Nitin — P0-E3 Durable Autonomous Control Loop (Slice 1, pure-Python core).

Builds STRICTLY on the frozen P0-E1 primitives (Event Ledger, deterministic Reducer, Backlog, Leases,
Idempotency, Human-Auth) and the P0-E2 autonomous runner. P0-E1/P0-E2 are NOT redesigned; this package
imports the frozen `control_plane` package unchanged.

Data flow:
  EVENT_LEDGER (append-only, hash-chained)
    -> DETERMINISTIC STATE REDUCER
    -> VERSIONED MASTER STATE  (state_version, previous_state_hash, state_hash, ledger_head_hash)
    -> CENTRAL PERSISTENCE  (write candidate -> read back -> SHA256 verify -> only then success)
    -> READ-BACK VERIFICATION
    -> BACKLOG / DEPENDENCY RESOLUTION
    -> CLAIM + LEASE  (exactly one valid claim; safe reclaim of stale lease)
    -> (TEMPORAL) EXECUTION  (deterministic job identity; exactly-once side effect)
    -> EVIDENCE
    -> STATE UPDATE
    -> AUTOMATIC NEXT READY TASK  (bounded; WAITING_FOR_NITIN never blocks independent work)

Invariant: REPLAY(ledger) == persisted MASTER STATE.
No production side effects. No publishing. Human gates are grantable ONLY by Nitin (Ed25519-verified).
"""
import os, sys

# Wire the frozen P0-E1 control_plane package onto the path without copying/redesigning it.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ARCH = os.path.abspath(os.path.join(_HERE, "..", ".."))
_P0E1 = os.path.join(_ARCH, "P0E1_CONTROL_PLANE")
if _P0E1 not in sys.path:
    sys.path.insert(0, _P0E1)

SLICE = "P0E3-SLICE-1"
