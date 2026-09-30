#!/usr/bin/env python3
"""PreToolUse gate for mcp__davinci_resolve__run_script (UNCHAINED NITIN, V01).

Fail-closed: run_script is allowed only when the submitted script is byte-identical
(after trailing-whitespace normalisation) to the pinned read-only probe below.
Every other script, malformed input or hook error is denied. Decisions are logged
locally without script bodies of denied calls beyond their hash.
"""
import datetime
import hashlib
import json
import os
import sys

TOOL = "mcp__davinci_resolve__run_script"
PINNED = {
    # .claude/resolve/readonly_identity_probe_v01.py
    "22cf949c0bd2b1fa657c542b5a9f3de057a39f444ceca85b3a970f6243ed4bf2": "readonly_identity_probe_v01",
}


def decide(event):
    if event.get("tool_name") != TOOL:
        return None, None, None
    script = (event.get("tool_input") or {}).get("script")
    if not isinstance(script, str):
        return "deny", "run_script without string script is blocked", None
    digest = hashlib.sha256((script.rstrip() + "\n").encode("utf-8")).hexdigest()
    probe = PINNED.get(digest)
    if probe:
        return "allow", f"pinned read-only probe {probe} sha256={digest}", digest
    return "deny", f"run_script blocked: sha256={digest} is not a pinned read-only probe", digest


def log(event, decision, reason, digest):
    try:
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        path = os.path.join(root, ".local", "claude_resolve_gate", "decisions.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "session_id": event.get("session_id"),
                "tool_name": event.get("tool_name"),
                "decision": decision,
                "script_sha256": digest,
                "reason": reason,
            }) + "\n")
    except Exception:
        pass


def main():
    try:
        event = json.load(sys.stdin)
        decision, reason, digest = decide(event)
    except Exception as exc:  # fail closed
        event, decision, reason, digest = {}, "deny", f"gate error: {type(exc).__name__}", None
    if decision is None:
        return 0
    log(event, decision, reason, digest)
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
