"""Append-only audit log (JSONL). Never stores secrets."""
from pathlib import Path
from .util import now_iso, redact
import json


class AuditLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, campaign, previous_state, new_state, operation, actor, artifact=None,
               artifact_sha=None, result="OK", error=None, extra=None):
        entry = {
            "timestamp": now_iso(),
            "campaign": campaign,
            "previous_state": previous_state,
            "new_state": new_state,
            "operation": operation,
            "actor": actor,
            "artifact": artifact,
            "artifact_sha": artifact_sha,
            "result": result,
            "error": error,
            "extra": redact(extra) if extra else None,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]
