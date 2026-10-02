# R4 recovery review — 2026-10-02

Reviewed head b25a50942f4a8364ee0a848ec0000be875915274.
Disposition: observed caption serialization mismatch addressed; eligible for one bounded R4 step2 execution through supported local permissions and existing private-build authorization. Do not repeat step1 or rerun earlier revisions.

Verified script SHA256 a3ab4952b676e0650a5fde32e54d1ad86bd96d8f29c8b90494416e7b6fbe26b0; tests 2a91199ef8af5fb6a3ab17d70eabbe362d8ad416dc9214fb1568b140ff8e9882. All four supplied fixture hashes match manifest.
Independently ran 21 tests: 20 passed, 1 skipped because Mac-local exports are unavailable. This includes the actual builder-supplied clip1 post-import export and negative checks.

R4 uses Fusion's observed spline naming convention, retains keyframe and wiring comparisons, and handles omitted TextPlus Size as the observed 0.08 default. This default remains specific to the observed runtime; actual rendered text must still be inspected. New R4 timelines/output paths preserve failed attempts. Previous render timeout/HOLD behavior remains intact.

Nonblocking metadata defect: main receipt still has numeric revision=3 although REV and paths are R4. For this exact reviewed script, identify the actual run by full script hash and R4 paths, and disclose the stale numeric label in the accompanying evidence. Do not change reviewed bytes ad hoc before execution.

Next: exact-hash check, expected recovery-state check (base plus A_V01 and A_R3; no render jobs), supported local permission for the reviewed command, and one step2 R4 attempt. Then step3 full decode, 360 frames/12 seconds/30fps, audio comparison, actual caption/crop/lipsync checks and opening both MP4 previews. Restore temporary rights and persist results. No additional design review is requested.

No preview has been independently observed here. Runtime/render success and media quality are not proved by the offline tests. Production/publication remain unauthorized.
