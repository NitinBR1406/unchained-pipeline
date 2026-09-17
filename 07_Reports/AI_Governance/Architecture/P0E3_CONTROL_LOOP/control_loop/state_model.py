"""P0-E3 versioned Master State — derived DETERMINISTICALLY from the Event Ledger.

The reducer (frozen P0-E1) is the only authority that turns ordered events into state. This module wraps the
reducer output in a versioned, hash-bound envelope and proves the core invariant:

    REPLAY(ledger) == persisted MASTER STATE

Design:
  * `derive(ledger, keyring)` reads the ledger, strips the ledger envelope from each record to recover the
    original event, replays it through the frozen reducer, and returns a PURE versioned state.
  * A PURE versioned state is a pure function of the ledger. It carries:
        state_version     - monotonic; the reducer's applied-transition counter
        ledger_head_hash  - the exact ledger head this state corresponds to
        state_hash        - SHA256 over the canonical core (bound to state_version + ledger_head_hash)
    plus the full reducer core (internal `_`-prefixed bookkeeping keys removed so the state is auditable
    and hashing is stable).
  * `previous_state_hash`, `persisted_at`, `persisted_by`, `persist_seq` are PERSIST metadata added by the
    persistence layer (they describe write history, not ledger-derived truth) and are excluded from replay
    equality.

No wall clock, no randomness: `updated_at`/`updated_by` come from the events themselves, so derive() is
fully reproducible.
"""
from control_plane.events import canonical, sha256          # frozen P0-E1
from control_plane.ledger import EventLedger, GENESIS        # frozen P0-E1
from control_plane.reducer import reduce as _reduce          # frozen P0-E1
from control_plane import human_auth                         # frozen P0-E1

# Ledger-envelope keys added by EventLedger.append(); not part of the original event.
_LEDGER_ENVELOPE = ("ledger_seq", "prev_ledger_hash", "ledger_hash")
# Persist-only metadata; excluded from the ledger-derived (PURE) state and from replay equality.
PERSIST_META = ("previous_state_hash", "persisted_at", "persisted_by", "persist_seq")


class StateError(Exception):
    pass


def _strip_envelope(rec):
    return {k: v for k, v in rec.items() if k not in _LEDGER_ENVELOPE}


def _core_from_reducer(s):
    """Drop internal bookkeeping (`_`-prefixed) keys -> stable, auditable core."""
    return {k: v for k, v in s.items() if not k.startswith("_")}


def compute_state_hash(core, state_version, ledger_head_hash):
    """Pure content hash binding the core to its exact version and ledger head."""
    payload = {"core": core, "state_version": state_version, "ledger_head_hash": ledger_head_hash}
    return sha256(canonical(payload).encode())


def derive(ledger, keyring=None):
    """Return the PURE versioned Master State for the current ledger. Pure function of the ledger."""
    if isinstance(ledger, str):
        ledger = EventLedger(ledger)
    if keyring is None:
        keyring = human_auth.load_keyring()
    ledger.verify_chain()  # fail-closed: never derive state from a tampered/broken ledger
    records = ledger.read_all()
    events = [_strip_envelope(r) for r in records]
    reduced = _reduce(events, keyring=keyring)
    core = _core_from_reducer(reduced)
    head = records[-1]["ledger_hash"] if records else GENESIS
    sv = reduced["state_version"]
    sh = compute_state_hash(core, sv, head)
    out = dict(core)
    out["state_version"] = sv
    out["ledger_head_hash"] = head
    out["state_hash"] = sh
    return out


def pure_view(state):
    """The ledger-derived (PURE) portion of a persisted state: strips persist-only metadata."""
    return {k: v for k, v in state.items() if k not in PERSIST_META}


def verify_replay(ledger, persisted, keyring=None):
    """REPLAY(ledger) == persisted MASTER STATE (over the pure, ledger-derived portion).

    Returns (ok, detail). Compares state_version, ledger_head_hash, state_hash and full core.
    """
    d = derive(ledger, keyring=keyring)
    p = pure_view(persisted)
    for k in ("state_version", "ledger_head_hash", "state_hash"):
        if d.get(k) != p.get(k):
            return False, "MISMATCH:%s derived=%r persisted=%r" % (k, d.get(k), p.get(k))
    if d != p:
        dk = sorted(set(d) | set(p))
        diff = [k for k in dk if d.get(k) != p.get(k)]
        return False, "CORE_MISMATCH:%s" % diff
    return True, "OK"


def is_monotonic(prev_version, next_version):
    """State versions must be strictly non-decreasing; a new accepted transition strictly increases."""
    return next_version >= prev_version
