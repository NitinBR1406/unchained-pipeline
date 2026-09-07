# Cover #2 dry-run — 2026-09-07T17:37:44.557298Z
source registered
after creative approve: jobs queued = 1 · dispatch calls = ['cover-2-dryrun'] (frozen SHA 34fd2407426a…)
=> APPROVE auto-dispatched the render workflow (no GitHub UI, no terminal)
executor job status = DONE · qc = PASS · render_id = fake-render-123 · out_sha = 66ca2ef29740…
campaign state after render+QC = AWAITING_FINAL_VIDEO_APPROVAL
notifications = ['AWAITING_FINAL_VIDEO_APPROVAL']
idempotent re-run: submits unchanged = True

Zero-terminal checks (simulated executor path):
  Nitin action = CREATIVE APPROVE only
  GitHub Actions UI / Run-workflow / campaign_id entry by Nitin = NONE (auto-dispatched)
  terminal / curl / key-copy / polling / download / ffprobe by Nitin = NONE
  publish performed = NO · publish_approval = False
COVER2_DRYRUN = PASS
