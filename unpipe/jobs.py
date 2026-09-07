"""Deterministic production job queue with idempotency.

Idempotency key = campaign_id + frozen_json_sha256 + production_profile.
A new job is NOT created if a DONE or in-progress job already exists for that key -> the same
approved frozen JSON never triggers uncontrolled duplicate paid renders.
"""
from pathlib import Path
from .util import read_json, write_json, now_iso

JOB_QUEUED = "QUEUED"
JOB_RUNNING = "RUNNING"
JOB_SUBMITTED = "SUBMITTED"
JOB_POLLING = "POLLING"
JOB_DOWNLOADING = "DOWNLOADING"
JOB_QC_RUNNING = "QC_RUNNING"
JOB_DONE = "DONE"
JOB_RETRY_WAIT = "RETRY_WAIT"
JOB_HOLD = "HOLD"
JOB_FAILED = "FAILED"

IN_PROGRESS = {JOB_QUEUED, JOB_RUNNING, JOB_SUBMITTED, JOB_POLLING, JOB_DOWNLOADING,
               JOB_QC_RUNNING, JOB_RETRY_WAIT}


def idempotency_key(campaign_id, frozen_sha, profile="MASTER_V1"):
    return f"{campaign_id}|{frozen_sha}|{profile}"


class JobQueue:
    def __init__(self, path):
        self.path = Path(path)
        self._data = read_json(self.path, default={"jobs": []}) or {"jobs": []}

    def _save(self):
        write_json(self.path, self._data)

    def find_by_key(self, ikey):
        return [j for j in self._data["jobs"] if j["idempotency_key"] == ikey]

    def active_or_done(self, ikey):
        for j in self.find_by_key(ikey):
            if j["status"] == JOB_DONE or j["status"] in IN_PROGRESS:
                return j
        return None

    def enqueue(self, campaign_id, frozen_artifact_id, frozen_sha, authorized_by_gate,
                profile="MASTER_V1"):
        ikey = idempotency_key(campaign_id, frozen_sha, profile)
        existing = self.active_or_done(ikey)
        if existing:
            return existing, False  # idempotent: reuse
        job = {
            "job_id": f"job-{len(self._data['jobs'])+1}-{frozen_sha[:8]}",
            "campaign_id": campaign_id,
            "frozen_json_artifact_id": frozen_artifact_id,
            "frozen_json_sha256": frozen_sha,
            "production_profile": profile,
            "idempotency_key": ikey,
            "requested_at": now_iso(),
            "authorized_by_gate": authorized_by_gate,
            "status": JOB_QUEUED,
            "attempt": 0,
            "shotstack_render_id": None,
            "output_artifact_id": None,
            "output_sha256": None,
            "tech_qc_status": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "error": None,
        }
        self._data["jobs"].append(job)
        self._save()
        return job, True

    def update(self, job_id, **fields):
        for j in self._data["jobs"]:
            if j["job_id"] == job_id:
                j.update(fields)
                j["updated_at"] = now_iso()
                self._save()
                return j
        raise KeyError(job_id)

    def get(self, job_id):
        for j in self._data["jobs"]:
            if j["job_id"] == job_id:
                return j
        return None

    def all(self):
        return list(self._data["jobs"])
