"""P0-E3 durable adapters: a file-backed exactly-once side-effect store and a canonical Backlog store.

These are ADDITIVE adapters, not redesigns of P0-E1. The exactly-once semantics and the deterministic
job identity come straight from the frozen `control_plane.idempotency`; here they are made crash-durable by
persisting to disk so exactly-once survives a process restart.
"""
import os, json, tempfile
from control_plane.idempotency import job_id as _job_id       # frozen P0-E1

# ---- canonical Backlog task schema (P0-E3 requirement 3) --------------------
TASK_FIELDS = ("task_id", "title", "priority", "dependencies", "status", "autonomy_level",
               "allowed_scope", "definition_of_done", "tests_required", "evidence_required",
               "rollback", "human_gate_required", "blocked_reason", "next_action",
               "claimed_by", "lease_id", "lease_expires_at", "input_hash", "idempotency_key",
               "state_version")
LIFECYCLE = {"READY", "CLAIMED", "RUNNING", "VERIFYING", "COMPLETED", "BLOCKED", "WAITING_FOR_NITIN", "FAILED"}
TERMINAL = {"COMPLETED", "FAILED"}


class SchemaError(Exception):
    pass


def _atomic_write_json(path, obj):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def validate_task(t):
    missing = [k for k in TASK_FIELDS if k not in t]
    if missing:
        raise SchemaError("task %r missing fields: %s" % (t.get("task_id"), missing))
    if t["status"] not in LIFECYCLE:
        raise SchemaError("task %r invalid status %r" % (t.get("task_id"), t["status"]))
    if not isinstance(t.get("dependencies"), list):
        raise SchemaError("task %r dependencies must be a list" % t.get("task_id"))
    return True


class BacklogStore:
    """Durable, JSON-file backed backlog with deterministic dependency resolution."""
    def __init__(self, path):
        self.path = path
        self.tasks = []
        if os.path.exists(path):
            self.tasks = json.load(open(path))
        for t in self.tasks:
            validate_task(t)

    def save(self):
        _atomic_write_json(self.path, self.tasks)

    def by_id(self, tid):
        for t in self.tasks:
            if t["task_id"] == tid:
                return t
        return None

    def completed_ids(self):
        return {t["task_id"] for t in self.tasks if t["status"] == "COMPLETED"}

    def ready(self):
        """Deterministic: READY tasks whose deps are all COMPLETED, ordered by (priority, task_id)."""
        done = self.completed_ids()
        out = [t for t in self.tasks
               if t["status"] == "READY" and all(d in done for d in t.get("dependencies", []))]
        out.sort(key=lambda t: (t.get("priority", 9999), t["task_id"]))
        return out

    def set_status(self, tid, status, **fields):
        t = self.by_id(tid)
        if t is None:
            raise SchemaError("unknown task %r" % tid)
        if status not in LIFECYCLE:
            raise SchemaError("invalid status %r" % status)
        t["status"] = status
        t.update(fields)
        validate_task(t)
        self.save()
        return t

    def summary(self):
        m = {"READY": "ready", "RUNNING": "running", "BLOCKED": "blocked",
             "WAITING_FOR_NITIN": "waiting_for_nitin", "COMPLETED": "completed",
             "FAILED": "failed", "CLAIMED": "claimed", "VERIFYING": "verifying"}
        c = {v: 0 for v in m.values()}
        for t in self.tasks:
            k = m.get(t["status"])
            if k:
                c[k] += 1
        return c


class DurableSideEffectStore:
    """Crash-durable exactly-once store. Keyed by deterministic job_id; re-runs never double-apply."""
    def __init__(self, path):
        self.path = path
        self._done = {}
        self.duplicate_attempts = 0
        if os.path.exists(path):
            data = json.load(open(path))
            self._done = data.get("done", {})
            self.duplicate_attempts = data.get("duplicate_attempts", 0)

    @staticmethod
    def job_id(task_id, state_version, input_hash):
        return _job_id(task_id, state_version, input_hash)

    def _flush(self):
        _atomic_write_json(self.path, {"done": self._done, "duplicate_attempts": self.duplicate_attempts})

    def once(self, key, fn):
        """Run fn() at most once per key. Returns (result, was_duplicate). Durable across restart."""
        if key in self._done:
            self.duplicate_attempts += 1
            self._flush()
            return self._done[key], True
        r = fn()
        self._done[key] = r
        self._flush()
        return r, False

    def has(self, key):
        return key in self._done

    def get(self, key):
        return self._done.get(key)

    def count(self):
        return len(self._done)
