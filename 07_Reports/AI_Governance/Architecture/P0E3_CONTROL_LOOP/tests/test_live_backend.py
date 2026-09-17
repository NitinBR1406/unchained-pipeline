"""P0-E3 Slice-2 live backends: shared-volume real read-back/CAS; Drive adapter fail-closed w/o creds."""
import os, tempfile
from _harness import Counter
from control_loop.live_backend import SharedVolumeBackend, GoogleDriveBackend, make_backend
from control_loop.persistence import CentralPersistence, CONFLICT, OK
c = Counter("LB")

root = tempfile.mkdtemp()
b = SharedVolumeBackend(root)
c.ok("shared_volume_describe_cross_process", b.describe()["cross_process"] is True)
c.ok("shared_volume_disposable", b.describe()["disposable"] is True)

cp = CentralPersistence(b)
cand = lambda v, h: {"state_version": v, "ledger_head_hash": h, "state_hash": "s%d" % v, "core": "x"}
r1 = cp.write(cand(1, "h1"), expected_state_version=0, expected_ledger_head_hash=None)
c.ok("shared_volume_write_readback_ok", r1["status"] == OK and r1["readback_verified"] is True)

# a second CentralPersistence over the SAME shared root sees the committed HEAD (cross-process visibility)
cp2 = CentralPersistence(SharedVolumeBackend(root))
c.ok("cross_process_head_visible", cp2.read_head()["state_version"] == 1)

# stale writer via the second handle is rejected (CAS across the shared store)
stale = cp2.write(cand(2, "h2"), expected_state_version=0, expected_ledger_head_hash=None)
c.ok("cross_process_stale_write_rejected", stale["status"] == CONFLICT)

# Drive backend refuses to run without an explicit client/folder (never fabricates persistence)
gd = GoogleDriveBackend()
for op in ("exists", "get_bytes"):
    try:
        getattr(gd, op)("x"); c.ok("drive_%s_fail_closed" % op, False)
    except RuntimeError:
        c.ok("drive_%s_fail_closed" % op, True)
try:
    gd.put_bytes("x", b"y"); c.ok("drive_put_fail_closed", False)
except RuntimeError:
    c.ok("drive_put_fail_closed", True)
c.ok("drive_describe_unprovisioned", make_backend("google_shared_drive").describe()["provisioned"] is False)
c.ok("make_backend_shared", isinstance(make_backend("shared_volume", root=root), SharedVolumeBackend))

c.done()
