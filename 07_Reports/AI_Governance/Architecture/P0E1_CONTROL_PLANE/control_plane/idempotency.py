"""Deterministic job identity + exactly-once side-effect store (dedup => 0 duplicate side effects)."""
from .events import sha256
def job_id(task_id, state_version, input_hash):
    return sha256({"task_id":task_id,"state_version":state_version,"input_hash":input_hash})
class SideEffectStore:
    def __init__(self): self._done={}; self.duplicate_attempts=0
    def once(self, key, fn):
        if key in self._done:
            self.duplicate_attempts += 1
            return self._done[key], True   # (result, was_duplicate) — fn NOT re-run
        r = fn(); self._done[key]=r; return r, False
    def count(self): return len(self._done)
