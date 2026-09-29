# UNCHAINED_PREMIUM_STYLE_SAMPLE_20260929_V02 — premium style plan (not rendered)

The authoritative data is in `PREMIUM_STYLE_SAMPLE_PLAN_V02.json`; this page is a summary. The plan was read at commit `3e1b268f…` (identical SHA fetched read-only from GitHub; macOS blocked this session from reading `~/Downloads`). It builds on the V13 base: master `7266506b…`, DRP `f1e720b6…`.

## Fix this first — V13 still stacks captions (HIGH)
On clip 1 (frames 89–203), V13 fades in `Merge1`/`Merge2`. In the inherited comp, those merges carry the **small old hook and the song-id**; title and artist sit on `Merge3`/`Merge4`. The V13 contact sheet (`cf872fca…`, row 2, cells 4–5) shows "UNCHAINED NITIN", the small hook and "AAKHRI ISHQ" stacked on top of each other. This matches Nitin's V12 overlap complaint, and the Gemini PASS missed it.

Rule for the fix: find each caption through the Merge Foreground `SourceOp`, never through the Merge name. Set the song-id to 0 in every clip.

## Two treatments on the same excerpt (frames 0–344, 11.5 s)
Audio, V06 LUT colour, crop/geometry, rhythm transform and cuts all stay exactly as in V13. No new effects are added.

| | A — Engraved Stillness (recommended) | B — Gold Accent Rise |
|---|---|---|
| Chain logo | 0–53: fade in 0–10, one light pass 14–32, fade out 41–53 (both) | same |
| Hook (Montserrat Medium, off-white) | visible 61–145, size 0.090, tracking 1.06 | visible 61–131, size 0.092, **"END." in warm gold** (the only accent) |
| Title (Cinzel SemiBold, warm gold) | 161–313, 0.115, tracking 1.12 | 149–299, 0.120, rises 0.006 on entry |
| Artist (Montserrat Medium, off-white) | 167–313, 0.066, tracking 1.30 | 155–299, 0.068 |
| Motion | opacity only, 12-frame smoothstep | opacity plus a subtle rise |

- Hook and title windows never overlap. There are at least 8 clear frames between logo and hook, and at least 15 between hook and title.
- The hook crosses cut 89 and the title crosses cut 204. The keys stay continuous (1.0 on both sides of each cut) and the text inputs are identical across the cut.

**Colour values** (HLG signal values; the implementer must first read back that the timeline really is HLG, and stop if it isn't):
- Off-white: 0.75 / 0.735 / 0.70
- Warm gold: 0.75 / 0.645 / 0.285

These follow ITU-R BT.2408, which puts HDR graphics white at 75%. V13 draws its gold at 100% of the HDR signal, which can look glaring on HDR phones.

**Logo:** the gold UN broken-chain emblem `5e77eb7a…` (lightning `9ec01839…` is forbidden). Keep V13's placement exactly: zoom 0.30, tilt −3000. The light pass is a masked Screen gradient that only touches pixels inside the logo. No glow, blur, shadow or scaling is added.

**Checks that stop the job on failure:**
- Intended and read-back comp hashes are stored separately.
- Read back every text input and blend curve.
- The tool inventory may only change as allowed in the plan.
- Render a CONTROL pass (no captions, no logo) plus separate logo/hook/title passes. These drive per-frame checks for window compliance, collisions, unplanned leftover text, face clearance (a missing face detector counts as a failure) and PCM equality.
- Any check that cannot run is recorded as a limitation, never as PASS.

**Coverage limitation:** the 4 s outro plus the 1.8 s intro already take up 24% of 24 s. This preview cannot show that the full clip meets the ≥ 75% text-free rule.

Nothing was rendered, deployed, posted or approved, and no Make scenario was touched.

PREMIUM_STYLE_SAMPLE_PLAN_COMPLETE
