# Follow-up code review — PR26, 2026-10-02
Reviewed head: ccd37b96f65816a0ac3d8e8f5e516fd602f03173.
Disposition: previous source-review blockers resolved; eligible for bounded local execution under Nitin's existing build approval and the supported local permission process. This is not runtime, media, creative or publication acceptance.

Verified:
- step2 SHA256 e4d0a70a98e07974902f0a590eb734cf0d88ba082d29b584c2cdfd9a16903669
- tests SHA256 00b89124d1cdf4dda24957d7ff6405a98790536bd616da3fbad4fbdda6582e9e
- REQUIRED_PERMISSIONS hash matches SHA256SUMS.
- Unchanged step1 was reviewed at its original hash 77c7b9bafe6ffd965872ad1c6bcfd8ecc367987f4e778148f07761813da83984.
- Independently ran test_step2_offline.py: 14 discovered, 13 passed, 1 skipped because Mac V13 exports are unavailable here.
- Caption curves, static values, wiring and original-caption inventory now have explicit checks including negative tests.
- Owned-job timeout requests stop, verifies stop state and persists HOLD; no following variant starts after HOLD. Foreign queue case deliberately does not issue a project-wide stop and records unverified stopped state.
- Expected step1 identity/mapping/settings validation added. Revised evidence distinguishes approximated beat timing from measured acceptance.

Next local steps:
1. Use the supported local permission/approval mechanism for the scoped reviewed scripts. The previously denied route is not authorized by this review alone; do not evade the tool's permission decision. Nitin's creative/private-build approval already exists and does not need to be requested again.
2. Verify exact script hashes immediately before invocation; no edits between hash check and execution. Local Write/command rules are path-based, not hash-enforced.
3. Run the offline suite on Mac, then step1 once. Inspect its actual readback. If expected source mapping/FPS/colour differs, stop and report exact mismatch rather than relax assertions.
4. Proceed to step2 only on matching readback, with no concurrent project edits. No retry on partial/unknown execution.
5. Perform step3 media QC and create/open A_PREVIEW.mp4 and B_PREVIEW.mp4. Report exact paths and real review links only after successful persistence. No rendered videos have been observed by this reviewer yet.
6. Restore temporary permissions and persist result/failure receipts.

Runtime API semantics, actual crop/legibility/lipsync and independently measured beat quality remain unproven until the local run and media inspection. Source review does not certify these. Production/publication gates remain unchanged.
