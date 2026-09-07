# Architecture

Local-first, stdlib-only. A **Campaign** (orchestrator.py) owns an isolated working directory and
composes small single-responsibility modules. No global state file, so campaigns run in parallel.

```
Manifest (campaign.json)  ->  Campaign
                                 |-- StateMachine (states.py)      deterministic transitions + audit
                                 |-- ApprovalStore (approvals.py)  3 SHA-bound human gates
                                 |-- ArtifactRegistry (registry.py) SHA-256 provenance
                                 |-- AuditLog (audit.py)           append-only JSONL, secret-redacted
                                 |-- mediaqc (ffprobe)             TECH_QC_REPORT.json
                                 |-- production (runner wrapper)   frozen-JSON contract, env-only secret
                                 |-- adapters                      derivatives/packaging/rights/publish/analytics/notify
                                 `-- brand + presets               reusable identity + MOTION_A/B
```

## Roles
- **Claude**: technical execution engine (timelines, render orchestration, QC, automation, reports).
  Never silently changes locked artist-facing creative decisions.
- **Gemini**: independent creative/platform intelligence (adapter). May disagree; not a mandatory
  bottleneck for every technical step.
- **ChatGPT**: central strategist/orchestrator/final synthesis. Nitin retains final authority.

## Environment separation
- Shotstack MCP/Studio/Stage = creative dev, preview, sandbox QC (watermark expected).
- Shotstack Production V1 (`/edit/v1/render`) = approved watermark-free masters. The runner has no
  stage path; accidental environment mixing is prevented by construction.

## Data-flow contract
Creative approval freezes an Edit JSON (immutable). Its SHA-256 is the contract between the creative
system and production. Production must not modify it; master mode rejects any `output.range`.

## Provenance
`source_master_sha`, `frozen_edit_sha`, `production_master_sha` are recorded. Re-encode by the
presentation renderer is expected; the system does not claim bit-identical streams unless verified.
