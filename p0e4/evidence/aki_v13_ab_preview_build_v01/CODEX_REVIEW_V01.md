# Code review — PR26, 2026-10-02
Reviewed head: 36a68df358be5a5965810ceda3b534e90c192587.
Status: CHANGES_REQUIRED_BEFORE_EXECUTION. No Resolve access or render performed.
Nitin's private A/B build authorization from 09:30 remains valid; this is a technical review, not a request to repeat creative approval.

Exact bytes verified:
- step1_import_readback.py: 77c7b9bafe6ffd965872ad1c6bcfd8ecc367987f4e778148f07761813da83984
- step2_build_render_ab.py: 1ce1bad4a7d034bd6a8f6087cdf8c91845ef29f9955509852a4942e0e4ab0e0b
Both parse as Python. Only isolated pure helper functions were evaluated; script top-level was never executed.

## Required fixes
1. step2 render(), lines 236-258: after 900 seconds the polling loop exits but never calls StopRendering. The assertion can fail while Resolve continues the job. On timeout, stop only the job started by this invocation using the supported scoped API (or project-level stop only while sole-job ownership is verified), verify it stopped, persist TIMEOUT/HOLD with job identity, and do not begin another variant. Persist failure state on render errors; avoid unconditional cleanup that touches unrelated work.

2. step2 verify_readback(), lines 189-208: only size keys, text/font/style and part of wiring are checked. Caption opacity/position keys, size/shading, T1/T2/T3 connections/centres and final MediaOut wiring are not validated. A targeted pure-function test confirmed acceptance of a synthetic comp whose caption has no opacity/position curves and no output connection, even though plan contains those curves. Compare actual keyframe values/frames and wiring against the plan; missing/empty matches must fail (all([]) is not evidence). Check disabled preexisting captions against their explicit inventory, including constant-zero blends. Add negative checks for dropped/changed caption curves and disconnected output. This does not replace pixel/media QC.

## Before mutation/render
- Inspect step1 readback against expected source mapping, FPS, audio and HLG settings, not merely equality with an arbitrary snapshot. Stop on mismatch.
- Keep actual output folder restriction and script hashes explicit. Current permissions are path-based, not hash-enforced; verify exact revised hashes immediately before execution and prevent changes between review and invocation. Do not describe folder Write permission as restricting script side effects.
- Existing auto-mode denial must be resolved through the supported local permission/approval process. Do not bypass the denial through another tool or route.

## Evidence corrections / preview limitations
- Reported onset 6.06s differs from nominal boundary 6.00s by 1.8 frames at 30fps. Do not claim all fixed boundaries meet a +/-1-frame beat tolerance. Verify or adjust actual boundaries, or explicitly report the unvalidated rhythm approximation for the private preview.
- Native 29.97fps and reported 30fps conform are not by themselves proof of a sync defect. Confirm the actual Resolve mapping and review resulting lipsync.
- peak_total_fusion_size currently uses peak * 2.3 and omits inherited rhythm pulses. Relabel as base-size estimate or compute actual composed peak; BUILD_STATUS quotes a larger pulse-inclusive value.
- Step3 QC/MP4 conversion is not included in this PR. Deliver it with actual results; do not claim completed A_PREVIEW/B_PREVIEW from step2 ProRes renders alone.
- No Gemini QC, media QC, readable-caption or safe-crop PASS is granted by this source review.

## Next action for local Claude
Fix these exact findings on this PR branch, update SHA256SUMS and REQUIRED_PERMISSIONS hashes, run meaningful offline negative checks, and provide the new head SHA. Preserve the original script revision in Git history. No generic redesign or new proposal round is needed.
