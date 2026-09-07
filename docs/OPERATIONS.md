# Operations

## Normal flow (Nitin's actions in bold)
1. Register source + build edit (system / Claude).
2. Sandbox preview render (Shotstack stage) → **Nitin reviews on mobile → APPROVE/REJECT (Gate 1)**.
3. On creative approve: freeze Edit JSON (SHA recorded) → production authorized.
4. Production render (runner: submit → poll → download → SHA) → auto tech QC (ffprobe).
   - QC fail / ffprobe missing / render fail → **HOLD** (Nitin notified, no action taken).
5. QC pass → **Nitin watches full master → APPROVE/REJECT (Gate 2)**.
6. On final-video approve: system auto-builds derivative plan + packaging → awaits publish.
7. Rights must be RIGHTS_PASS → **Nitin PUBLISH/HOLD (Gate 3)**.
8. On publish approve: system publishes via connected adapters, starts analytics.

## Commands
```
python3 -m unpipe.cli status  <workdir> <manifest>
python3 -m unpipe.cli approve <workdir> <manifest> creative     <asset_id> <sha> "notes"
python3 -m unpipe.cli approve <workdir> <manifest> final_video  <asset_id> <sha> "notes"
python3 -m unpipe.cli approve <workdir> <manifest> publish      <asset_id> <sha> "notes"
python3 -m unpipe.cli advance <workdir> <manifest> [master_path] [master_sha]
```

## Production render (until hosted)
```
export SHOTSTACK_PRODUCTION_API_KEY="..."   # once, in your shell
bash shotstack_production_render.sh <frozen.json> --master --name <OUTPUT>.mp4
```

## HOLD handling
Material failures (missing source/audio, duration/geometry/fps mismatch, watermark on a production
asset, hash mismatch, render failure, rights hold, missing approval) route to HOLD/TECH_QC_FAIL.
Resolve the cause, then re-run the stage. Transient failures (timeout, 429, 5xx) retry with backoff
inside the runner.

## Drive routing (planned, non-destructive)
`Campaigns/<campaign_id>/{00_Source-Raw,01_Working,02_Branding-Assets,03_Previews,04_Master,
05_Derivatives,06_Packaging,07_Publish-Ready,08_Published,09_Analytics,99_Archive}`. Do not
destructively reorganize the existing Drive; migrate via a mapping plan first.
