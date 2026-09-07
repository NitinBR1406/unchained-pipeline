"""Artifact registry: records artifacts with SHA-256 for immutable provenance."""
from pathlib import Path
from .util import sha256_file, read_json, write_json, now_iso


class ArtifactRegistry:
    def __init__(self, path):
        self.path = Path(path)
        self._data = read_json(self.path, default={}) or {}

    def register(self, artifact_id, file_path, kind, meta=None):
        p = Path(file_path)
        sha = sha256_file(p) if p.exists() else None
        rec = {
            "artifact_id": artifact_id,
            "path": str(file_path),
            "kind": kind,
            "sha256": sha,
            "exists": p.exists(),
            "size": p.stat().st_size if p.exists() else None,
            "registered_at": now_iso(),
            "meta": meta or {},
        }
        self._data[artifact_id] = rec
        write_json(self.path, self._data)
        return rec

    def get(self, artifact_id):
        return self._data.get(artifact_id)

    def sha(self, artifact_id):
        r = self._data.get(artifact_id)
        return r["sha256"] if r else None

    def all(self):
        return dict(self._data)
