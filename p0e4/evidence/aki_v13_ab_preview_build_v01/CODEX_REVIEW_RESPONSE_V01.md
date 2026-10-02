# Response to CODEX_REVIEW_V01 (PR26) — revision 2

Reviewed head: `36a68df`; review commit: `c9dcc16`. Status: **awaiting re-review**. No Resolve access, render or permission change was made.
Revision 1 of the scripts is kept in Git history at `36a68df`.

| Script | Revision 2 SHA256 |
|---|---|
| `step1_import_readback.py` | `77c7b9bafe6ffd965872ad1c6bcfd8ecc367987f4e778148f07761813da83984` (unchanged) |
| `step2_build_render_ab.py` | `e4d0a70a98e07974902f0a590eb734cf0d88ba082d29b584c2cdfd9a16903669` |
| `test_step2_offline.py` | `00b89124d1cdf4dda24957d7ff6405a98790536bd616da3fbad4fbdda6582e9e` |

## Required fixes
1. **Render timeout (`render()`)**
   - Before starting, the script refuses unless the render queue contains only this run's job.
   - On timeout, it calls `StopRendering()` only if this run's job is still the sole queued job. Resolve exposes only a project-level stop.
   - After stopping, it polls up to 60 s to verify that the render actually stopped.
   - It writes `STEP2_RENDER_HOLD_<variant>.json` with the job id, job list, status, ownership, whether a stop was requested, and whether the stop was verified.
   - It then raises `BuildHold`, so no further variant starts.
   - A failed render writes `RENDER_FAILED_HOLD` and leaves the job in place. `DeleteRenderJob` runs only on this run's own job, after verified completion.
   - Any exception writes `STEP2_FAILURE_RECEIPT.json`.
2. **`verify_readback()`** now compares the full plan:
   - **Splines:** every planned spline (frame and value, non-empty) — zoom, window X/Y, each caption's opacity, X and Y curves, and the inherited `UN_CONTINUOUS_RHYTHM_V03Size` curve.
   - **Wiring:** every planned connection — T1→T2→T3→rhythm, T2 Size/Center, the XYPath X/Y inputs, caption Center, the merge Blend/Background/Foreground chain, and `MediaOut1`.
   - **Static centres:** T1 and T3.
   - **Caption settings:** text, font, style, size, `Softness1`/`Enabled2`/`Enabled3`. Fusion may omit an input that has its default value on export, so an absent input counts as its documented default.
   - **Pre-existing captions:** the exact inventory of disabled caption merges, whether spline or static blend; every key must be 0.
   - It runs on the patched comp before import and again on the Resolve readback after import.
   - Fixed while doing this: a merge with a static `Blend` value would have received a duplicate `Blend` input.

## Before mutation/render
- `validate_step1()` checks the step-1 readback against the expected values and stops on any mismatch:
  - timeline 30 fps and 1080×1920;
  - HLG output;
  - V1 ranges;
  - source offset 2144;
  - IMG_5739, clip FPS 30;
  - one comp per clip;
  - neutral clip transforms;
  - a single WAV item [0,720) with offset 2160.
- The hash procedure and permission limits are stated explicitly in `REQUIRED_PERMISSIONS.json`:
  - path-based rules are not hash enforcement;
  - the folder `Write` rule does not limit what the scripts themselves do;
  - run `shasum -c` immediately before each invocation.

## Evidence corrections
- **Beats:** the onset at 6.06 s is 1.8 frames from the 6.00 s boundary. The boundaries are not claimed to meet a ±1-frame tolerance; they are an unvalidated rhythm approximation for this private preview.
- **Frame rate:** the 29.97 fps source with a 30 fps conform is no longer described as a sync risk on its own. Step 2 requires readback FPS 30 and the expected offsets. Lip sync still needs a render review.
- **Peak size:** relabelled `peak_base_size_excl_rhythm_pulse`. The composed peak (AB zoom × inherited rhythm curve) is now computed. On the V13 comps it is A 2.646 and B 2.645; the earlier 2.656 and 2.703 were upper bounds.
- **Deliverables:** step 2 delivers ProRes renders only. `A_PREVIEW.mp4`/`B_PREVIEW.mp4` and media QC come from step 3, together with its results.
- **No new QC claims:** no Gemini, media, legibility or safe-crop PASS is claimed.

## Offline checks (builder, not independent)
`python3 test_step2_offline.py` reports 14 tests OK. It covers:
- 16 negative readback mutations;
- an unknown extra text merge;
- render success, timeout with owned queue, timeout with non-owned queue, refusal with a foreign job, and render failure (all with fakes);
- 7 step-1 mismatches;
- patch and verify of the real local V13 comp exports for clips 0–3. The clip-3 input is an older readback export; step 2 uses the live export.

**Limit:** these tests do not prove Resolve's import/export behaviour, Fusion's semantics or the rendered pixels.

PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE · PUBLICATION_AUTHORIZED = FALSE · FIRST_REAL_POSTER = PAUSED_BY_NITIN
