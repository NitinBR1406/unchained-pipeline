"""Persistent approval records for the THREE mandatory human gates.

Gates (must stay separate; no technical success implies any of them):
  GATE 1  NITIN_CREATIVE_APPROVAL     -> approves a preview/edit artifact
  GATE 2  NITIN_FINAL_VIDEO_APPROVAL  -> approves the production master
  GATE 3  NITIN_PUBLISH_APPROVAL      -> authorizes publication

An approval is bound to the approved artifact's SHA-256. If the artifact changes
(SHA differs), the prior approval is INVALID for the changed artifact.
"""
from pathlib import Path
from .util import read_json, write_json, now_iso

GATE_CREATIVE = "NITIN_CREATIVE_APPROVAL"
GATE_FINAL_VIDEO = "NITIN_FINAL_VIDEO_APPROVAL"
GATE_PUBLISH = "NITIN_PUBLISH_APPROVAL"
GATES = (GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_PUBLISH)

APPROVE = "APPROVE"
REJECT = "REJECT"


class ApprovalStore:
    def __init__(self, path):
        self.path = Path(path)
        self._data = read_json(self.path, default={"approvals": []}) or {"approvals": []}

    def record(self, campaign_id, asset_id, gate, decision, approved_by, artifact_sha256,
               notes="", version="1"):
        assert gate in GATES, f"unknown gate {gate}"
        assert decision in (APPROVE, REJECT), f"bad decision {decision}"
        rec = {
            "campaign_id": campaign_id,
            "asset_id": asset_id,
            "gate": gate,
            "decision": decision,
            "approved_by": approved_by,
            "timestamp": now_iso(),
            "artifact_sha256": artifact_sha256,
            "notes": notes,
            "version": version,
        }
        self._data["approvals"].append(rec)
        write_json(self.path, self._data)
        return rec

    def latest(self, campaign_id, gate):
        recs = [a for a in self._data["approvals"]
                if a["campaign_id"] == campaign_id and a["gate"] == gate]
        return recs[-1] if recs else None

    def is_approved(self, campaign_id, gate, current_sha):
        """True only if the latest decision is APPROVE AND it was made against current_sha."""
        rec = self.latest(campaign_id, gate)
        if not rec or rec["decision"] != APPROVE:
            return False
        if current_sha is None or rec["artifact_sha256"] is None:
            return False
        return rec["artifact_sha256"] == current_sha

    def all(self, campaign_id=None):
        if campaign_id is None:
            return list(self._data["approvals"])
        return [a for a in self._data["approvals"] if a["campaign_id"] == campaign_id]
