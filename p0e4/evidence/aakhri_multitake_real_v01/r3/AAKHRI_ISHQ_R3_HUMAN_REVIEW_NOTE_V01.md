# Aakhri Ishq R3 — QC rejected human review candidate

Status: `QC_REJECTED_HUMAN_REVIEW_CANDIDATE`

Candidate SHA256: `baa675588c3fb3bd57bec71b0261f76a4a28eff74047f8673c3e0aceb0ac7487`

Technical QC: `GREEN` — the R3 master and all four derivatives completed full AVFoundation decode; local framing checks found no ceiling, floor or white lower border after Repair 5.

Independent Gemini QC: `REPAIR_REQUIRED`.

Review these reported ranges against the actual video:

- `00:09–00:21` — reported forehead texture/shadow artifact.
- `01:13–01:29` — reported recurring forehead texture/shadow artifact.
- `01:33–01:58` — reported excessive or distracting movement/shake.
- `01:52–01:54` — special attention: reported mouth/tongue distortion and possible lip-sync concern.

Nitin review instruction: confirm each reported defect, reject it as a false positive, or request a specific bounded repair. This candidate is not POST_READY, final-video-approved, final-asset-approved, rights-cleared or publish-ready.

Governance remains: `PRODUCTION_DEPLOYMENT_AUTHORIZED=false`, `PUBLICATION_AUTHORIZED=false`, `FIRST_REAL_POSTER=PAUSED_BY_NITIN`.
