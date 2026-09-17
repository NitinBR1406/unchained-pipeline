# P0-E4 Slice 1 — production intake preparation

Verdict: **BLOCKED, NOT GREEN**. This additive slice imports the real repository campaign into the
frozen P0-E3 DurableControlLoop, records a hash-bound TASK_REQUEST, runs read-only intake and independent
engineering work, and verifies event-ledger replay against local persisted state. It does not claim a
live Temporal run or Shared Drive state persistence. V05/state_version 10 remains authoritative.

## Frozen sources and boundaries

Base: `263a36980fc2e2aa3138609f5406555ead9ef8d7`. P0-E0..E3, campaign approvals, Make blueprint,
Render configuration, and poster eligibility remain unchanged. P0-E3 final and hermetic manifests:
16/16 entries verified. Existing run 35258089586 is successful; its workflow registration SHA is
594ccf2b8b0ac3aaa93210dff614492bbe865dd3 and accepted feature SHA is
fe3bb58c3ddbd8bc02d968c00f7f03d51d3d8936. No run dispatched.

Inspected: P0-E1 event/reducer/human-auth contracts, P0-E2 live runner contracts, P0-E3 loop,
backlog schema, persistence/readback/CAS and Drive client; `unpipe/adapters.py`, `production.py`,
`publish_approval.py`, `make/V3_SECURE_blueprint.json`, `render.yaml`, campaign state/approvals/registry.
Make visualizer approval only advances VISUALIZER_APPROVED. Render hosts the approval surface; it
is not a media-render authorization. Poster eligibility requires separate final-asset and publish
gates and a scoped grant. Slice 1 has **no callable production/publish transport**. Unknown executor
tasks raise PermissionError. Existing signed-gate semantics are reused unchanged.

## Real workload gaps

* Final-video APPROVE is recorded, but its SHA is `AKI_PRODUCTION_MASTER_V01_SHA_PENDING_LOCAL_RENDER`.
  Respect the approval; do not invent a cryptographic binding or replace it with a new approval.
* The production master is absent from the repository registry. Drive folder listing locates
  `AKI_SHOTSTACK_PRESENTATION_MASTER_V01.mp4`, file `1ifHVAW1E0NjhN-eguBWUMNRekoemweAn`,
  168512442 bytes, Shared Drive `0AG0CqqUZ6YuXUk9PVA`. Raw connector retrieval succeeded;
  byte SHA/QC and binding to the approved asset are not yet verified. See `evidence/drive_discovery.json`.
* Rights are RIGHTS_HOLD. Packages have missing copy and ADAPTER_READY status; derivatives are plans.
* An E4-specific live executor and durable Drive persistence are not provisioned by this implementation.
  Frozen P0-E3 live evidence cannot prove these E4 integrations.

Consequently AKI_RELEASE is BLOCKED, **not** fraudulently advanced to WAITING_FOR_NITIN or publish-ready.
The future human gate remains NITIN_PUBLISH_APPROVAL. A TEST_ONLY workload proves that the existing gate
parks and releases unrelated work; that test is never evidence of real AKI readiness.

## Reproduction

Python 3 with cryptography and PyYAML for the existing regression suites:

```
PYTHONDONTWRITEBYTECODE=1 python3 p0e4/tests/test_handoff.py
PYTHONDONTWRITEBYTECODE=1 python3 p0e4/handoff.py --workdir /tmp/p0e4-isolated-run
```

Use a fresh directory for changed inputs. Restarts with identical inputs are idempotent. Immutable,
atomic evidence installation protects the executor/store crash window. No production mutation,
asset edit, render, deployment, approval creation, or publication is performed.

## Acceptance mapping

1. Real typed intake: repository campaign/state provenance hash-bound in TASK_REQUEST; no live backlog claim.
2. Existing durable loop/reducer/lease/dedup semantics: offline verified; real E4 Temporal execution pending.
3. Boundaries fail closed: verified; no production transports exposed.
4. Recorded approvals read, no publish approval created: verified; asset SHA binding unresolved.
5. Publish-ready handoff: BLOCKED by asset binding, rights, derivatives and packaging.
6. Real AKI WAITING_FOR_NITIN: NOT REACHED; synthetic nonblocking gate tested separately.
7–9. No publication path; poster remains paused; authorization flags remain strict false.
10. Local replay/reproducibility verified; authoritative E4 Shared Drive state persistence pending.
11. Local evidence retry/crash idempotency verified; external exactly-once is unproven.
12. Independent READY work completes while real release is blocked; synthetic human wait also nonblocking.

## Smallest next action

Reconcile the identified Drive master and its byte SHA/QC with the existing final-video approval through
an authoritative asset binding record. If no existing record establishes identity, that binding requires
Nitin's confirmation; do not silently reinterpret the placeholder. Resolve the recorded rights hold and
complete per-platform assets/metadata before requesting publish approval. Then wire an E4-specific
SHA-pinned disposable Temporal + Drive acceptance using existing backend contracts. Keep deployment and
publication false, First Real Poster paused. Do not use Nitin as an AI-to-AI relay.
