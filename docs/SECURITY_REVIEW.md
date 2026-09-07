# Security Review

Scope: local-first V1 orchestration package + Shotstack production runner.

## Secret handling — PASS
- Production key is read ONLY from `SHOTSTACK_PRODUCTION_API_KEY` (environment variable).
- Never hardcoded, printed, logged, returned, committed, stored in campaign manifest, Edit JSON, or
  reports, and never sent to any model.
- In the shell runner the key is passed to curl via a `chmod 600` temp config (deleted on exit), so
  it never appears in process arguments (`ps`).
- Missing secret → safe stop (`PRODUCTION_SECRET_AVAILABLE = NO`), no crash, no fallback.
- `util.redact()` blanks any secret-looking key before anything is written to audit/extra fields.

## Automated scan — PASS
`grep` for the shared key literal and for `api_key = "..."` patterns across `unpipe/`, `tests/`,
scripts: no embedded secrets found. Key referenced only as the env-var name and in docs.

## Temp files
Runner uses `mktemp` for the curl config and payload; both removed via `trap cleanup EXIT`. Curl
config is `chmod 600`.

## Audit log
Append-only JSONL; `extra` fields pass through `redact()`. No secret values recorded.

## Known limitations / recommendations
- Rotate the production key that was shared in chat earlier; store the new one only via the env var.
- For hosted execution, move the secret into a managed secret store (e.g. cloud secret manager) and
  keep the same env-var contract.
- Adapters for external platforms are not connected; when connected, apply least-privilege tokens
  and the same redaction/no-log rules.
