"""Campaign orchestrator: ties state machine, approvals, registry, audit, QC, production,
adapters. Local-first, isolated per campaign (no global state -> parallel campaigns safe)."""
from pathlib import Path
from .states import State, can_transition, GATE_STATES
from .approvals import (ApprovalStore, GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH,
                        APPROVE, REJECT)
from .registry import ArtifactRegistry
from .audit import AuditLog
from .manifest import load_manifest
from .adapters import (DerivativeEngine, PackagingEngine, RightsGate,
                       default_publish_adapters, AnalyticsAdapter, Notifier)
from . import mediaqc, production
from .jobs import JobQueue
from .util import write_json, read_json, now_iso, sha256_file
import os
from pathlib import Path as _Path


class Campaign:
    def __init__(self, workdir, manifest_path, runner_path=None):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.manifest = load_manifest(manifest_path)
        self.manifest_dir = _Path(manifest_path).resolve().parent
        self.cid = self.manifest["campaign_id"]
        self.runner_path = runner_path
        self.jobs = JobQueue(self.workdir / "jobs.json")
        self.approvals = ApprovalStore(self.workdir / "approvals.json")
        self.registry = ArtifactRegistry(self.workdir / "registry.json")
        self.audit = AuditLog(self.workdir / "audit.jsonl")
        self.notifier = Notifier()
        self.publish_adapters = default_publish_adapters()
        self.status_path = self.workdir / "CAMPAIGN_STATUS.json"
        self.ops_path = self.workdir / "operations.json"     # idempotency ledger
        self._status = read_json(self.status_path, default=None) or self._init_status()
        self._ops = read_json(self.ops_path, default={}) or {}

    # ------------------------------------------------------------------ status
    def _init_status(self):
        s = {
            "campaign_id": self.cid,
            "current_state": State.SOURCE_READY.value,
            "last_successful_state": State.SOURCE_READY.value,
            "blocking_issue": None,
            "creative_approval": False,
            "video_approval": False,
            "publish_approval": False,
            "source_asset": self.manifest.get("source_master"),
            "preview_asset": None,
            "production_master": None,
            "derivative_count": 0,
            "packaging_status": "NONE",
            "publication_status": "NONE",
            "analytics_status": "NONE",
            "updated_at": now_iso(),
        }
        write_json(self.status_path, s)
        return s

    def _save_status(self):
        self._status["updated_at"] = now_iso()
        write_json(self.status_path, self._status)

    @property
    def state(self):
        return State(self._status["current_state"])

    # ------------------------------------------------------------------ transitions
    def transition(self, dst: State, operation, actor="system", artifact=None, artifact_sha=None,
                   error=None):
        src = self.state
        if not can_transition(src, dst):
            raise ValueError(f"illegal transition {src.value} -> {dst.value}")
        self._status["current_state"] = dst.value
        if dst not in (State.HOLD, State.FAILED, State.TECH_QC_FAIL,
                       State.CREATIVE_REJECTED, State.FINAL_VIDEO_REJECTED, State.PUBLISH_REJECTED):
            self._status["last_successful_state"] = dst.value
        if dst in (State.HOLD, State.TECH_QC_FAIL, State.FAILED):
            self._status["blocking_issue"] = error or operation
        elif dst not in GATE_STATES:
            self._status["blocking_issue"] = None
        self._save_status()
        self.audit.record(self.cid, src.value, dst.value, operation, actor,
                          artifact=artifact, artifact_sha=artifact_sha,
                          result="OK" if dst != State.HOLD else "HOLD", error=error)
        self.notifier.maybe_notify(self.cid, dst.value)
        return dst

    def hold(self, reason, actor="system"):
        return self.transition(State.HOLD, f"HOLD: {reason}", actor=actor, error=reason)

    # ------------------------------------------------------------------ artifacts + gates
    def register(self, artifact_id, path, kind, meta=None):
        return self.registry.register(artifact_id, path, kind, meta=meta)

    def approve(self, gate, asset_id, artifact_sha256, by="Nitin", decision=APPROVE, notes=""):
        rec = self.approvals.record(self.cid, asset_id, gate, decision, by, artifact_sha256, notes)
        self.audit.record(self.cid, self.state.value, self.state.value,
                          f"GATE {gate} {decision}", by, artifact=asset_id, artifact_sha=artifact_sha256)
        # mirror booleans into status (only true if bound to current sha checked later)
        if gate == GATE_CREATIVE:
            self._status["creative_approval"] = (decision == APPROVE)
        elif gate == GATE_FINAL_VIDEO:
            self._status["video_approval"] = (decision == APPROVE)
        elif gate == GATE_PUBLISH:
            self._status["publish_approval"] = (decision == APPROVE)
        self._save_status()
        if gate == GATE_CREATIVE and decision == APPROVE:
            self._maybe_queue_production(artifact_sha256)  # zero-terminal trigger (V1.1)
        return rec

    def _resolve_frozen(self):
        fm = self.manifest.get("frozen_master")
        if not fm:
            return None
        p = _Path(fm) if os.path.isabs(fm) else (self.manifest_dir / fm)
        p = p.resolve()
        return p if p.exists() else None

    def _maybe_queue_production(self, approval_sha):
        """On valid creative approval, auto-queue a production job (idempotent). No terminal."""
        p = self._resolve_frozen()
        if not p:
            return None
        if sha256_file(p) != approval_sha:
            return None  # approval must bind to the actual frozen file
        self.register("frozen_master", str(p), "frozen_edit_json")
        job, created = self.jobs.enqueue(self.cid, "frozen_master", approval_sha, GATE_CREATIVE)
        self.audit.record(self.cid, self.state.value, self.state.value,
                          "auto-queue production job" if created else "production job idempotent-reuse",
                          "system", artifact="frozen_master", artifact_sha=approval_sha,
                          extra={"job_id": job["job_id"]})
        return job

    def gate_ok(self, gate, current_sha):
        return self.approvals.is_approved(self.cid, gate, current_sha)

    # ------------------------------------------------------------------ production + QC
    def run_production_master(self, frozen_json_path, out_name, execute=True):
        # requires creative approval bound to the frozen JSON sha
        frozen_sha = production.assert_master_payload(frozen_json_path)
        if not self.gate_ok(GATE_CREATIVE, frozen_sha):
            raise PermissionError("production blocked: creative approval missing/invalid for this frozen JSON")
        if self.state != State.FROZEN_JSON_READY:
            raise ValueError(f"production requires FROZEN_JSON_READY (current {self.state.value})")
        self.transition(State.PRODUCTION_AUTHORIZED, "authorize production", actor="Nitin",
                        artifact=str(frozen_json_path), artifact_sha=frozen_sha)
        self.transition(State.PRODUCTION_RENDERING, "submit production render")
        res = production.render_master(frozen_json_path, self.runner_path, out_name,
                                       cwd=str(self.workdir), execute=execute)
        if not res.get("executed"):
            # cannot execute here (no secret / proxy) -> HOLD with the local command
            self.hold("production not executable in this environment; run runner locally")
            return res
        if res.get("return_code") == 0:
            self.transition(State.PRODUCTION_RENDER_READY, "production render done")
        else:
            self.transition(State.TECH_QC_FAIL, "production render failed",
                            error="runner non-zero exit")
        return res

    def run_tech_qc(self, master_path):
        self.transition(State.TECH_QC_RUNNING, "start tech QC")
        expected = {"duration": self.manifest["duration"],
                    "width": self.manifest.get("width", 1080),
                    "height": self.manifest.get("height", 1920),
                    "fps": self.manifest["fps"], "duration_tol": 0.6}
        rep = mediaqc.run_media_qc(master_path, expected, self.workdir / "TECH_QC_REPORT.json")
        if rep.get("qc_pass") is True:
            self.transition(State.TECH_QC_PASS, "tech QC pass")
        else:
            self.hold("tech QC failed or ffprobe unavailable")
        return rep

    # ------------------------------------------------------------------ post-approval automation
    def build_derivatives(self, master_path):
        eng = DerivativeEngine()
        plan = eng.plan(self.cid, master_path, self.manifest["platform_targets"])
        write_json(self.workdir / "DERIVATIVE_PLAN.json", plan)
        self._status["derivative_count"] = len(plan["targets"])
        self._save_status()
        return plan

    def build_packaging(self):
        pkg = PackagingEngine().build(self.cid, self.manifest["platform_targets"],
                                      {"title": self.manifest["song_title"],
                                       "rights_status": (self.manifest.get("rights") or {}).get("status")})
        write_json(self.workdir / "PACKAGING.json", pkg)
        self._status["packaging_status"] = "READY"
        self._save_status()
        return pkg

    def rights_ok(self):
        return RightsGate().evaluate(self.manifest.get("rights"))

    def publish(self, current_master_sha):
        """Publish only if all gates satisfied. Idempotent per platform."""
        if not self.gate_ok(GATE_PUBLISH, current_master_sha):
            raise PermissionError("publish blocked: NITIN_PUBLISH_APPROVAL missing/invalid")
        r = self.rights_ok()
        if not r["pass"]:
            self.hold(f"rights gate not passed ({r['status']})")
            raise PermissionError(f"publish blocked: rights {r['status']}")
        results = {}
        for plat, adapter in self.publish_adapters.items():
            op_key = f"publish:{plat}:{current_master_sha}"
            if self._ops.get(op_key):  # idempotency: already done
                results[plat] = {**self._ops[op_key], "idempotent_skip": True}
                continue
            res = adapter.publish({"campaign_id": self.cid, "platform": plat})
            self._ops[op_key] = res
            results[plat] = res
        write_json(self.ops_path, self._ops)
        return results

    # ------------------------------------------------------------------ deterministic advance
    def advance(self, master_path=None, master_sha=None):
        """Execute the next AUTHORIZED automatic stage. Stops at unsatisfied gates / HOLD."""
        s = self.state
        if s == State.FINAL_VIDEO_APPROVED:
            self.transition(State.DERIVATIVES_BUILDING, "auto: build derivatives")
            self.build_derivatives(master_path or self._status.get("production_master") or "N/A")
            self.transition(State.DERIVATIVES_READY, "derivatives plan ready")
            return self.advance(master_path, master_sha)
        if s == State.DERIVATIVES_READY:
            self.transition(State.PACKAGING_BUILDING, "auto: build packaging")
            self.build_packaging()
            self.transition(State.PACKAGING_READY, "packaging ready")
            return self.advance(master_path, master_sha)
        if s == State.PACKAGING_READY:
            self.transition(State.AWAITING_PUBLISH_APPROVAL, "await publish approval")
            return self.state  # HARD STOP at gate
        if s == State.PUBLISH_APPROVED:
            self.transition(State.PUBLISHING, "auto: publish")
            self.publish(master_sha)
            self.transition(State.PUBLISHED, "published")
            self.transition(State.ANALYTICS_ACTIVE, "analytics active")
            self._status["publication_status"] = "PUBLISHED"
            self._status["analytics_status"] = "ACTIVE"
            self._save_status()
            return self.state
        return self.state  # nothing to auto-advance (gate/manual step)
