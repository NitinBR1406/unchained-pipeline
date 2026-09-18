# P0-E4 — production integration and release orchestration

**Engineering integration verified; actual release BLOCKED, not GREEN.**

Current evidence: `evidence/resume/ACCEPTANCE_RESUME.json`.
Versioned project snapshot: `evidence/resume/state/UNCHAINED_MASTER_PROJECT_STATE_V06.json`,
state_version **11**, composed deterministically from frozen V05/version 10 and one hash-chained
engineering evidence event. Human authorizations are copied unchanged; no approval is added.

## Completed

* Authoritative GitHub branch inspected before continuing: P0-E3 freeze remains
  `263a36980fc2e2aa3138609f5406555ead9ef8d7`. P0-E0..E3 and original campaign files unchanged.
* Real Shared Drive presentation master and three existing derivatives downloaded to temporary cache,
  SHA256 fingerprinted, and fully decoded (both audio and video) without modifying a byte. All four pass.
* Seven platform metadata drafts produced, plus explicit asset proposals in `RELEASE_REVIEW_PACKET.json`.
  These are review artifacts, not approval records or proof of platform/rights clearance.
* Existing P0-E3 DurableControlLoop schedules real typed campaign tasks; existing frozen P0-E1
  ControlPlaneTask executes via a narrow E4 evidence activity. No parallel control-plane implementation.
* GitHub Actions run **35325952509**, exact implementation SHA
  **41230edcaac11218ec7576530ce79065522a42f2**, succeeds using the existing keyless WIF variables.
  Four engineering workflows complete against real disposable Temporal and real Shared Drive state
  persistence. Readback/replay, stale-write rejection, duplicate dispatch without an extra activity,
  independent progress during a TEST_ONLY human wait, and cleanup are observed.
* Full regression: **37/37 executable suites PASS**, including fourteen new E4 unittest cases.
  Artifact ZIP SHA matches GitHub's digest
  `ed4e7de1bf83e7c27bd5fc4f5806dd38aa5ca7dfa73af3909c4958e24f231aba`.

The earlier local-only report and evidence remain in place for traceability. They do not describe the
current integration capabilities. `local_temporal_4ff37a2/` is the precursor local smoke, not another
GitHub authoritative acceptance. No old authoritative P0-E3 run was re-dispatched.

## Genuine release gates remaining

1. **Approval binding:** the existing final-video APPROVE refers to
   `AKI_PRODUCTION_MASTER_V01_SHA_PENDING_LOCAL_RENDER`. The actual Drive master is
   `1ifHVAW1E0NjhN-eguBWUMNRekoemweAn`, SHA256
   `0c6fdfc23439d195a2ff4aa4d809fd4621912d0023db5003bc7a6d972d0117b1`.
   A new hash observation cannot silently rewrite Nitin's approval. The binding request contains the
   existing decision and exact candidate identity; Nitin or an existing authoritative binding must resolve it.
2. **Rights:** campaign remains RIGHTS_HOLD; composition publisher, backing master origin and Content ID
   expectation remain UNKNOWN. No clearance is invented. This is a rights-evidence gate, not an API problem.
3. **Release review:** seven copy/asset proposals are complete. Technical derivative QC does not establish
   their approved lineage or final creative release scope. The proposal is available for a concrete review,
   without asking Nitin to execute commands or relay messages between agents.

The real release is BLOCKED. PUBLISH_READY and WAITING_FOR_NITIN at NITIN_PUBLISH_APPROVAL are not claimed.
After the prerequisite gates resolve, the next gate is NITIN_PUBLISH_APPROVAL, then STOP before publication.
Both deployment/publication authorization flags remain false; FIRST_REAL_POSTER remains PAUSED_BY_NITIN.

## Acceptance and evidence limits

| Requirement | Current result |
|---|---|
| Real typed AKI workload from repository/state | Verified; hash-bound TASK_REQUEST and real workflow IDs |
| Existing durable control-plane semantics | Verified on disposable Temporal with frozen workflow/loop |
| Explicit fail-closed boundaries | Unknown task/input rejected; no production/publish transport |
| Read approvals without inventing publish approval | Verified; placeholder explicitly remains unresolved |
| Publish-ready handoff | Blocked; seven review proposals prepared |
| Actual AKI waiting at publish approval | Not reached; TEST_ONLY wait tested separately |
| No publication; poster paused; flags false | Verified within executed engineering scope |
| Reproducible persisted evidence/state | GitHub + versioned snapshot; live disposable Drive lifecycle verified |
| Failures/retries without duplicates | Offline crash-window tests and live duplicate-dispatch test pass |
| Independent READY work not blocked | Four complete; no READY work left in scoped backlog |

This is not production deployment, multiwriter production certification, full audiovisual creative QC,
or new approval of any derivative. Decode checks do not replace creative review. The disposable Drive
namespace is removed; retained production evidence is archived separately. Platform proposals were prepared
after the live run and are not represented as the exact input package exercised by that run.

## Reproduction and persistence

Install isolated Python dependencies: temporalio==1.33.0, cryptography, PyYAML,
imageio-ffmpeg (media checks), google-api-python-client and google-auth (Drive test).

```
python p0e4/tests/test_handoff.py
python p0e4/tests/test_release.py
python p0e4/tests/test_state_update.py
python p0e4/media_verify.py --manifest p0e4/evidence/resume/asset_sources.json --cache CACHE --out MEDIA_QC.json
python p0e4/temporal_integration.py --media MEDIA_QC.json --out NEW_ISOLATED_DIRECTORY
```

Optional `--drive-namespace P0E4_DISPOSABLE_UNIQUE_RUN` uses the existing P0-E3 Drive backend with ADC;
CI obtains ADC via keyless WIF, never a pasted key. The new workflow runs only for E4 code/test/workflow
changes on the dedicated E4 branch and checks out the exact triggering SHA. Evidence-only commits do not
start another run. Do not rerun authoritative acceptance just to reproduce an already accepted result.

`state_update.project()` replays the append-only engineering ledger with the frozen reducer and composes
V06 with its hash-bound V05 parent. This additive project snapshot projection does not replace the runtime
reducer. Repeated identical updates are idempotent; changed evidence requires a subsequent version.
