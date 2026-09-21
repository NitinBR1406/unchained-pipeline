INTELLIGENCE V01 — Track CLAUDE_B — FROZEN_V01 — observed 2026-09-22 UTC
Contents:
  REPORT_CLAUDE_B_FROZEN_V01.md        readable report (all required sections)
  data/RAW_DATASET.csv|.json           168 rows (GLOBAL 85, HINDI_INDIAN 83, CROSSOVER 0, OWN_DATA 0)
  data/SOURCES_PROVENANCE.csv          list/feature source registry with as-of + observation dates
  data/LITERATURE_EVIDENCE.csv         24 verified literature sources, numbers as stated
  data/COLLECTOR_BATCH_G00_RAW.txt     verbatim output of the one per-song collector that completed before the halt
  data/ANALYSIS_RESULTS.json           computed descriptives (per-cell n)
  data/MACHINE_READABLE_RESULT.json    findings, reference zones, VOCAL_KEY_OPTIMIZER, engine design, ID chain, RECEIPT
  code/*.py                            computation code; run order: build_dataset -> merge_batch_g00 -> literature -> analyze -> machine_result
  HASHES.txt                           SHA-256 over final bytes of every file above (coordinator should recompute on receipt)
This freeze preserves the report; it does not certify its claims. No cross-track synthesis.
