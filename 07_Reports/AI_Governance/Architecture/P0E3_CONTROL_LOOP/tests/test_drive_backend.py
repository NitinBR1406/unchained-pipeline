"""P0-E3 Slice-2 Google Drive backend: real client contract over CentralPersistence (in-memory fake),
plus the REAL_SHARED_DRIVE predicate that a shared volume can never satisfy."""
import hashlib
from _harness import Counter
from control_loop.drive_client import InMemoryDriveClient, GoogleApiDriveClient
from control_loop.live_backend import GoogleDriveBackend, SharedVolumeBackend
from control_loop.persistence import CentralPersistence, CONFLICT, OK
from control_loop import live_evidence as LE
c = Counter("DRV")

# --- full CAS lifecycle against the Drive-shaped API (fake client) ---
client = InMemoryDriveClient()
be = GoogleDriveBackend(client=client, drive_id="D1", namespace="ns-test")
cp = CentralPersistence(be)
cand = lambda v, h: {"state_version": v, "ledger_head_hash": h, "state_hash": "s%d" % v, "core": "x"}
r1 = cp.write(cand(1, "h1"), expected_state_version=0, expected_ledger_head_hash=None)
c.ok("drive_write_ok", r1["status"] == OK and r1["readback_verified"] is True)
c.ok("drive_object_id_captured", be.object_id("state_v1.json") is not None)
c.ok("drive_head_object_captured", be.object_id(CentralPersistence.HEAD) is not None)

# read back from the fake Drive + SHA recompute
raw = be.get_bytes("state_v1.json")
c.ok("drive_readback_sha_matches", hashlib.sha256(raw).hexdigest() == cp.read_head()["sha256"])

# stale writer rejected via CAS over the same namespace
stale = cp.write(cand(2, "h2"), expected_state_version=0, expected_ledger_head_hash=None)
c.ok("drive_stale_write_rejected", stale["status"] == CONFLICT)

# teardown trashes namespace; verify gone
be.teardown()
c.ok("drive_teardown_removes_objects", client.find(be.folder_id, "state_v1.json") is None)

# --- run_drive_lifecycle end-to-end against the fake client ---
client2 = InMemoryDriveClient()
contract = LE.run_drive_lifecycle(client2, drive_id="D2", namespace="ns2")
c.ok("lifecycle_write_observed", contract["write_observed"] is True)
c.ok("lifecycle_readback_sha_matches", contract["readback_sha_matches"] is True)
c.ok("lifecycle_cas_head", contract["cas_head_update_observed"] is True)
c.ok("lifecycle_head_readback", contract["head_readback_observed"] is True)
c.ok("lifecycle_stale_rejected", contract["stale_write_rejected"] is True)
c.ok("lifecycle_artifacts_removed", contract["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"] is False)
# fake client is stamped FAKE -> can NEVER pass the REAL Shared Drive predicate
c.ok("fake_client_not_real_shared_drive", LE.drive_persistence_observed(contract) is False)

# --- REAL predicate: only a google_shared_drive contract with the authoritative drive id passes ---
real = {"backend_type": "google_shared_drive", "drive_id": LE.AUTHORITATIVE_DRIVE_ID,
        "disposable_test_namespace": "ns", "version_object_id": "vid", "head_object_id": "hid",
        "write_observed": True, "readback_observed": True, "expected_sha256": "a", "readback_sha256": "a",
        "readback_sha_matches": True, "cas_head_update_observed": True, "head_readback_observed": True,
        "stale_write_rejected": True}
c.ok("real_contract_passes_predicate", LE.drive_persistence_observed(real) is True)

# shared volume masquerading -> FALSE
sv = dict(real); sv["backend_type"] = "shared_volume"
c.ok("shared_volume_cannot_pass", LE.drive_persistence_observed(sv) is False)
c.ok("shared_volume_describe_backend_type", SharedVolumeBackend("/tmp/x").describe()["backend_type"] == "shared_volume")

# real Google client fails closed without credentials (never fabricates auth)
gc = GoogleApiDriveClient(credentials=None, drive_id=LE.AUTHORITATIVE_DRIVE_ID)
try:
    gc.ensure_namespace(LE.AUTHORITATIVE_DRIVE_ID, "x"); c.ok("google_client_fail_closed_no_creds", False)
except RuntimeError:
    c.ok("google_client_fail_closed_no_creds", True)

c.done()
