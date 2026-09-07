#!/usr/bin/env python3
"""Cover #2 READINESS dry-run: exercises the full zero-terminal path with a FAKE backend.
No network, no paid render, no publish. Simulates what GitHub Actions would do after approval.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from unpipe.orchestrator import Campaign
from unpipe.states import State
from unpipe.approvals import GATE_CREATIVE
from unpipe import mediaqc, executor
from unpipe.dispatcher import FakeDispatcher
from unpipe.util import sha256_file, now_iso

import tempfile
MANI = HERE / "campaigns" / "cover-2-dryrun" / "campaign.json"
WORK = Path(tempfile.mkdtemp(prefix="cover2_dryrun_")) / "state"   # fresh, ephemeral each run
FROZEN = HERE / "campaigns" / "cover-2-dryrun" / "frozen_dryrun.json"


def main():
    lines = []
    def log(x): lines.append(x); print(x)
    log(f"# Cover #2 dry-run — {now_iso()}")

    disp = FakeDispatcher()   # stands in for the GitHub repository_dispatch call
    c = Campaign(WORK, MANI, runner_path="/x", dispatcher=disp)
    # source registration
    c.register("source_master", MANI, "source_ref")   # ref only (binary on Drive)
    log("source registered")

    # creative approval -> auto-queues production job AND auto-dispatches the workflow (V1.1.1)
    sha = sha256_file(FROZEN)
    c.approve(GATE_CREATIVE, "frozen_master", sha, by="Nitin", notes="dry-run creative approve")
    jobs = c.jobs.all()
    log(f"after creative approve: jobs queued = {len(jobs)} · dispatch calls = {disp.calls} "
        f"(frozen SHA {sha[:12]}…)")
    assert len(jobs) == 1, "creative approval must auto-queue exactly one job"
    assert disp.calls == ["cover-2-dryrun"], "creative approval must auto-dispatch exactly once"
    log("=> APPROVE auto-dispatched the render workflow (no GitHub UI, no terminal)")

    # move to FROZEN_JSON_READY (system) and run the executor with a FAKE production backend
    c._status["current_state"] = State.FROZEN_JSON_READY.value; c._save_status()

    # simulate a good production output for QC (FakeBackend writes a stub file; QC is stubbed to pass)
    mediaqc.ffprobe_available = lambda: True
    mediaqc.probe = lambda p: {
        "streams": [{"codec_type": "video", "width": 1080, "height": 1920,
                     "r_frame_rate": "24/1", "codec_name": "h264"},
                    {"codec_type": "audio", "codec_name": "aac", "duration": "208.6"}],
        "format": {"duration": "208.625", "format_name": "mp4"}}

    be = executor.FakeBackend(transient_before_success=1)  # also proves retry
    res = executor.run_production_job(c, jobs[0], be, str(FROZEN),
                                     c.manifest["production_master_name"], sleep=lambda s: None)
    log(f"executor job status = {res['status']} · qc = {res.get('tech_qc_status')} · "
        f"render_id = {res.get('shotstack_render_id')} · out_sha = {str(res.get('output_sha256'))[:12]}…")
    log(f"campaign state after render+QC = {c.state.value}")
    log(f"notifications = {[n['state'] for n in c.notifier.outbox]}")

    # idempotency: re-run must not resubmit
    subs = be._submits
    executor.run_production_job(c, jobs[0], be, str(FROZEN), c.manifest["production_master_name"],
                               sleep=lambda s: None)
    log(f"idempotent re-run: submits unchanged = {be._submits == subs}")

    ok = (res["status"] == "DONE" and res["tech_qc_status"] == "PASS"
          and c.state == State.AWAITING_FINAL_VIDEO_APPROVAL
          and be._submits == subs and not c._status["publish_approval"])
    log("")
    log("Zero-terminal checks (simulated executor path):")
    log("  Nitin action = CREATIVE APPROVE only")
    log("  GitHub Actions UI / Run-workflow / campaign_id entry by Nitin = NONE (auto-dispatched)")
    log("  terminal / curl / key-copy / polling / download / ffprobe by Nitin = NONE")
    log(f"  publish performed = NO · publish_approval = {c._status['publish_approval']}")
    log(f"COVER2_DRYRUN = {'PASS' if ok else 'FAIL'}")

    (HERE / "COVER2_DRYRUN_REPORT.md").write_text("\n".join(lines) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
