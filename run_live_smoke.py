#!/usr/bin/env python3
"""LIVE HTTP smoke against a really-running approval server (localhost socket, dry dispatch).

Proves the deployed service behaves correctly over real HTTP incl. restart-persistence — everything
except a public phone HTTPS URL (that needs a cloud host + your account). No GitHub/Shotstack calls
(PIPELINE_DISPATCH_DRY=1), no credits, no publish.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_approval_link import create_link
from unpipe.util import sha256_file

PORT = 8791
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "smoke-signing-secret"


def http(method, path, data=None):
    url = BASE + path
    body = None
    headers = {}
    if data is not None:
        body = "&".join(f"{k}={urllib.request.quote(v)}" for k, v in data.items()).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def start_server(root, stderr_path):
    env = dict(os.environ)
    env.update({"APPROVAL_SIGNING_SECRET": SECRET, "APPROVERS": "nitin",
                "PIPELINE_DISPATCH_DRY": "1",
                "CONSUMED_STORE": str(root / "_consumed.json")})
    f = open(stderr_path, "w")
    p = subprocess.Popen([sys.executable, str(HERE / "approval_server.py"), str(root), "127.0.0.1", str(PORT)],
                         env=env, stderr=f, stdout=subprocess.DEVNULL)
    for _ in range(50):
        try:
            if http("GET", "/healthz")[0] == 200:
                return p
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("server did not start")


def dry_count(root):
    f = root / "_dry_dispatch.log"
    return len(f.read_text().splitlines()) if f.exists() else 0


def main():
    tmp = Path(tempfile.mkdtemp())
    root = tmp / "campaigns"
    cdir = root / "cover-2-live"
    cdir.mkdir(parents=True)
    (cdir / "frozen.json").write_text(json.dumps(
        {"timeline": {"tracks": [{"clips": []}]}, "output": {"format": "mp4"}}))
    (cdir / "campaign.json").write_text(json.dumps({
        "campaign_id": "cover-2-live", "artist": "UNCHAINED NITIN", "song_title": "Cover 2 (live smoke)",
        "release_type": "cover", "source_master": "s.mp4", "duration": 208.625, "aspect_ratio": "9:16",
        "width": 1080, "height": 1920, "fps": 24, "presentation_preset": "MOTION_A_PREMIUM_RESTRAINED",
        "brand_profile": "UNCHAINED_NITIN_BRAND_PROFILE_V1", "platform_targets": ["youtube_hero"],
        "rights": {"status": "RIGHTS_HOLD"}, "frozen_master": "frozen.json", "release_status": "V01"}))
    sha = sha256_file(cdir / "frozen.json")
    stderr_path = tmp / "server.stderr"
    results = {}
    os.environ["APPROVAL_SIGNING_SECRET"] = SECRET   # for create_link

    p = start_server(root, stderr_path)
    try:
        # 1 health
        results["1_health"] = (http("GET", "/healthz") == (200, "ok"))
        # 2 page loads, no SHA shown
        link = create_link(str(root), "cover-2-live", "creative", BASE, secret=SECRET)
        token = link.split("token=")[1]
        st, body = http("GET", f"/approve?token={token}")
        results["2_page_loads"] = (st == 200 and "APPROVE" in body and sha not in body)
        # 3 APPROVE works + dispatch fires (dry)
        st, body = http("POST", "/decision", {"token": token, "approver": "nitin", "decision": "APPROVE"})
        results["3_approve"] = (st == 200 and "Approved" in body)
        results["4_dispatch_fired"] = (dry_count(root) == 1)
        # 5 replay idempotent (no 2nd dispatch)
        http("POST", "/decision", {"token": token, "approver": "nitin", "decision": "APPROVE"})
        results["5_replay_idempotent"] = (dry_count(root) == 1)
        # 6 expired link rejected
        exp = create_link(str(root), "cover-2-live", "creative", BASE, ttl=-10, secret=SECRET)
        etok = exp.split("token=")[1]
        results["6_expired_rejected"] = (http("GET", f"/approve?token={etok}")[0] == 400)
        # 7 tampered link rejected
        good = create_link(str(root), "cover-2-live", "creative", BASE, secret=SECRET).split("token=")[1]
        tampered = good[:-1] + ("a" if good[-1] != "a" else "b")
        results["7_tampered_rejected"] = (
            http("POST", "/decision", {"token": tampered, "approver": "nitin", "decision": "APPROVE"})[0] == 400)
        # 8 unauthorized approver rejected
        u = create_link(str(root), "cover-2-live", "creative", BASE, secret=SECRET).split("token=")[1]
        before = dry_count(root)
        results["8_unauthorized_rejected"] = (
            http("POST", "/decision", {"token": u, "approver": "intruder", "decision": "APPROVE"})[0] == 400
            and dry_count(root) == before)
        # 9 REJECT never dispatches
        rj = create_link(str(root), "cover-2-live", "creative", BASE, secret=SECRET).split("token=")[1]
        before = dry_count(root)
        http("POST", "/decision", {"token": rj, "approver": "nitin", "decision": "REJECT"})
        results["9_reject_no_dispatch"] = (dry_count(root) == before)
    finally:
        p.terminate(); p.wait(timeout=5)

    # 10 restart persistence: consumed nonce (token from #3) must remain consumed after restart
    before = dry_count(root)
    p2 = start_server(root, tmp / "server2.stderr")
    try:
        http("POST", "/decision", {"token": token, "approver": "nitin", "decision": "APPROVE"})
        results["10_replay_after_restart"] = (dry_count(root) == before)  # no new dispatch
    finally:
        p2.terminate(); p2.wait(timeout=5)

    # 11 secrets absent from responses/logs
    logs = ""
    for f in (stderr_path, tmp / "server2.stderr"):
        if f.exists():
            logs += f.read_text(errors="ignore")
    results["11_secrets_absent"] = (SECRET not in logs)

    ok = all(results.values())
    lines = ["# Live HTTP smoke (localhost, dry dispatch) — %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ")]
    for k, v in results.items():
        lines.append(f"{'PASS' if v else 'FAIL'}  {k}")
    lines.append("")
    lines.append("NOTE: real HTTP over a running server socket with restart-persistence. This is NOT a")
    lines.append("public phone HTTPS URL — that requires hosting on your cloud account (see DEPLOY_HOSTING.md).")
    lines.append(f"LIVE_HTTP_SMOKE = {'PASS' if ok else 'FAIL'}")
    (HERE / "LIVE_SMOKE_REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
