"""Production render engine wrapper around shotstack_production_render.sh.

- Enforces the FROZEN JSON contract: refuses a payload containing output.range in master mode.
- Never handles/logs the API key: the key stays in the SHOTSTACK_PRODUCTION_API_KEY env var
  and is consumed only by the shell runner. This wrapper checks presence, not value.
- Production endpoint only (/edit/v1/render); the runner has no stage path.
"""
import os
import subprocess
from pathlib import Path
from .util import read_json, sha256_file

PRODUCTION_ENDPOINT = "https://api.shotstack.io/edit/v1/render"


class ProductionError(Exception):
    pass


def secret_available():
    return bool(os.environ.get("SHOTSTACK_PRODUCTION_API_KEY"))


def assert_master_payload(frozen_json_path):
    """Frozen JSON contract check for MASTER mode."""
    data = read_json(frozen_json_path)
    if data is None:
        raise ProductionError(f"frozen JSON not found/invalid: {frozen_json_path}")
    if "range" in data.get("output", {}):
        raise ProductionError("master payload must NOT contain output.range (would truncate master)")
    return sha256_file(frozen_json_path)


def render_master(frozen_json_path, runner_path, out_name, cwd=None, execute=True, timeout=1800):
    """Run the production runner in --master mode.

    Returns dict with attempted/executed/return_code/frozen_sha/command (key never included).
    If execute=False, returns the exact command Nitin can run locally (no execution).
    """
    frozen_sha = assert_master_payload(frozen_json_path)
    if not secret_available():
        return {"attempted": False, "executed": False, "secret_available": False,
                "frozen_sha256": frozen_sha,
                "reason": "SHOTSTACK_PRODUCTION_API_KEY not set",
                "local_command": _cmd(runner_path, frozen_json_path, out_name)}
    if not execute:
        return {"attempted": False, "executed": False, "secret_available": True,
                "frozen_sha256": frozen_sha,
                "local_command": _cmd(runner_path, frozen_json_path, out_name)}
    proc = subprocess.run(
        ["bash", str(runner_path), str(frozen_json_path), "--master", "--name", out_name],
        cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return {"attempted": True, "executed": True, "secret_available": True,
            "frozen_sha256": frozen_sha, "return_code": proc.returncode,
            "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-1000:]}


def _cmd(runner_path, frozen_json_path, out_name):
    return (f"export SHOTSTACK_PRODUCTION_API_KEY='***'  # set in your shell, never in files\n"
            f"bash {Path(runner_path).name} {Path(frozen_json_path).name} --master --name {out_name}")
