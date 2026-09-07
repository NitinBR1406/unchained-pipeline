"""Autonomous production executor (V1.1).

Runs on an event (GitHub Actions job) after CREATIVE_APPROVAL. Owns the full production job
lifecycle so Nitin never touches a terminal:

  authorize -> submit -> poll -> download -> hash -> register -> tech QC -> advance state

Backend-agnostic: HttpProductionBackend (real, runs where network is available, e.g. GH Actions)
or FakeBackend (tests; never hits the network, never creates paid renders).
"""
import os
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

from .states import State
from .approvals import GATE_CREATIVE
from .jobs import (JOB_SUBMITTED, JOB_POLLING, JOB_DOWNLOADING, JOB_QC_RUNNING, JOB_DONE,
                   JOB_HOLD, JOB_FAILED, JOB_RUNNING)
from . import mediaqc, production
from .util import sha256_file

PRODUCTION_ENDPOINT = "https://api.shotstack.io/edit/v1/render"
SECRET_ENV = "SHOTSTACK_PRODUCTION_API_KEY"


class TransientError(Exception):
    """Retryable (429, 5xx, timeout, connection reset, poll interruption)."""


class MaterialError(Exception):
    """Never retry -> route to HOLD (invalid JSON, auth/SHA mismatch, wrong env, render failed)."""


# --------------------------------------------------------------------------- backends
class RenderBackend:
    endpoint = PRODUCTION_ENDPOINT

    def assert_production(self):
        if "/stage/" in self.endpoint or "sandbox" in self.endpoint:
            raise MaterialError(f"refusing non-production endpoint: {self.endpoint}")

    def submit(self, frozen_path, out_name): raise NotImplementedError
    def poll(self, render_id): raise NotImplementedError            # -> (status, url)
    def download(self, url, dest): raise NotImplementedError        # -> path


class HttpProductionBackend(RenderBackend):
    """Real Shotstack Production backend (urllib). Key read from env only; never logged."""
    endpoint = PRODUCTION_ENDPOINT

    def _key(self):
        k = os.environ.get(SECRET_ENV)
        if not k:
            raise MaterialError(f"{SECRET_ENV} not set")
        return k

    def _req(self, url, method="GET", body=None):
        headers = {"x-api-key": self._key(), "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                raise TransientError(f"HTTP {e.code}")
            raise MaterialError(f"HTTP {e.code}: {e.read().decode()[:200]}")
        except (urllib.error.URLError, TimeoutError) as e:
            raise TransientError(f"network: {e}")

    def submit(self, frozen_path, out_name):
        self.assert_production()
        data = Path(frozen_path).read_bytes()
        resp = self._req(self.endpoint, "POST", data)
        rid = (resp.get("response") or {}).get("id")
        if not rid:
            raise MaterialError("no render id in submit response")
        return rid

    def poll(self, render_id):
        resp = self._req(f"{self.endpoint}/{render_id}")
        r = resp.get("response") or {}
        return r.get("status"), r.get("url")

    def download(self, url, dest):
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            raise TransientError(f"download: {e}")
        return dest


# --------------------------------------------------------------------------- executor
def _authorize(campaign, job):
    frozen_sha = job["frozen_json_sha256"]
    if not campaign.gate_ok(GATE_CREATIVE, frozen_sha):
        raise MaterialError("creative approval missing/invalid for this frozen SHA")
    if campaign.state == State.HOLD:
        raise MaterialError("campaign is on HOLD")
    if campaign.state not in (State.FROZEN_JSON_READY, State.PRODUCTION_AUTHORIZED):
        raise MaterialError(f"state {campaign.state.value} does not permit production")


def _retry(fn, attempts=4, base=0.2, sleep=time.sleep):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except TransientError as e:
            last = e
            sleep(base * (2 ** i))
    raise MaterialError(f"transient failure persisted: {last}")


def run_production_job(campaign, job, backend, frozen_path, out_name,
                       poll_interval=0.0, poll_max=200, sleep=time.sleep):
    """Execute one production job end-to-end. Idempotent: DONE jobs are not re-run."""
    q = campaign.jobs
    if job["status"] == JOB_DONE:
        return job  # idempotent no-op

    try:
        _authorize(campaign, job)
        backend.assert_production()
        try:
            production.assert_master_payload(frozen_path)   # invalid JSON / proof-range -> HOLD
        except production.ProductionError as e:
            raise MaterialError(str(e))

        # advance campaign into production
        if campaign.state == State.FROZEN_JSON_READY:
            campaign.transition(State.PRODUCTION_AUTHORIZED, "executor: authorize", actor="system")
        campaign.transition(State.PRODUCTION_RENDERING, "executor: submit")

        q.update(job["job_id"], status=JOB_RUNNING, attempt=job["attempt"] + 1)
        campaign.audit.record(campaign.cid, campaign.state.value, campaign.state.value,
                              "PRODUCTION_JOB_STARTED", "system", artifact=out_name,
                              extra={"job_id": job["job_id"]})
        rid = _retry(lambda: backend.submit(frozen_path, out_name), sleep=sleep)
        q.update(job["job_id"], status=JOB_SUBMITTED, shotstack_render_id=rid)

        # poll
        q.update(job["job_id"], status=JOB_POLLING)
        url = None
        for _ in range(poll_max):
            status, u = _retry(lambda: backend.poll(rid), sleep=sleep)
            if status == "done":
                url = u
                break
            if status == "failed":
                raise MaterialError("shotstack render failed")
            sleep(poll_interval)
        if not url:
            raise MaterialError("render poll timed out")

        # download + hash
        q.update(job["job_id"], status=JOB_DOWNLOADING)
        dest = Path(campaign.workdir) / out_name
        _retry(lambda: backend.download(url, str(dest)), sleep=sleep)
        out_sha = sha256_file(dest)
        campaign.register("production_master", str(dest), "production_mp4",
                          meta={"render_id": rid, "job_id": job["job_id"]})
        campaign._status["production_master"] = out_name
        campaign._save_status()
        campaign.transition(State.PRODUCTION_RENDER_READY, "executor: downloaded",
                            artifact=out_name, artifact_sha=out_sha)
        q.update(job["job_id"], output_artifact_id="production_master", output_sha256=out_sha)

        # chained tech QC (production success != QC success)
        q.update(job["job_id"], status=JOB_QC_RUNNING)
        rep = campaign.run_tech_qc(str(dest))
        if rep.get("qc_pass") is True:
            campaign.audit.record(campaign.cid, campaign.state.value, campaign.state.value,
                                  "TECH_QC_PASS", "system", artifact=out_name)
            campaign.transition(State.AWAITING_FINAL_VIDEO_APPROVAL, "executor: QC pass -> await final video")
            q.update(job["job_id"], status=JOB_DONE, tech_qc_status="PASS")
            campaign.audit.record(campaign.cid, campaign.state.value, campaign.state.value,
                                  "PRODUCTION_JOB_COMPLETED", "system", artifact=out_name,
                                  artifact_sha=out_sha, extra={"job_id": job["job_id"]})
        else:
            campaign.audit.record(campaign.cid, campaign.state.value, campaign.state.value,
                                  "TECH_QC_FAIL", "system", artifact=out_name)
            q.update(job["job_id"], status=JOB_HOLD, tech_qc_status="FAIL",
                     error="tech QC material failure")
        return q.get(job["job_id"])

    except MaterialError as e:
        if campaign.state != State.HOLD:
            campaign.hold(f"production executor: {e}")
        q.update(job["job_id"], status=JOB_HOLD, error=str(e))
        return q.get(job["job_id"])


# --------------------------------------------------------------------------- test backend
class FakeBackend(RenderBackend):
    """Deterministic backend for tests. Never hits network / never a paid render."""
    def __init__(self, endpoint=PRODUCTION_ENDPOINT, transient_before_success=0,
                 render_status="done", audio=True, duration=208.625, make_file=True):
        self.endpoint = endpoint
        self.transient_before_success = transient_before_success
        self.render_status = render_status
        self.audio = audio
        self.duration = duration
        self.make_file = make_file
        self._submits = 0

    def submit(self, frozen_path, out_name):
        self.assert_production()
        if self._submits < self.transient_before_success:
            self._submits += 1
            raise TransientError("simulated 429")
        self._submits += 1
        return "fake-render-123"

    def poll(self, render_id):
        return self.render_status, "https://api.shotstack.io/prod-out/fake.mp4"

    def download(self, url, dest):
        if self.make_file:
            Path(dest).write_bytes(b"FAKEMP4" * 100)
        return dest
