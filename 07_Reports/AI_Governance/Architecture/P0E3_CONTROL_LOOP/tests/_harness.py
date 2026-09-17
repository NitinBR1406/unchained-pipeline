"""Shared tiny test harness (same style as P0-E1/P0-E2 offline tests). No pytest dependency."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # P0E3_CONTROL_LOOP
ARCH = os.path.dirname(ROOT)                       # .../Architecture
for p in (ROOT, os.path.join(ARCH, "P0E1_CONTROL_PLANE")):
    if p not in sys.path:
        sys.path.insert(0, p)


def live_shaped_drive_contract():
    """A TEST-layer, live-shaped Drive contract for exercising the gate's all-criteria PASS path offline.

    Represents what a genuine live Drive run emits (source='live_drive_lifecycle') — it is NOT the synthetic
    offline fixture, and it is NOT read from any recorded artifact. Values are deterministic TEST values. This
    lets negative/positive tests establish a PASS baseline hermetically without any recorded live artifact.
    """
    h = "1" * 64
    return {
        "backend_type": "google_shared_drive",
        "drive_id": "0AG0CqqUZ6YuXUk9PVA",
        "disposable_test_namespace": "TEST_ONLY_live_shaped_ns",
        "version_object_id": "TEST_ONLY_live_version_object",
        "head_object_id": "TEST_ONLY_live_head_object",
        "write_observed": True,
        "readback_observed": True,
        "expected_sha256": h,
        "readback_sha256": h,
        "readback_sha_matches": True,
        "cas_head_update_observed": True,
        "head_readback_observed": True,
        "stale_write_rejected": True,
        "SHARED_DRIVE_TEST_ARTIFACTS_REMAINING": False,
        "source": "live_drive_lifecycle",
    }


class Counter:
    def __init__(self, tag):
        self.tag = tag
        self.P = 0
        self.F = 0
        self.FAILS = []

    def ok(self, name, cond):
        if cond:
            self.P += 1
            print("PASS", name)
        else:
            self.F += 1
            self.FAILS.append(name)
            print("FAIL", name)

    def done(self):
        print("\n%s_TOTAL=%d PASSED=%d FAILED=%d" % (self.tag, self.P + self.F, self.P, self.F))
        if self.FAILS:
            print("FAILURES:", self.FAILS)
        sys.exit(1 if self.F else 0)
