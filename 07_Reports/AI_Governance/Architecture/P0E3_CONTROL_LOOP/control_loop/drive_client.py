"""P0-E3 Slice-2 Google Shared Drive client interface + a real reference client + an in-memory fake.

`DriveClient` is the minimal contract the GoogleDriveBackend needs. Two implementations:

  * GoogleApiDriveClient — the REAL client (google-api-python-client). It authenticates ONLY from an
    explicitly provided credentials object (Application Default Credentials / service account). It never
    reads, prints, commits or embeds a secret; if no credentials are provided it fails closed. This is the
    client the live CI run would use IF (and only if) the runner is provisioned with a Drive service account.

  * InMemoryDriveClient — a deterministic fake used by OFFLINE tests to exercise the full CentralPersistence
    CAS lifecycle over the Drive-shaped API. It reports backend_type "google_shared_drive_FAKE" so it can
    never masquerade as the real Shared Drive in live acceptance.

Object model: files live under a folder (the disposable test namespace). Each object has an id; content is
raw bytes. `create` returns a new id; `update` overwrites by id; `download` returns bytes; `find` locates by
name within the folder; `delete` trashes; `exists_id` checks a specific id.
"""


class DriveClient:
    backend_type = "abstract"

    def ensure_namespace(self, drive_id, name):
        """Create/return the disposable folder id under the Shared Drive. Returns folder_id."""
        raise NotImplementedError

    def create(self, folder_id, name, data):
        """Create an object; return its id."""
        raise NotImplementedError

    def update(self, file_id, data):
        raise NotImplementedError

    def download(self, file_id):
        raise NotImplementedError

    def find(self, folder_id, name):
        """Return id of object named `name` in folder, or None."""
        raise NotImplementedError

    def exists_id(self, file_id):
        raise NotImplementedError

    def delete(self, file_id):
        raise NotImplementedError

    def list_children(self, folder_id):
        raise NotImplementedError


class GoogleApiDriveClient(DriveClient):
    """REAL Shared Drive client. Fails closed without explicit credentials — never fabricates auth."""
    backend_type = "google_shared_drive"

    def __init__(self, credentials=None, drive_id=None):
        self._creds = credentials
        self.drive_id = drive_id
        self._svc = None

    def _service(self):
        if self._creds is None:
            raise RuntimeError(
                "GoogleApiDriveClient has no credentials. Provision a Drive service account "
                "(supplied to the runner via the CI secret mechanism) and pass its credentials; "
                "refusing to run without real, authorized auth.")
        if self._svc is None:
            from googleapiclient.discovery import build  # imported lazily; only needed for the real client
            self._svc = build("drive", "v3", credentials=self._creds, cache_discovery=False)
        return self._svc

    # --- all operations use supportsAllDrives / driveId for Shared Drive semantics ---
    def ensure_namespace(self, drive_id, name):
        svc = self._service()
        q = ("name = '%s' and '%s' in parents and trashed = false "
             "and mimeType = 'application/vnd.google-apps.folder'" % (name, drive_id))
        res = svc.files().list(q=q, corpora="drive", driveId=drive_id, includeItemsFromAllDrives=True,
                               supportsAllDrives=True, fields="files(id)").execute()
        if res.get("files"):
            return res["files"][0]["id"]
        meta = {"name": name, "parents": [drive_id], "mimeType": "application/vnd.google-apps.folder"}
        f = svc.files().create(body=meta, supportsAllDrives=True, fields="id").execute()
        return f["id"]

    def create(self, folder_id, name, data):
        from googleapiclient.http import MediaInMemoryUpload
        svc = self._service()
        media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
        f = svc.files().create(body={"name": name, "parents": [folder_id]}, media_body=media,
                               supportsAllDrives=True, fields="id").execute()
        return f["id"]

    def update(self, file_id, data):
        from googleapiclient.http import MediaInMemoryUpload
        svc = self._service()
        media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
        svc.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
        return file_id

    def download(self, file_id):
        svc = self._service()
        return svc.files().get_media(fileId=file_id, supportsAllDrives=True).execute()

    def find(self, folder_id, name):
        svc = self._service()
        q = "name = '%s' and '%s' in parents and trashed = false" % (name, folder_id)
        res = svc.files().list(q=q, includeItemsFromAllDrives=True, supportsAllDrives=True,
                               fields="files(id)").execute()
        fs = res.get("files") or []
        return fs[0]["id"] if fs else None

    def exists_id(self, file_id):
        svc = self._service()
        try:
            svc.files().get(fileId=file_id, supportsAllDrives=True, fields="id,trashed").execute()
            return True
        except Exception:
            return False

    def delete(self, file_id):
        svc = self._service()
        svc.files().update(fileId=file_id, body={"trashed": True}, supportsAllDrives=True).execute()
        return True

    def list_children(self, folder_id):
        svc = self._service()
        q = "'%s' in parents and trashed = false" % folder_id
        res = svc.files().list(q=q, includeItemsFromAllDrives=True, supportsAllDrives=True,
                               fields="files(id,name)").execute()
        return res.get("files") or []


class InMemoryDriveClient(DriveClient):
    """Deterministic fake for offline CAS lifecycle tests. Never the real Shared Drive."""
    backend_type = "google_shared_drive_FAKE"

    def __init__(self):
        self._folders = {}     # folder_id -> {name: file_id}
        self._files = {}       # file_id -> bytes
        self._n = 0

    def _id(self, prefix):
        self._n += 1
        return "%s_%d" % (prefix, self._n)

    def ensure_namespace(self, drive_id, name):
        fid = self._id("folder")
        self._folders[fid] = {}
        return fid

    def create(self, folder_id, name, data):
        fid = self._id("obj")
        self._files[fid] = bytes(data)
        self._folders.setdefault(folder_id, {})[name] = fid
        return fid

    def update(self, file_id, data):
        self._files[file_id] = bytes(data)
        return file_id

    def download(self, file_id):
        return self._files[file_id]

    def find(self, folder_id, name):
        return self._folders.get(folder_id, {}).get(name)

    def exists_id(self, file_id):
        return file_id in self._files

    def delete(self, file_id):
        self._files.pop(file_id, None)
        for m in self._folders.values():
            for n, i in list(m.items()):
                if i == file_id:
                    del m[n]
        return True

    def list_children(self, folder_id):
        return [{"id": i, "name": n} for n, i in self._folders.get(folder_id, {}).items()]
