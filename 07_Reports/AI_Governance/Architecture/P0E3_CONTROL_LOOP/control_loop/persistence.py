"""P0-E3 Central Persistence adapter — write / read-back / SHA256-verify + optimistic concurrency.

Lifecycle (never claim success before read-back verification):
    WRITE candidate version  ->  READ BACK  ->  SHA256 VERIFY  ->  only then mark persistence successful

Optimistic concurrency (never silent last-write-wins). A writer must present:
    expected_state_version
    expected_ledger_head_hash
If central state changed since the writer read it, the write is a CONFLICT: the candidate is NOT written,
HEAD is untouched, and the caller must reload + reconcile + retry.

Versioning: every committed version is written to an immutable file `state_v{N}.json` and never overwritten
(historical versions are preserved). A single `HEAD.json` names the current committed version and is swapped
atomically (write-temp + os.replace) only after read-back verification succeeds.

`Backend` is an abstract interface so a Google Shared Drive-backed backend can be dropped in unchanged
(put_bytes/get_bytes/exists). `LocalDirBackend` is the offline reference implementation used for Slice-1;
the identical write->read-back->sha256 contract was independently proven live against the Shared Drive during
the P0-E2 final freeze. This module does NOT fabricate any live Drive persistence.
"""
import os, json, hashlib, tempfile

CONFLICT = "CONFLICT"
OK = "OK"


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


class PersistenceError(Exception):
    pass


class Backend:
    """Abstract byte store. A Shared Drive-backed implementation only needs these three operations."""
    def put_bytes(self, name, data):  raise NotImplementedError
    def get_bytes(self, name):        raise NotImplementedError
    def exists(self, name):           raise NotImplementedError


class LocalDirBackend(Backend):
    """Filesystem reference backend (stands in for the Shared Drive in offline Slice-1)."""
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _p(self, name):
        return os.path.join(self.root, name)

    def put_bytes(self, name, data):
        # atomic replace so a crash never leaves a torn file
        fd, tmp = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._p(name))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def get_bytes(self, name):
        with open(self._p(name), "rb") as f:
            return f.read()

    def exists(self, name):
        return os.path.exists(self._p(name))


class CentralPersistence:
    HEAD = "HEAD.json"

    def __init__(self, backend):
        self.backend = backend

    # ---- HEAD helpers ---------------------------------------------------
    def read_head(self):
        if not self.backend.exists(self.HEAD):
            return None
        return json.loads(self.backend.get_bytes(self.HEAD).decode())

    def head_bytes(self):
        """Raw HEAD bytes (or None) — used by tests to prove HEAD is untouched on a rejected write."""
        if not self.backend.exists(self.HEAD):
            return None
        return self.backend.get_bytes(self.HEAD)

    def _version_name(self, n):
        return "state_v%d.json" % n

    def read_current(self):
        """Return the current committed Master State document, or None."""
        h = self.read_head()
        if not h:
            return None
        return json.loads(self.backend.get_bytes(h["file"]).decode())

    # ---- the guarded write ---------------------------------------------
    def write(self, candidate, expected_state_version, expected_ledger_head_hash, on_boundary=None):
        """Persist `candidate` with optimistic concurrency + mandatory read-back SHA256 verification.

        Returns a result dict:
          {status:OK, state_version, sha256, readback_verified:True, file}          on success
          {status:CONFLICT, head_state_version, head_ledger_head_hash, ...}         on CAS conflict
        Raises PersistenceError only if a write physically happened but read-back did NOT verify.
        """
        head = self.read_head()

        # ---- optimistic concurrency (CAS): never silent last-write-wins ----
        if head is None:
            if expected_state_version not in (None, 0):
                return {"status": CONFLICT, "reason": "EXPECTED_NONEMPTY_BUT_STORE_EMPTY",
                        "head_state_version": None, "head_ledger_head_hash": None}
        else:
            if (head["state_version"] != expected_state_version
                    or head["ledger_head_hash"] != expected_ledger_head_hash):
                return {"status": CONFLICT, "reason": "STALE_EXPECTATION",
                        "head_state_version": head["state_version"],
                        "head_ledger_head_hash": head["ledger_head_hash"]}

        new_version = candidate["state_version"]
        # monotonic guard: never regress, and never overwrite a committed historical version
        committed = head["state_version"] if head else -1
        if new_version <= committed:
            return {"status": CONFLICT, "reason": "NON_MONOTONIC_OR_HISTORICAL",
                    "head_state_version": committed}

        name = self._version_name(new_version)
        payload = json.dumps(candidate, sort_keys=True, indent=2).encode()
        expected_sha = _sha256_bytes(payload)

        # ---- WRITE candidate ----
        self.backend.put_bytes(name, payload)

        # crash boundary B: state file written, HEAD not yet committed, read-back not yet done
        if on_boundary:
            on_boundary("state_written_before_readback", {"file": name})

        # ---- READ BACK + SHA256 VERIFY (persistence is NOT successful until this passes) ----
        readback = self.backend.get_bytes(name)
        actual_sha = _sha256_bytes(readback)
        if actual_sha != expected_sha or readback != payload:
            raise PersistenceError(
                "READ_BACK_VERIFY_FAILED for %s: expected %s got %s" % (name, expected_sha, actual_sha))

        # ---- only NOW commit HEAD (atomic swap) ----
        new_head = {"state_version": new_version,
                    "ledger_head_hash": candidate["ledger_head_hash"],
                    "state_hash": candidate["state_hash"],
                    "file": name,
                    "sha256": expected_sha}
        self.backend.put_bytes(self.HEAD, json.dumps(new_head, sort_keys=True, indent=2).encode())

        return {"status": OK, "state_version": new_version, "sha256": expected_sha,
                "readback_verified": True, "file": name}
