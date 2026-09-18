# P0-E4 integration contracts v1

Executable specification: `contracts.validate` and `validate_chain`. All wire objects
use exact field sets and schema_version integer 1; extra fields, string booleans,
unknown versions, placeholder SHA256 and non-UTC timestamps fail closed.
`fixtures.chain()` produces the three complete machine-readable TEST_ONLY examples.

Every package: schema (CREATIVE_INTELLIGENCE_PACKAGE / PRODUCTION_RELEASE_PACKAGE /
INDEPENDENT_QC_PACKAGE), schema_version, content_id, package_id, created_at,
producer {agent, model, run_id}, inputs [{role, uri, sha256}], evidence_refs
[{uri, sha256}], payload. Unknown model is null, never an invented model identity.

- Creative payload: edit_plan with output duration in integer milliseconds, full
  contiguous segments, SHA-bound sources and source intervals, performer visibility,
  bounded effects, baseline_locked and RECOMMENDATION_ONLY mode. At least 4/5 of
  output duration must show the performer. Overlap never counts twice. No retiming
  or obscuring effects. This is a structural recommendation check; independent
  rendered-output QC must verify actual visibility and effects.
- Production payload: creative_package_sha256, edit_plan_sha256, outputs, platforms.
  Each platform row binds title/caption and exact output SHA. Chain validation reads
  input/output/evidence bytes and verifies all hashes, content identity and time order.
- QC payload: production_package_sha256, checked_assets, verdict, checks. PASS needs
  technical, look_match, full_motion, lipsync, audio, platform_safe_area and
  performance_rule PASS, every output checked, separate producer agent/run and
  trusted transport receipts. A self-declared Gemini name is not authentication.

Trust boundaries: resolver supplies bytes from an approved store; authenticated_receipts
comes from authenticated integration transport, not user/package JSON. The final
review verifier must consult the existing authoritative human approval path for
creative/final asset/final video/release review on this exact package hash. There is
no default accepting verifier. Production wiring of these capabilities is blocked.
The isolated positive tests inject TEST_ONLY doubles, never real approvals.

RightsRouter validates exact content/asset, platform, account, territory, use,
monetization, validity term, revocation, complete rights review and SHA-bound
source evidence. Reviewer public keys are externally provisioned; empty trust is
HOLD. It does not generate keys or invent legal clearance. Every request rereads
the store; any bad record blocks the whole snapshot. Trusted callers supply evaluation
time (UTC); it must be current at the release boundary, not copied from a prior run.
No cross-grant scope union. Re-evaluate before any future publish boundary.

Existing system: wrapper calls unpipe.adapters.PackagingEngine.build and returns
PREPARED_NOT_DISPATCHED with deterministic timestamps and idempotency keys. It does
not recreate Claude/Make or call any publish/production endpoint. Existing execution
entrypoint is unpipe.executor.run_production_job, gated separately. Resolve/FFmpeg/
Shotstack execution adapters for the new recommendations remain external capability
work; no support is claimed simply because a contract names an effect.

Golden scope: read-only hash-verified RAW/audio intake, package lineage, existing
packaging wrapper, rights routing, isolated frozen P0-E3 scheduling/replay and hard
stop at WAITING_FOR_NITIN_PUBLISH_APPROVAL. Test bytes are not playable media and
cannot establish real RAW-to-render E2E acceptance. No production activation occurs.
