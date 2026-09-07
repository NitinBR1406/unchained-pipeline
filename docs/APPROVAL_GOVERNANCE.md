# Approval Governance

Exactly **three** mandatory human gates, kept strictly separate. No technical success (render OK,
QC pass, Gemini/Claude/Work approval, derivatives existing) may imply any of them.

| Gate | Constant | Approves | Unlocks |
|---|---|---|---|
| 1 | NITIN_CREATIVE_APPROVAL | preview/frozen edit | production authorization |
| 2 | NITIN_FINAL_VIDEO_APPROVAL | production master | derivatives + packaging |
| 3 | NITIN_PUBLISH_APPROVAL | release package | publishing (with rights pass) |

CREATIVE ≠ FINAL VIDEO ≠ PUBLISH.

## SHA binding
Every approval stores the approved artifact's SHA-256. `is_approved(gate, current_sha)` returns true
only when the latest decision is APPROVE **and** it was made against `current_sha`. If the artifact
changes, the old approval is automatically invalid for the new artifact. (Tested.)

## Never inferred from chat
Approvals are explicit records (`approve`/`reject`) with approver, timestamp, SHA, notes, version.
Chat sentiment never creates an approval.

## Publish preconditions (all required)
FINAL_VIDEO_APPROVED + DERIVATIVES_READY + PACKAGING_READY + RIGHTS_PASS + NITIN_PUBLISH_APPROVAL.
Missing any one → publish blocked (PermissionError / HOLD). Per-platform results tracked separately;
one platform failing never marks others successful.
