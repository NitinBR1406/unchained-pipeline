"""Shared tiny test harness (same style as P0-E1/P0-E2 offline tests). No pytest dependency."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # P0E3_CONTROL_LOOP
ARCH = os.path.dirname(ROOT)                       # .../Architecture
for p in (ROOT, os.path.join(ARCH, "P0E1_CONTROL_PLANE")):
    if p not in sys.path:
        sys.path.insert(0, p)


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
