# P0-D - REAL P1 Wiring Plan V01

Goal: wire the proven Publish-Approval gate in front of REAL P1 (9627055) for posters, delivered
INACTIVE, and stop for Nitin's explicit activation. Nitin remains sole Publish Authority.

Safety invariants for the WHOLE phase:
REAL P1 not activated; N3/N4/legacy 9561890 OFF; no external publication; no Aakhri Ishq Publish
Approval; live poster store 177455 not mutated except the additive, reversible backfill in step 5
(and only with Nitin's go).

## Carry-forward (mandatory)

MUST-FIX (blocks activation): Verifier approval/grant changes - ESPECIALLY REVOCATION - must take
effect on the very next request WITHOUT a service restart.
Required regression (must pass before wiring):
  1) provision valid grant -> request -> eligible=true
  2) set revoked=true on disk (no restart) -> next request -> eligible=false
  Also: create-after-boot grant visible next request; expired remains time-correct.
Implementation: PublishApprovalService (or approval_server) reloads the stores per request (or via
mtime/file-watch cache), instead of reading once at boot. Keep fail-closed on read/parse error.

MATERIAL: REAL P1 gate must use the proven V2 Make boundary on BOTH IG and FB routes:
  HTTP parseResponse=OFF -> {{toString(data)}} -> json:ParseJSON (onerror -> block) ->
  authorize only if parsed reason == VALID_PUBLISH_APPROVAL AND raw JSON literal boolean eligible:true
  -> then the real publisher module. Any malformed / non-JSON / missing / HTTP / network condition
  fails closed (no publish). parseResponse=off returns a base64 buffer, hence toString.

## Order (as specified)

1. Fix verifier reload behavior (per-request store read / file-watch). Unit + local tests.
2. Regression prove IMMEDIATE revocation (the two-step test above) on a deployed build; capture evidence.
3. Inspect REAL P1 9627055 for drift (fetch blueprint; confirm two publish routes: IG module 10
   instagram-business:CreatePostPhoto, FB module 20 http download + 21 facebook-pages:UploadPhoto;
   confirm still inactive; compare to the P0-B rollback snapshot).
4. Create a FRESH pre-change rollback snapshot of P1; archive centrally (SHA/read-back/registry).
5. Additive poster schema + backfill (NON-destructive, Nitin-approved):
   add poster record fields content_id(=poster_id), asset_sha256, packaging_sha256, schedule_version,
   scheduled_at_epoch, *_approval_state, publish_approval_id. Backfill existing 177455 rows with
   fingerprint fields and approval_state=none and NO grants -> every existing poster BLOCKED until
   explicitly approved+provisioned (safe default). Backfill is a separate reviewed step; do not run
   during wiring.
6. Wire the verified V2 gate into REAL P1 in front of BOTH publish routes, 0 bypass, delivered while
   P1 remains INACTIVE. Per-route verifier call with platform scope; secret via keychain 217337
   (or a fresh keychain), never in blueprint.
7. Full regression on P1-as-wired (using a disposable poster grant, mock/observed boundary; do NOT
   publish): positive IG+FB, cross-platform isolation, revoke (immediate) isolation, expiry isolation,
   all mismatch/missing cases, HTTP-200-eligible-false, malformed/string-true/HTTP/network fail-closed,
   duplicate-safe. Then remove disposable authority and prove absence.
8. Archive evidence centrally (report + P1 pre/post snapshots + test evidence; SHA-256 / Drive upload /
   read-back / registry update).
9. STOP for Nitin's explicit activation/release decision. Do NOT activate P1.

## Exit criteria before activation
Verifier immediate-revocation regression GREEN; V2 gate on both routes with 0 bypass; poster
provisioning path end-to-end green on a disposable grant; backfill leaves all existing posters blocked
until approved; OPEN_MUST_FIX=0; evidence archived. Activation is a separate explicit Nitin decision.

## Open items entering P0-D
MUST-FIX: verifier per-request reload / immediate revocation (from P0-C live finding).
MATERIAL: apply V2 boundary to real P1; poster backfill defaults every existing poster to blocked.
NICE-TO-HAVE: update publish_approval.py docstring (final_video -> medium-neutral).
