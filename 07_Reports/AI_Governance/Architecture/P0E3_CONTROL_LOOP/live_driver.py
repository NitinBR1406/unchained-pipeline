"""P0-E3 Slice-2 LIVE driver (runs ON the GitHub Actions runner; disposable, non-production).

Phases:
  run       -> execute the durable control loop live against a cross-process central backend (shared volume),
               dispatching real Temporal ControlPlaneTask workflows via the frozen P0-E2 LiveRunner, then
               assemble the full canonical live evidence bundle.
  assemble  -> (re)assemble the evidence bundle from artifacts already on disk (no new execution).

Real Temporal workflow/run ids are read from the dispatch evidence the frozen P0-E2 LiveRunner persists
(WORKFLOWS_JSON), never invented. Checkout SHAs, teardown POC and container crash observations are supplied
by the workflow as env/JSON. Booleans are real Python bools. No production / Make / Render / social mutation.
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "P0E1_CONTROL_PLANE"))

from control_loop import live_evidence as LE


def _load_json(path, default):
    if path and os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return default
    return default


def _checkout():
    return {"requested": os.environ.get("REQUESTED_SHA", ""),
            "CHECKED_OUT_SHA": os.environ.get("CHECKED_OUT_SHA", "")}


def _workflows():
    # produced by the frozen P0-E2 LiveRunner dispatch step (real Temporal ids); path via env
    return _load_json(os.environ.get("WORKFLOWS_JSON"), {})


def _poc():
    # written by the teardown-verification step via evidence_json.py (real Python bool)
    return _load_json(os.environ.get("POC_JSON"), {"POC_INFRA_REMAINING": None})


def _container_obs():
    return _load_json(os.environ.get("CONTAINER_OBS_JSON"), {})


def _real_drive_contract():
    """Execute the REAL Google Shared Drive lifecycle. Fails closed (no credentials => not observed).

    Auth mechanism: Application Default Credentials on the runner (a Drive service account provisioned via
    the CI secret mechanism). This function NEVER reads, prints or embeds a secret; it only asks the Google
    auth library for ADC. If ADC is unavailable, it returns a contract that cannot satisfy the live gate.
    """
    from control_loop.drive_client import GoogleApiDriveClient
    drive_id = os.environ.get("P0E3_DRIVE_ID", LE.AUTHORITATIVE_DRIVE_ID)
    namespace = os.environ.get("P0E3_DRIVE_NAMESPACE", "P0E3_LIVE_ACCEPTANCE_DRIVE_TEST")
    try:
        import google.auth  # provided only when the runner is provisioned with Drive auth
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
        client = GoogleApiDriveClient(credentials=creds, drive_id=drive_id)
        return LE.run_drive_lifecycle(client, drive_id, namespace)
    except Exception as e:  # no ADC / no google client / Drive error -> fail closed, honest
        return {"backend_type": "unprovisioned", "drive_id": drive_id,
                "disposable_test_namespace": namespace, "error": str(e),
                "write_observed": False, "readback_observed": False, "readback_sha_matches": False,
                "cas_head_update_observed": False, "head_readback_observed": False,
                "stale_write_rejected": False, "version_object_id": None, "head_object_id": None,
                "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": False}


def _drive():
    # allow an already-produced drive contract (e.g. recorded proof) via DRIVE_JSON; else run it live
    j = _load_json(os.environ.get("DRIVE_JSON"), None)
    return j if j is not None else _real_drive_contract()


def _poc_with_drive(drive):
    poc = dict(_poc())
    if "TEMPORAL_POC_INFRA_REMAINING" not in poc:
        poc["TEMPORAL_POC_INFRA_REMAINING"] = poc.get("POC_INFRA_REMAINING", None)
    poc["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"] = drive.get("SHARED_DRIVE_TEST_ARTIFACTS_REMAINING", True)
    return poc


def run(evidence_dir):
    central_root = os.environ.get("P0E3_CENTRAL_DIR", os.path.join(evidence_dir, LE.CENTRAL_DIR))
    loop = LE.run_durable_live(evidence_dir, backend_root=central_root)
    drive = _drive()
    facts = LE.build_bundle(evidence_dir, loop, checkout=_checkout(), workflows=_workflows(),
                            poc=_poc_with_drive(drive), drive=drive, container_obs=_container_obs())
    print("P0E3_LIVE run assembled; aggregate:", json.dumps(facts["aggregate"]))
    return facts


def assemble(evidence_dir):
    # rebuild the loop view over the already-produced live ledger + central store, then reassemble
    from control_loop.control_loop import DurableControlLoop, Clock
    from control_loop.live_backend import SharedVolumeBackend
    loop = DurableControlLoop(evidence_dir, clock=Clock(9000))
    loop.persistence.backend = SharedVolumeBackend(os.environ.get(
        "P0E3_CENTRAL_DIR", os.path.join(evidence_dir, LE.CENTRAL_DIR)))
    drive = _load_json(os.path.join(evidence_dir, LE.F_DRIVE), None) or _drive()
    facts = LE.build_bundle(evidence_dir, loop, checkout=_checkout(), workflows=_workflows(),
                            poc=_poc_with_drive(drive), drive=drive, container_obs=_container_obs())
    print("P0E3_LIVE reassembled")
    return facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["run", "assemble"])
    ap.add_argument("--evidence", required=True)
    a = ap.parse_args()
    if a.phase == "run":
        run(a.evidence)
    else:
        assemble(a.evidence)


if __name__ == "__main__":
    main()
