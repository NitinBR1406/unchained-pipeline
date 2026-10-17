"""Shared helpers: hashing, time, secret redaction, safe JSON IO."""
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
import re
from datetime import datetime, timezone
from pathlib import Path

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password)")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text())


def write_json(path, obj):
    """Atomic: write a temp file in the same directory, fsync, then os.replace (readers never see half a file)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(".%s.%d.tmp" % (p.name, os.getpid()))
    with open(tmp, "w") as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return str(p)


@contextmanager
def locked(path):
    """Exclusive inter-thread/inter-process lock for a read-modify-write of `path` (lock file next to it).
    All writers of the grant store use this, so a revoke can never be lost by a concurrent update."""
    lp = Path(str(path) + ".lock")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def redact(obj):
    """Recursively blank any value whose key looks like a secret. Never persist secrets."""
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if _SECRET_RE.search(str(k)) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj
