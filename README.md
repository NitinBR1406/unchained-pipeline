# Unchained Nitin — Autonomous Media Pipeline V1

Local-first, dependency-free (Python stdlib) orchestration for the Unchained Nitin cover/original
factory. Core principle: **Nitin approves, the system executes.** Three separate human gates;
nothing publishes without explicit publish approval.

```
unchained_pipeline/
  unpipe/            # the package
    states.py        # State enum + deterministic transition table
    orchestrator.py  # Campaign: ties everything together (advance/transition/gates)
    approvals.py     # 3-gate approval store, SHA-bound (hash change invalidates approval)
    registry.py      # artifact registry + SHA-256 provenance
    mediaqc.py       # ffprobe technical QC -> TECH_QC_REPORT.json
    production.py     # wraps shotstack_production_render.sh; frozen-JSON contract; env-only secret
    adapters.py      # derivatives / packaging / rights / publish / analytics / notifications
    brand.py         # brand profile + presentation presets (MOTION_A locked, MOTION_B optional)
    manifest.py      # campaign manifest load/validate
    audit.py         # append-only JSONL audit log (no secrets)
    util.py          # hashing, time, secret redaction, JSON IO
    cli.py           # thin operational CLI (status / approve / reject / advance)
  campaigns/<id>/campaign.json   # per-campaign config (isolated state dir under state/)
  tests/test_pipeline.py         # 13 governance/QC/idempotency tests (all pass)
  run_aki_acceptance.py          # Aakhri Ishq acceptance test (reconstruct, no publish)
  docs/                          # ARCHITECTURE, STATE_MACHINE, GOVERNANCE, SECURITY, etc.
```

## Run
```
python3 -m unittest tests.test_pipeline          # test suite
python3 run_aki_acceptance.py                     # AKI acceptance (no publish)
python3 -m unpipe.cli status  <workdir> <manifest>
python3 -m unpipe.cli approve <workdir> <manifest> creative|final_video|publish <asset_id> <sha> [notes]
python3 -m unpipe.cli advance <workdir> <manifest> [master_path] [master_sha]
```

## Secret
`SHOTSTACK_PRODUCTION_API_KEY` is read only from the environment by the shell runner. It is never
hardcoded, printed, logged, committed, put in JSON/manifests/reports, or sent to any model.

## Status
See `CAPABILITY_MATRIX.md` for the honest per-capability classification and remaining automation debt.
Aakhri Ishq: VIDEO_APPROVED = TRUE, PUBLISH_APPROVED = FALSE. Nothing is published.
