"""P0-E3 Slice-2 central-persistence backends for LIVE acceptance.

The frozen `persistence.CentralPersistence` protocol (write -> read-back -> SHA256 verify -> CAS HEAD)
is backend-agnostic: a backend only implements put_bytes / get_bytes / exists. This module provides the
live backends without changing that protocol:

  * SharedVolumeBackend  — a genuinely cross-process store on a shared disposable volume. In the live CI
    run this volume is mounted into the disposable Temporal worker containers, so concurrent live writers
    (worker1/worker2) contend for the SAME central HEAD through the real filesystem — a real, observable
    central persistence backend (not a mock), disposable, and torn down after the run.

  * GoogleDriveBackend   — a skeleton that maps the identical three operations onto a Google Shared Drive.
    It is intentionally NOT wired to credentials here and raises if used without an explicit, caller-
    supplied client. This avoids fabricating live Drive persistence: the byte-identical write->read-back
    ->SHA256 contract was already proven live against the Shared Drive at the P0-E2 final freeze, and this
    adapter is the drop-in that reuses it. No secrets, no keys, no production Drive mutation.
"""
import os
from .persistence import LocalDirBackend, Backend


class SharedVolumeBackend(LocalDirBackend):
    """Cross-process central store on a shared disposable volume (real read-back, real CAS contention)."""
    KIND = "shared_volume"

    def describe(self):
        return {"kind": self.KIND, "backend_type": self.KIND, "root": self.root,
                "cross_process": True, "disposable": True}


class GoogleDriveBackend(Backend):
    """REAL Shared Drive backend implementing the CentralPersistence 3-op contract against a DriveClient.

    Objects (state_v{N}.json, HEAD.json) are files in a disposable folder (test namespace) under the Shared
    Drive. `put_bytes` create-or-updates by name; `get_bytes` downloads the real bytes back from Drive;
    `exists` checks presence in the namespace. Requires an explicit, provisioned DriveClient + drive_id +
    namespace — fail-closed otherwise, so nothing here can fabricate live Drive persistence.
    """
    KIND = "google_shared_drive"

    def __init__(self, client=None, drive_id=None, namespace=None, folder_id=None):
        self.client = client
        self.drive_id = drive_id
        self.namespace = namespace
        self.folder_id = folder_id
        self._object_ids = {}          # name -> Drive object id (captured for evidence)

    def _require(self):
        if self.client is None or self.drive_id is None or self.namespace is None:
            raise RuntimeError(
                "GoogleDriveBackend is not provisioned (need client + drive_id + namespace). "
                "Refusing to run without a real, authorized Drive client.")

    def _ensure_folder(self):
        self._require()
        if self.folder_id is None:
            self.folder_id = self.client.ensure_namespace(self.drive_id, self.namespace)
        return self.folder_id

    def put_bytes(self, name, data):
        fid = self._ensure_folder()
        existing = self.client.find(fid, name)
        if existing is not None:
            oid = self.client.update(existing, data)
        else:
            oid = self.client.create(fid, name, data)
        self._object_ids[name] = oid
        return oid

    def get_bytes(self, name):
        fid = self._ensure_folder()
        oid = self.client.find(fid, name)
        if oid is None:
            raise FileNotFoundError(name)
        self._object_ids[name] = oid
        return self.client.download(oid)

    def exists(self, name):
        fid = self._ensure_folder()
        return self.client.find(fid, name) is not None

    def object_id(self, name):
        return self._object_ids.get(name)

    def teardown(self):
        """Trash every object in the disposable namespace + the folder; return remaining child count."""
        self._require()
        if self.folder_id is None:
            return 0
        for child in self.client.list_children(self.folder_id):
            self.client.delete(child["id"])
        self.client.delete(self.folder_id)
        # verify gone
        return len(self.client.list_children(self.folder_id)) if self.client.exists_id(self.folder_id) else 0

    def describe(self):
        return {"kind": self.KIND, "backend_type": self.KIND, "drive_id": self.drive_id,
                "disposable_test_namespace": self.namespace, "folder_id": self.folder_id,
                "provisioned": self.client is not None,
                "client_backend_type": getattr(self.client, "backend_type", None)}


def make_backend(kind, root=None, client=None, drive_id=None, namespace=None, folder_id=None):
    if kind == SharedVolumeBackend.KIND:
        return SharedVolumeBackend(root or os.environ.get("P0E3_CENTRAL_DIR", "/data/se/central"))
    if kind == GoogleDriveBackend.KIND:
        return GoogleDriveBackend(client=client, drive_id=drive_id, namespace=namespace, folder_id=folder_id)
    raise ValueError("unknown backend kind: %r" % kind)
