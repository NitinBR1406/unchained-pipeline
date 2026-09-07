# Cover #2 Onboarding

Goal: run a new cover through the system with Nitin only recording, reviewing, and approving.

## Steps
1. Copy `campaigns/aakhri-ishq/campaign.json` to `campaigns/<cover2-id>/campaign.json` and edit:
   `campaign_id`, `song_title`, `source_master`, `duration`, `rights`, `platform_targets`.
   Keep `presentation_preset = MOTION_A_PREMIUM_RESTRAINED` and `brand_profile` unchanged.
2. Provide the verified lyric master + caption schedule + motion cues for the song (same shape as
   AKI). The presentation builder reuses the locked V03A visual language automatically.
3. System builds the edit and a sandbox preview. **Nitin approves creative (Gate 1).**
4. System freezes JSON, renders production master, runs tech QC. **Nitin approves final video (Gate 2).**
5. System builds derivatives + packaging. Complete rights review to RIGHTS_PASS.
   **Nitin approves publish (Gate 3).** System publishes + starts analytics.

## Cover #2 acceptance target (no manual grunt work)
NO manual curl · NO per-render API key entry · NO manual polling · NO manual URL extraction ·
NO manual ffprobe · NO manual Drive routing · NO manual derivative cutting · NO manual metadata copy.

Human work = record, review, approve/reject, artist decisions.

## Current gap for full "no terminal"
The production render step still launches the local runner (proxy blocks the API from the hosted env).
Closing debt item #1 in CAPABILITY_MATRIX.md (hosted runner / production connector) removes the last
terminal touch from the normal flow.
