# Codex technical review — PR30 V01
Date: 2026-10-02. Reviewed source head: 6d5d9776330df3c3d16562ab1093af1a7cd48440.
Reviewer: Work/Codex cloud session; no Mac/Resolve execution or media inspection.

## Decision
TECHNICAL_REVIEW_COMPLETE_FOR_SCOPED_PRIVATE_EXECUTION, with the factual correction below.
No critical execution defect identified in the reviewed source. The existing Nitin private-build authorization remains the authority; this review does not grant OS/tool permissions or final creative approval.
No additional creative selection or manual step-1 message relay is necessary: step2.validate_step1 already checks the persisted step-1 identity, source offsets, track layout and neutral transforms. Claude must inspect that local readback itself and stop on a mismatch. Use the normal supported local permission route where a technical permission is actually required; never bypass a deny.

## Verified here
- Retrieved all 13 PR files at the reviewed commit; all 12 SHA256SUMS entries match exact bytes.
- Executed test_full24_offline.py on the downloaded source: 20/20 PASS. These are offline tests with actual V13 comp fixtures and mocked Resolve operations, not live render proof.
- Inspected step1, overlay generation, full step2 and test implementation.
- New isolated project/timeline names; original DRP hash binding; base comp/V2/audio before/after comparison; explicit readback of planned Fusion animation/text/output reachability; detached lightning-logo input rejected if made reachable.
- Render covers inclusive marks origin+0 through origin+719. Exclusive AppendToTimeline endFrame is consistent with repository INSTALLED_ACCEPTANCE_CONTRACT_V163.md for installed Resolve 21.1; live readback still enforces actual placement.
- Owned render-job check, timeout stop/readback and HOLD retained; no automatic rerender on uncertainty.
- 143-frame conservative overlay union, leaving 80.14% unobstructed, and 1.15 peak relative zoom are verified from the offline plan. Actual output checks remain required.

## Factual correction: protected R4 span is not completely identical
A direct comparison with executed R4 step2 (SHA a3ab4952b676e0650a5fde32e54d1ad86bd96d8f29c8b90494416e7b6fbe26b0) shows:
- global frames 60–68 have a new punch in full24; R4 excerpt begins at global60 and therefore had no opening punch.
- Full24 zoom values are 1.015, 1.03, 1.02625, 1.0225, 1.01875, 1.015, 1.01125, 1.0075, 1.00375; old R4 values were all1.0.
- Frames69–419 match the R4 zoom/reframe schedule.
- test_selected_r4_b_span_preserved checks shot tuples only and does not establish per-frame equivalence.
This is a small in-scope rhythmic extension, within the approved zoom cap, not a reason for another creative approval cycle. Do not claim the whole [60,420) animation is identical. Record this exception in the execution receipt; captions intentionally differ as requested. If exact preservation is implemented instead, changed script bytes need an updated review/hash.

## Runtime and visual checks still open
Actual source availability, installed font resolution, local tool permission, successful Fusion import, render/decode, 720-frame duration, complete PCM comparison, perceptual lipsync, headroom and moving-caption legibility are not proved by these offline tests.
Caption bottom placement may collide with social UI: acceptable for the scoped private review, not platform-safe-area certification.
Overlay manifest hashes bind generated files but are not an independent logo-generation attestation; verify approved source logo, generated alpha/position, exact scripts and manifest as described.
The supported path-based local permission rules are not hash-enforced OS isolation. Verify exact script hashes immediately before use. No policy/deny removal is authorized by this review.
An interrupted process/uncertain Resolve state must be reconciled before any repeat execution. The script's controlled timeout handling is not OS-wide crash recovery.

## Handoff without user relay
This review is now repository evidence available to the existing Claude session. A repository write does not prove that session read it; no direct session wake-up is claimed. The separate no-relay automation work must close that transport boundary.
After supported permissions are present, continue the already-authorized private build, perform actual media QC, deliver the private video link and compact receipt. Do not label a script or test run as a completed video.

PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE
PUBLICATION_AUTHORIZED = FALSE
FIRST_REAL_POSTER = PAUSED_BY_NITIN
