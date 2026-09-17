"""P0-E3 central persistence: write->read-back->sha256 verify, CAS/optimistic concurrency, immutability."""
import os, tempfile, hashlib
from _harness import Counter
from control_loop.persistence import CentralPersistence, LocalDirBackend, CONFLICT, OK, PersistenceError
c = Counter("PER")


def fresh():
    return CentralPersistence(LocalDirBackend(tempfile.mkdtemp()))


def cand(v, head="h%d", core="X"):
    hh = (head % v) if "%" in head else head
    return {"state_version": v, "ledger_head_hash": hh, "state_hash": "s%d" % v, "core": core}

# first write to empty store
p = fresh()
r = p.write(cand(1), expected_state_version=0, expected_ledger_head_hash=None)
c.ok("first_write_ok", r["status"] == OK and r["readback_verified"] is True)
c.ok("head_reflects_write", p.read_head()["state_version"] == 1)

# read-back sha matches file bytes
head = p.read_head()
raw = p.backend.get_bytes(head["file"])
c.ok("readback_sha_matches", hashlib.sha256(raw).hexdigest() == head["sha256"])

# correct CAS advances
r2 = p.write(cand(2), expected_state_version=1, expected_ledger_head_hash="h1")
c.ok("cas_advance_ok", r2["status"] == OK and p.read_head()["state_version"] == 2)

# stale expectation -> CONFLICT, no overwrite
before = p.head_bytes()
r3 = p.write(cand(3), expected_state_version=1, expected_ledger_head_hash="h1")  # stale (head is v2)
c.ok("stale_expectation_conflict", r3["status"] == CONFLICT)
c.ok("head_untouched_on_conflict", p.head_bytes() == before)

# wrong ledger_head_hash -> CONFLICT
r4 = p.write(cand(3), expected_state_version=2, expected_ledger_head_hash="WRONG")
c.ok("wrong_headhash_conflict", r4["status"] == CONFLICT)

# non-monotonic / historical version -> CONFLICT (never overwrite committed history)
r5 = p.write(cand(2), expected_state_version=2, expected_ledger_head_hash="h2")
c.ok("historical_overwrite_rejected", r5["status"] == CONFLICT)

# historical version file is preserved (immutability)
c.ok("v1_file_preserved", p.backend.exists("state_v1.json"))
c.ok("v2_file_preserved", p.backend.exists("state_v2.json"))

# empty store but caller expects nonzero -> CONFLICT (no silent create)
p2 = fresh()
r6 = p2.write(cand(5), expected_state_version=4, expected_ledger_head_hash="h4")
c.ok("empty_store_nonzero_expectation_conflict", r6["status"] == CONFLICT)

# read-back verification failure is surfaced (never reported as success)
class FlakyBackend(LocalDirBackend):
    def get_bytes(self, name):
        if name.startswith("state_v"):
            return b'{"corrupted":true}'   # read-back returns different bytes than written
        return super().get_bytes(name)
p3 = CentralPersistence(FlakyBackend(tempfile.mkdtemp()))
try:
    p3.write(cand(1), expected_state_version=0, expected_ledger_head_hash=None)
    c.ok("readback_mismatch_raises", False)
except PersistenceError:
    c.ok("readback_mismatch_raises", True)
c.ok("no_head_committed_on_readback_fail", p3.read_head() is None)

c.done()
