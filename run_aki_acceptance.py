#!/usr/bin/env python3
"""Aakhri Ishq ACCEPTANCE TEST — reconstruct current state from real artifacts, no publish.

Verifies the automation reconstructs AKI to FINAL_VIDEO_APPROVED / PUBLISH=FALSE and hard-stops
at the publish gate. Does NOT rerender and does NOT publish.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from unpipe.orchestrator import Campaign
from unpipe.states import State
from unpipe.approvals import GATE_CREATIVE, GATE_FINAL_VIDEO
from unpipe import production
from unpipe.util import now_iso

OUTPUTS = HERE.parent  # .../outputs
FROZEN = OUTPUTS / "AKI_SHOTSTACK_FULL_MASTER_V01_FROZEN_EDIT.json"
RUNNER = OUTPUTS / "shotstack_production_render.sh"
MANIFEST = HERE / "campaigns" / "aakhri-ishq" / "campaign.json"
WORKDIR = HERE / "campaigns" / "aakhri-ishq" / "state"

def main():
    c = Campaign(WORKDIR, MANIFEST, runner_path=str(RUNNER))
    lines = []
    def log(x): lines.append(x); print(x)

    log(f"# Aakhri Ishq Acceptance — {now_iso()}")
    # 1. register real frozen master JSON (immutable creative contract)
    rec = c.register("frozen_master_v01", FROZEN, "frozen_edit_json")
    fsha = rec["sha256"]
    log(f"frozen_master_v01 SHA256 = {fsha}")

    # 2. reconstruct approvals from authoritative status (mission section 2):
    #    creative PASS, final video PASS, publish FALSE.
    c.approve(GATE_CREATIVE, "frozen_master_v01", fsha, by="Nitin",
              notes="Gemini 96.8/100; MUST_FIX=0; reconstruction")
    # production master binary is not in local workspace (rendered via local runner);
    # bind final-video approval to its declared/recorded sha token.
    master_sha = "AKI_PRODUCTION_MASTER_V01_SHA_PENDING_LOCAL_RENDER"
    c._status["production_master"] = c.manifest["production_master_name"]
    c.approve(GATE_FINAL_VIDEO, "production_master_v01", master_sha, by="Nitin",
              notes="NITIN_FINAL_VIDEO_APPROVAL = TRUE (authoritative)")
    # place at FINAL_VIDEO_APPROVED (reconstructed)
    c._status["current_state"] = State.FINAL_VIDEO_APPROVED.value
    c._status["last_successful_state"] = State.FINAL_VIDEO_APPROVED.value
    c._save_status()
    log(f"reconstructed state = {c.state.value}  video_approval={c._status['video_approval']}")

    # 3. advance automatic stages (derivatives plan -> packaging -> await publish). No publish.
    final = c.advance(master_path=c.manifest["production_master_name"], master_sha=master_sha)
    log(f"advanced to = {final.value}")

    # 4. rights + publish must be blocked
    rights = c.rights_ok()
    log(f"rights = {rights['status']} (pass={rights['pass']})")
    publish_blocked = False
    try:
        c.publish(master_sha)
    except PermissionError as e:
        publish_blocked = True
        log(f"publish correctly BLOCKED: {e}")

    # 5. results
    ok = (final == State.AWAITING_PUBLISH_APPROVAL and publish_blocked
          and c._status["video_approval"] and not c._status["publish_approval"])
    log("")
    log(f"CURRENT_AAKHRI_STATE = {c.state.value}")
    log(f"video_approval = {c._status['video_approval']} · publish_approval = {c._status['publish_approval']}")
    log(f"derivative_count = {c._status['derivative_count']} · packaging = {c._status['packaging_status']}")
    log(f"publication_status = {c._status['publication_status']} (must be NONE)")
    log(f"notifications outbox = {[n['state'] for n in c.notifier.outbox]}")
    log(f"ACCEPTANCE = {'PASS' if ok else 'FAIL'}")

    (HERE / "AAKHRI_ISHQ_ACCEPTANCE_REPORT.md").write_text("\n".join(lines) + "\n")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
