"""Deterministic leases: claim -> heartbeat -> expiry -> safe reclaim. `now` is always explicit."""
class Lease:
    def __init__(self, task_id, holder, lease_id, acquired_at, ttl):
        self.task_id=task_id; self.holder=holder; self.lease_id=lease_id
        self.acquired_at=acquired_at; self.ttl=ttl; self.last_heartbeat=acquired_at; self.released=False
    def expires_at(self): return self.last_heartbeat + self.ttl
    def is_expired(self, now): return (not self.released) and now >= self.expires_at()
    def heartbeat(self, now):
        if not self.released: self.last_heartbeat=now
        return self
    def release(self): self.released=True; return self
class LeaseTable:
    """A task may be held by at most one live lease unless allow_parallel."""
    def __init__(self): self._by_task={}
    def acquire(self, task_id, holder, lease_id, now, ttl, allow_parallel=False):
        cur=self._by_task.get(task_id)
        if cur and not cur.released and not cur.is_expired(now) and not allow_parallel:
            return None  # already held by a live lease
        lease=Lease(task_id,holder,lease_id,now,ttl); self._by_task[task_id]=lease; return lease
    def get(self, task_id): return self._by_task.get(task_id)
    def reclaim(self, task_id, holder, lease_id, now, ttl):
        cur=self._by_task.get(task_id)
        if cur and not cur.released and not cur.is_expired(now): return None  # still live -> cannot reclaim
        return self.acquire(task_id, holder, lease_id, now, ttl)
