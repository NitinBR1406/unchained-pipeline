# Exact operation supplement V01

`compile_operations(base_plan, spec)` accepts strict versioned operation details
bound to the canonical JSON SHA256 of an already validated base plan. Callers
must validate that base with `resolve.plan.verify` first. Supplemental details
are explicit proposed instructions, not a silent expansion of canonical effects.

The input schema is `RESOLVE_OPERATION_DETAILS`, version 1. Every operation has
an ID, package ID, kind, half-open integer output-frame interval, explicitly false
`performer_obscured`, typed parameters and an evidence reference. No fractional
frames, float geometry, inferred random shake, script or code expression exists.

- Cuts specify sorted unique cut frames; they do not retime the timeline.
- Reframe specifies crop edges in integer millionths of output dimensions.
- Zoom/push-in/shake specify exact scale and normalized center keyframes with
  LINEAR/HOLD interpolation. Push-in scale must increase. Shake is an explicit
  deterministic transform trajectory requiring later visual suitability QC.
- Captions/text specify exact text, position and hash-bound style reference.
- Transitions specify DISSOLVE/WIPE, duration and explicit source-handle lengths.
- Effects specify plugin identity and template hash. License UNKNOWN or a reported
  VERIFIED_AVAILABLE cannot enable execution without independently checked proof.

Reference hashes are typed bindings only in this stage, not fetched bytes or
verified licenses. The resulting supplement remains execution-blocked pending
installation and operation-specific capability smoke. Cropping, titles and
transitions require actual unobscured-performer and safe-area QC; false visibility
declarations are not treated as authenticated evidence. Source handles must be
checked against real decoded media before execution. Audio/color baseline
changes, unknown operations/fields and authority escalation fail closed.
