# AKI twin — private local reference build
Task: AKI_TWIN_REFERENCE_EXTRACTION_20261019_V01, revision 1.
Parent: AKI_TWIN_PREFLIGHT_20261019_V01 R4, result PR #47.
State: PREPARED_FOR_LOCAL_EXECUTOR; no ACK or execution claimed.
Executor: existing interactive Claude Code session on Nitin's Mac with private campaign-register and Drive access. NOT the proposal-only headless runner.

## User authorization
Nitin chose existing Aakhri Ishq imagery and real audio as reference and authorized local reference preparation. Latest instruction 2026-10-19 23:58 Europe/Amsterdam: "Oké ga autonoom aan de slag met Claude en Gemini om de twin asap op te leveren".
Do not request new photographs or repeat reference-use approval. Keep the existing review boundary before a new AI provider upload, training, paid generation, new accounts or publication. This is not permission to expand tool rights, alter runner settings or bypass gates. Existing AKI campaign is untouched.

## Deliver now
A PRIVATE reference pack with contact sheets, 8–15 suitable candidate stills where the source supports them, and 1–3 real-singing excerpts of at least 10 seconds. If fewer suitable frames exist, deliver the available set with an honest limitation, not a fabricated pass. No twin generation in this stage.
Use the existing approved AKI master and audio from the private register. Resolve exact current source identity locally; no historical filename, duration or hash is authoritative without checking.

## Execution
1. ACK with actual session, host and tool capability; check no duplicate active reference build. Verify source identities and hashes against the private register. If ambiguous, report the exact ambiguity. Preserve originals.
2. Probe and decode with existing ffmpeg/ffprobe. Record real dimensions, colour metadata, stream indices, rates and timestamps. No arbitrary upper limits on fps, sample rate, duration or dimensions.
3. Contact sheets: for monotonic presentation timestamps p[i], use targets p[0]+k*2 seconds while target <= p[last]. For each target select i_k=min{i:p[i]>=target}. Deduplicate indices, add final frame, sort. Paginate all selected frames. Verify each i_k against its target and verify final set separately. Unknown final-frame duration does not block contact sheets. Missing/unusable timestamps: disclose timing limitation, never silently assume constant fps.
4. Candidate stills: select sharp frontal/three-quarter views without captions or motion blur where available. Preserve natural identity, age and skin; record frame index, actual PTS and output hash. Document colour conversion; an SDR preview is separate from the source-derived reference.
5. Audio: native rate/channels; define sample zero on decoded presentation timeline after documented priming. Use one canonical interleaved PCM format, recorded decoder/version and channel order. Extract [s_in,s_out) within available samples. Independently read actual output count and require count == s_out-s_in. Compare output PCM to exactly the same full-decoded-source interval, not WAV/AAC container hashes. No voice cloning, source separation or enhancement.
6. Write private versioned output folder, never overwrite approved materials. Keep input paths, register IDs, media and full manifests private. Read back output bytes through available Drive method and compare hashes; distinguish remote readback from a local sync cache.
7. Deliver private file links, contact-sheet previews, sample durations, source/output checks, actual limitations and RESULT. Status BUILT, not creatively approved.

## Public-schema defect resolution
An optional public JSON summary is OUT OF SCOPE for this first private pack. Do not build or publish the disputed A1 schema from R4. This removes its status-dependent-field and arbitrary-range defects from the local build path. Public reporting can be a minimal non-sensitive completion notice. No private paths, metadata, signed links or credentials in public GitHub.

## Review handoff
Codex/ChatGPT: inspect real manifest/extraction evidence and media, separating inspection from tests.
Gemini: existing "YouTube-groeistrategie unchainednitin" project conversation, review actual selected media for identity, image quality and reference suitability. No fresh generation or new provider upload. Record actual receipt; do not claim delivery from merely writing a link.
Nitin: select preferred reference appearance; later review production service, cost ceiling and generated stills before moving to paid/video generation.
For this step use existing tools and permissions. If direct Gemini transport is unavailable, deliver pack to ChatGPT and identify authentication blocker.

## Transport
This brief is a handoff document, not an executable runner task. The current automated runner only supports READ_ONLY/BUILD_PROPOSAL/RESOLVE_READ_ONLY. Do not modify it to execute this build or pretend it dispatched to the interactive session. An actual local session must read this brief and ACK. Prior review results remain evidence, not a requirement for another abstract proposal loop.
