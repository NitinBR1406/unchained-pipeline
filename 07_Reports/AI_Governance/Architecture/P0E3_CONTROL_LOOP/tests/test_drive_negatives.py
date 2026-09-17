"""P0-E3 Slice-2 Shared Drive NEGATIVE matrix: every Drive defect MUST force the live gate to FAIL closed."""
import os, json, tempfile, shutil
from _harness import Counter, live_shaped_drive_contract
from control_loop import live_evidence as LE
import live_acceptance_p0e3 as G
c = Counter("DNEG")

BASE = tempfile.mkdtemp()
LE.build_pass_bundle(BASE, drive=live_shaped_drive_contract())   # hermetic live-shaped PASS baseline
c.ok("base_bundle_is_PASS", G.verify(BASE)["FINAL"] == "PASS")


def clone():
    d = tempfile.mkdtemp()
    shutil.copytree(BASE, os.path.join(d, "e"))
    return os.path.join(d, "e")


def edit_drive(dirp, mutate):
    p = os.path.join(dirp, LE.F_DRIVE)
    obj = json.load(open(p))
    json.dump(mutate(obj), open(p, "w"), indent=2)


def case(label, mutate_dir, expect_crit):
    d = clone(); mutate_dir(d)
    v = G.verify(d)
    c.ok(label, v["FINAL"] == "FAIL" and (expect_crit is None or expect_crit in v["failed_criteria"]))


DRV = "REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"

# 1. shared-volume backend presented as Shared Drive
case("shared_volume_presented_as_drive_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "backend_type": "shared_volume"}), DRV)

# 2. backend_type != google_shared_drive
case("wrong_backend_type_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "backend_type": "s3"}), DRV)

# 3. wrong drive_id
case("wrong_drive_id_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "drive_id": "0AWRONGWRONGWRONG"}), DRV)

# 4. missing version_object_id
case("missing_version_object_id_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "version_object_id": ""}), DRV)

# 5. missing head_object_id
case("missing_head_object_id_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "head_object_id": None}), DRV)

# 6. missing Shared Drive readback
case("missing_drive_readback_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "readback_observed": False}), DRV)

# 7. readback SHA mismatch
case("drive_readback_sha_mismatch_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "readback_sha_matches": False}), DRV)

# 8. CAS HEAD not observed
case("cas_head_not_observed_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "cas_head_update_observed": False}), DRV)

# 9. Shared Drive test artifacts remain after teardown
def _artifacts_remain(d):
    p = os.path.join(d, LE.F_POC); o = json.load(open(p))
    o["SHARED_DRIVE_TEST_ARTIFACTS_REMAINING"] = True; o["POC_INFRA_REMAINING"] = True
    json.dump(o, open(p, "w"))
case("drive_artifacts_remain_FAIL", _artifacts_remain, "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING_IS_FALSE")

# 10. drive evidence entirely missing
case("missing_drive_evidence_FAIL", lambda d: os.remove(os.path.join(d, LE.F_DRIVE)), DRV)

# 11. stale writer not rejected on Drive
case("drive_stale_not_rejected_FAIL",
     lambda d: edit_drive(d, lambda o: {**o, "stale_write_rejected": False}), DRV)

# aggregate cannot mask a shared-volume drive contract
def _agg_lies(d):
    p = os.path.join(d, LE.F_AGG); o = json.load(open(p)); o["REAL_SHARED_DRIVE_PERSISTENCE_OBSERVED"] = True
    json.dump(o, open(p, "w"))
    edit_drive(d, lambda o: {**o, "backend_type": "shared_volume"})
case("aggregate_cannot_mask_shared_volume_FAIL", _agg_lies, DRV)

c.done()
