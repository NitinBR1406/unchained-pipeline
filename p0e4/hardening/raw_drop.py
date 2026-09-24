"""Crash-recoverable synthetic RAW-drop intake with append-only hash chaining.

This module has no cloud watcher, production adapter, or Aakhri-specific callable.
Callers supply already observed disposable bytes and an explicit synthetic scope.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


class SyntheticRawDropIntake:
    """Durable local projection over a synthetic event ledger.

    The ledger is authoritative for the disposable run. State is always replayed,
    so a crash between an event append and response delivery cannot duplicate intake.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "SYNTHETIC_RAW_DROP_LEDGER.jsonl"

    def _events(self):
        if not self.ledger_path.exists():
            return []
        events = [json.loads(x) for x in self.ledger_path.read_text().splitlines() if x]
        previous = "0" * 64
        for sequence, event in enumerate(events, 1):
            require(event["sequence"] == sequence, "ledger sequence")
            require(event["previous_hash"] == previous, "ledger chain")
            body = {k: v for k, v in event.items() if k != "event_hash"}
            require(event["event_hash"] == digest(body), "ledger event hash")
            previous = event["event_hash"]
        return events

    def _append(self, event_type, payload):
        events = self._events()
        body = {
            "schema": "SYNTHETIC_RAW_DROP_EVENT_V01",
            "sequence": len(events) + 1,
            "previous_hash": events[-1]["event_hash"] if events else "0" * 64,
            "event_type": event_type,
            "payload": payload,
        }
        body["event_hash"] = digest(body)
        with self.ledger_path.open("a") as stream:
            stream.write(json.dumps(body, sort_keys=True) + "\n")
            stream.flush()
        return body

    def replay(self):
        accepted_by_hash = {}
        path_bindings = {}
        aliases = {}
        holds = []
        for event in self._events():
            payload = event["payload"]
            if event["event_type"] == "RAW_ACCEPTED":
                accepted_by_hash[payload["sha256"]] = payload
                path_bindings[payload["drop_key"]] = payload["sha256"]
            elif event["event_type"] == "DUPLICATE_SUPPRESSED":
                aliases[payload["drop_key"]] = payload
            elif event["event_type"] == "SOURCE_DRIFT_HELD":
                holds.append(payload)
        return {
            "schema": "SYNTHETIC_RAW_DROP_STATE_V01",
            "accepted_by_hash": accepted_by_hash,
            "path_bindings": path_bindings,
            "aliases": aliases,
            "holds": holds,
            "event_count": len(self._events()),
            "ledger_head_hash": self._events()[-1]["event_hash"] if self._events() else "0" * 64,
        }

    def observe(self, observation, content):
        expected = {"schema", "scope", "drop_key", "basename", "bytes", "sha256", "stable_reads", "source_mutations"}
        require(set(observation) == expected, "observation fields")
        require(observation["schema"] == "SYNTHETIC_RAW_DROP_OBSERVATION_V01", "observation schema")
        require(observation["scope"] == "SYNTHETIC_DISPOSABLE_ONLY", "real RAW drop forbidden")
        require(type(content) is bytes and content, "content bytes")
        require(observation["bytes"] == len(content), "byte count")
        require(observation["sha256"] == digest(content), "content hash")
        require(observation["stable_reads"] >= 2, "file not stable")
        require(observation["source_mutations"] == 0, "source mutation")
        require(observation["basename"].lower().endswith((".mov", ".mp4", ".mxf")), "unsupported RAW extension")
        state = self.replay()
        alias = state["aliases"].get(observation["drop_key"])
        prior_path_hash = state["path_bindings"].get(observation["drop_key"]) or (alias and alias["sha256"])
        if prior_path_hash and prior_path_hash != observation["sha256"]:
            payload = {"drop_key": observation["drop_key"], "previous_sha256": prior_path_hash,
                       "observed_sha256": observation["sha256"], "status": "HOLD_SOURCE_DRIFT"}
            self._append("SOURCE_DRIFT_HELD", payload)
            return payload
        existing = state["accepted_by_hash"].get(observation["sha256"])
        if existing:
            payload = {"drop_key": observation["drop_key"], "sha256": observation["sha256"],
                       "existing_intake_id": existing["intake_id"], "status": "DUPLICATE_SUPPRESSED"}
            if observation["drop_key"] not in state["aliases"]:
                self._append("DUPLICATE_SUPPRESSED", payload)
            return payload
        intake_id = "sri_" + digest({"drop_key": observation["drop_key"], "sha256": observation["sha256"]})[:24]
        payload = {"intake_id": intake_id, "drop_key": observation["drop_key"],
                   "basename": observation["basename"], "bytes": observation["bytes"],
                   "sha256": observation["sha256"], "status": "SYNTHETIC_RAW_ACCEPTED"}
        self._append("RAW_ACCEPTED", payload)
        return payload


class SyntheticDirectoryWatcher:
    """Two-poll file-stability watcher restricted by an explicit disposable marker."""

    def __init__(self, drop_root, state_root):
        self.drop_root = Path(drop_root).resolve()
        self.state_root = Path(state_root).resolve()
        require((self.drop_root / ".synthetic_disposable_scope").is_file(), "synthetic scope marker required")
        self.intake = SyntheticRawDropIntake(self.state_root)
        self.snapshot_path = self.state_root / "WATCHER_STABILITY_STATE.json"

    def _state(self):
        if not self.snapshot_path.exists():
            return {}
        value = json.loads(self.snapshot_path.read_text())
        require(type(value) is dict, "watcher state")
        return value

    def poll(self):
        previous = self._state()
        current = {}
        results = []
        for path in sorted(self.drop_root.iterdir()):
            if not path.is_file() or path.name.startswith(".") or not path.name.lower().endswith((".mov", ".mp4", ".mxf")):
                continue
            content = path.read_bytes()
            identity = {"bytes": len(content), "sha256": digest(content)}
            prior = previous.get(path.name)
            stable_reads = prior.get("stable_reads", 0) + 1 if prior and prior["sha256"] == identity["sha256"] and prior["bytes"] == identity["bytes"] else 1
            current[path.name] = dict(identity, stable_reads=stable_reads)
            if stable_reads < 2:
                results.append({"drop_key": path.name, "status": "PENDING_STABILITY"})
                continue
            observation = {"schema": "SYNTHETIC_RAW_DROP_OBSERVATION_V01", "scope": "SYNTHETIC_DISPOSABLE_ONLY",
                           "drop_key": path.name, "basename": path.name, "bytes": identity["bytes"],
                           "sha256": identity["sha256"], "stable_reads": stable_reads, "source_mutations": 0}
            results.append(self.intake.observe(observation, content))
        self.snapshot_path.write_text(json.dumps(current, sort_keys=True) + "\n")
        return results
