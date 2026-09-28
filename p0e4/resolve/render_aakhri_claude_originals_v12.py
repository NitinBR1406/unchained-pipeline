"""Bind the approved chain logo and flattened outro card to V13."""

import json
import time
from pathlib import Path

import DaVinciResolveScript as d

from aakhri_v12_repair_contract import (
    CHAIN_LOGO_SHA256,
    VISIBILITY_WINDOWS,
    resolve_chain_logo,
    sha256,
    verify_full_decode,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair"
PROJECT = "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR"
INTRO = OUT / "unchained_chain_emblem.png"
OUTRO = ROOT / "p0e4/evidence/claude_edit_posting_handoff_review_v01_execution/ORIGINAL_visualizer_outro.png"
BASE_RECEIPT = OUT / "RESOLVE_CHAIN_CAPTION_REPAIR_BASE_V13.json"
BASE_RENDERER = Path(__file__).with_name("render_aakhri_claude_intro_outro_v12.py")
CONTRACT = Path(__file__).with_name("aakhri_v12_repair_contract.py")


resolve_chain_logo(INTRO)
assert BASE_RECEIPT.exists(), "run caption/base repair before intro/outro render"
base_receipt = json.loads(BASE_RECEIPT.read_text())
assert base_receipt["project"] == PROJECT
assert base_receipt["repair_binding"] == {
    "renderer_sha256": sha256(BASE_RENDERER),
    "contract_sha256": sha256(CONTRACT),
}, "stale V12 project/receipt binding"
resolve = d.scriptapp("Resolve")
assert resolve and sha256(INTRO) == CHAIN_LOGO_SHA256 and OUTRO.exists()
manager = resolve.GetProjectManager()
project = manager.LoadProject(PROJECT)
assert project and not project.IsRenderingInProgress()
timeline = project.GetCurrentTimeline()
origin = timeline.GetStartFrame()
pool = project.GetMediaPool()
while timeline.GetTrackCount("video") < 2:
    assert timeline.AddTrack("video")

# Idempotent disposable execution: remove only prior V13 overlay clips.
prior = timeline.GetItemListInTrack("video", 2)
if prior:
    assert timeline.DeleteClips(prior, False)

imports = pool.ImportMedia([str(INTRO), str(OUTRO)])
by_name = {item.GetName(): item for item in imports}
intro_item = by_name[INTRO.name]
outro_item = by_name[OUTRO.name]

intro = pool.AppendToTimeline([{
    "mediaPoolItem": intro_item, "startFrame": 0, "endFrame": VISIBILITY_WINDOWS["chain_intro"][1],
    "mediaType": 1, "trackIndex": 2, "recordFrame": origin,
}])[0]
assert intro.SetProperty("ZoomX", 0.55)
assert intro.SetProperty("ZoomY", 0.55)
assert intro.SetProperty("Tilt", 420.0)

outro = pool.AppendToTimeline([{
    "mediaPoolItem": outro_item, "startFrame": 0, "endFrame": 119,
    "mediaType": 1, "trackIndex": 2, "recordFrame": origin + VISIBILITY_WINDOWS["outro_card"][0],
}])[0]

assert manager.SaveProject()
drp = OUT / f"{PROJECT}.drp"
assert manager.ExportProject(PROJECT, str(drp), False)
render = OUT / "AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR_HLG_PRORES.mov"
assert resolve.OpenPage("deliver")
assert project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetCurrentRenderMode(1)
assert project.SetRenderSettings({
    "SelectAllFrames": False, "MarkIn": origin, "MarkOut": origin + 719,
    "TargetDir": str(OUT), "CustomName": render.stem,
    "ExportVideo": True, "ExportAudio": True,
    "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
    "AudioCodec": "lpcm", "AudioSampleRate": 48000,
})
job = project.AddRenderJob(); assert job
assert project.StartRendering([job], False)
deadline = time.monotonic() + 1800
while project.IsRenderingInProgress() and time.monotonic() < deadline:
    time.sleep(0.5)
assert not project.IsRenderingInProgress()
status = project.GetRenderJobStatus(job)
assert status.get("JobStatus") == "Complete" and render.exists(), status
project.DeleteRenderJob(job)
decode = verify_full_decode(render)

receipt = {
    "schema": "RESOLVE_CHAIN_CAPTION_REPAIR_V13",
    "project": PROJECT,
    "timeline": timeline.GetName(),
    "rendered_frames": [0, 719],
    "intro": {
        "identity": "NITIN_APPROVED_GOLD_UN_BROKEN_CHAIN",
        "frames": list(VISIBILITY_WINDOWS["chain_intro"]),
        "sha256": sha256(INTRO),
        "expected_sha256": CHAIN_LOGO_SHA256,
    },
    "outro": {"frames": [600, 719], "sha256": sha256(OUTRO), "exact_wording": ["UNCHAINED NITIN", "~ THE INDESTRUCTIBLE VOICE ~", "FOLLOW FOR MORE", "@UnchainedNitin"]},
    "render": {"path": str(render), "sha256": sha256(render), "bytes": render.stat().st_size},
    "drp": {"path": str(drp), "sha256": sha256(drp), "bytes": drp.stat().st_size},
    "render_status": status,
    "full_decode": decode,
    "base_binding": {
        "receipt_sha256": sha256(BASE_RECEIPT),
        "renderer_sha256": sha256(BASE_RENDERER),
        "contract_sha256": sha256(CONTRACT),
    },
    "independent_gemini_qc": "REQUIRED_ON_EXACT_RENDER_SHA_NOT_RUN_BY_THIS_SCRIPT",
    "nitin_approval": False,
    "publication_authorized": False,
}
(OUT / "RESOLVE_CHAIN_CAPTION_REPAIR_V13.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
