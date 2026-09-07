#!/usr/bin/env python3
"""Autonomous production executor entrypoint (invoked by GitHub Actions; never by Nitin).

Reads the Shotstack production key from the SHOTSTACK_PRODUCTION_API_KEY env var (a GitHub
Actions encrypted secret). Picks the queued production job for the campaign and runs it end to end
(submit -> poll -> download -> hash -> register -> tech QC -> advance state). No terminal, no key
copy, no manual polling/download/ffprobe.

Usage (CI): python3 prod_executor_entry.py --campaign <id> --manifest <path> --workdir <path>
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from unpipe.orchestrator import Campaign
from unpipe.executor import run_production_job, HttpProductionBackend
from unpipe.jobs import IN_PROGRESS, JOB_QUEUED


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out-name", default=None)
    args = ap.parse_args()

    c = Campaign(args.workdir, args.manifest)
    frozen = c._resolve_frozen()
    if not frozen:
        print("no frozen master resolvable; nothing to render"); return 2
    out_name = args.out_name or c.manifest.get("production_master_name", "PRODUCTION_MASTER.mp4")

    # pick a queued job (created by creative approval); idempotent if already DONE
    jobs = [j for j in c.jobs.all() if j["status"] == JOB_QUEUED or j["status"] in IN_PROGRESS]
    if not jobs:
        print("no queued production job (need creative approval first)"); return 3
    job = jobs[0]

    backend = HttpProductionBackend()  # real Shotstack production; key from env only
    res = run_production_job(c, job, backend, str(frozen), out_name, poll_interval=6, poll_max=200)
    print(f"job {res['job_id']} -> {res['status']} qc={res.get('tech_qc_status')}")
    return 0 if res["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
