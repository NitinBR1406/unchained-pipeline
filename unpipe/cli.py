#!/usr/bin/env python3
"""Thin operational CLI. Nitin's normal flow is approve/reject; the system does the rest.

Usage:
  python3 -m unpipe.cli status   <workdir> <manifest>
  python3 -m unpipe.cli approve  <workdir> <manifest> <gate> <asset_id> <sha> [notes]
  python3 -m unpipe.cli reject   <workdir> <manifest> <gate> <asset_id> <sha> [notes]
  python3 -m unpipe.cli advance  <workdir> <manifest> [master_path] [master_sha]

gate = creative | final_video | publish
"""
import json
import sys
from .orchestrator import Campaign
from .approvals import GATE_CREATIVE, GATE_FINAL_VIDEO, GATE_FINAL_ASSET, GATE_PUBLISH, APPROVE, REJECT

GATE_MAP = {"creative": GATE_CREATIVE, "final_video": GATE_FINAL_VIDEO,
            "final_asset": GATE_FINAL_ASSET, "publish": GATE_PUBLISH}


def main(argv=None):
    a = argv or sys.argv[1:]
    if not a:
        print(__doc__); return 2
    cmd = a[0]
    if cmd == "status":
        c = Campaign(a[1], a[2])
        print(json.dumps(c._status, indent=2)); return 0
    if cmd in ("approve", "reject"):
        c = Campaign(a[1], a[2]); gate = GATE_MAP[a[3]]
        dec = APPROVE if cmd == "approve" else REJECT
        notes = a[7] if len(a) > 7 else ""
        rec = c.approve(gate, a[4], a[5], by="Nitin", decision=dec, notes=notes)
        print(json.dumps(rec, indent=2)); return 0
    if cmd == "advance":
        c = Campaign(a[1], a[2])
        mp = a[3] if len(a) > 3 else None
        ms = a[4] if len(a) > 4 else None
        st = c.advance(master_path=mp, master_sha=ms)
        print(f"state = {st.value}"); return 0
    print(f"unknown command {cmd}"); return 2


if __name__ == "__main__":
    sys.exit(main())
