# R3 recovery review — 2026-10-02

Reviewed head: 639c07c497c7ccd87dd3898b78e5facaef353aef.
Disposition: specific comp-import failure addressed; eligible for one bounded R3 step2 attempt under existing build authorization and supported local permissions. Do not rerun step1.

- Verified step2 SHA256 c3b34f0f39a1fad7bec72a9af3ac8cab90a0169b54f2ec04f039de00155d5f90 and tests SHA256 934c534382c8f630480208fa8568ea4b1b329a48fa957c9f88aaff58baef16d0 against manifest. Both supplied Resolve fixture hashes and LOCAL_RUN_RESULT hash match.
- Independently ran suite: 19 discovered, 18 passed, 1 skipped (Mac-only local exports unavailable). Recorded fixture tests pass offline; no live Resolve run was performed here.
- swap_comp accepts observed in-place replacement or one added comp; unexpected name lists fail. Existing verify_readback still checks resulting content.
- Recovery requires the known base and failed A_V01 timeline. It duplicates the base into new R3 timelines, uses comps_r3 and new render/receipt paths, and leaves failed-run evidence untouched.
- LOCAL_RUN_RESULT reports step1 readback MATCH, no render jobs, base comp hashes unchanged and no original V13 project load. Those are builder-reported local observations, not independently inspected Mac state.

Next: obtain the supported local tool permission for the reviewed R3 command, verify hashes immediately before execution, confirm the expected recovery state and perform only step2 R3. Stop on drift or partial failure; no blind rerun. Then create the review MP4s, perform actual media QC and open both previews. Restore temporary rights and publish the receipt. Do not repeat creative approval requests.

Reported timelinePlaybackFrameRate is 24 while intended timeline/render rate is 30. Verify actual delivered 360-frame/12-second/30fps media and sync in step3; do not silently change source interpretation. Media quality, crop/face clearance, captions, lipsync and Gemini QC remain unproven by these tests. Production/publication remain unauthorized.
