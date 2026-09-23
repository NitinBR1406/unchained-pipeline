# Catalog Discovery V02 — Nitin iCloud music catalog

Read-only discovery completed. This is a technical candidate inventory, **not 88 confirmed songs**. Existing global Master State V16.3/state 29 remains unchanged; task-local evidence and NEXT_READY record this discovery without granting production authority.

- 78 top-level entries inspected; all in-scope directories enumerated without listing errors.
- 962 file metadata records; 77 local media files SHA256 verified; 28 WAV headers supply duration, sample rate, channels and sample width. Header parsing is not a full decode or musical-quality check.
- 835 files carry cloud/dataless indicators and remain NOT_LOCAL_AVAILABLE. 50 other files have local metadata only. No cloud download was requested.
- 88 provisional candidates: 60 song folders, 4 mashup/medley folders, 16 child folders, 8 individual recordings under NITIN 2008.
- 6 collections/special containers; 107 unassigned media candidates retained separately rather than counted as songs. Downloads, videos, performances and versions require identity association first.
- 19 administrative/system exclusions (including nested metadata). ING docs, automation administration and obvious root administrative PDFs were excluded; their contents were not read. Exclusion is reversible and deletes nothing.

## NITIN 2008

The container is not a song. Eight recordings are candidate child songs. “Mastered” in a filename proves neither mix/master completion nor authorship. Nitin must confirm original/cover, identity and current usability.

- asma mastered_01.wav: NOT_LOCAL_AVAILABLE
- KHAN KHAN MASTERED.wav: LOCAL_BYTES_VERIFIED
- KHILTA GHUL MASTERED.wav: LOCAL_BYTES_VERIFIED
- khud se mastered.wav: LOCAL_BYTES_VERIFIED
- raeena mastered.wav: LOCAL_BYTES_VERIFIED
- SANIYA MASTERED_00.wav: LOCAL_BYTES_VERIFIED
- tum sabse mastered.wav: LOCAL_BYTES_VERIFIED
- ye raat mastered_00.wav: LOCAL_BYTES_VERIFIED

## Minimal semantic review

Use NITIN_SEMANTIC_REVIEW_QUEUE.csv or the JSON queue. First confirm/correct identities and classify TYPE (original / cover / mashup / medley / reference / other / ?). Merge versions before answering readiness. The six container questions avoid a separate readiness form for every loose recording.

For MUSIC_READY, LYRICS_READY, VOCALS_READY, MIX_MASTER_READY, REVISION_REQUIRED and LIVE_READY use ✓ / ✗ / ?. All initial values are UNKNOWN; file presence is not readiness. Set PRIORITY, NEXT_ACTION and ACTION_OWNER only where known. A batch statement may cover explicitly named rows. Existing automated technical facts need no manual re-entry.

MASTER_CATALOG_V01 and the Nitin × Vatsal operational view will be prepared after these answers; the earlier V01 remains historical and is not overwritten. No Shared Drive or production sheet was changed.

## Evidence limits and reuse

Metadata is an observation at discovery time. Titles, years, originals, voice identity, rights, creative readiness and preferred versions are not proven. No archive extraction, lyric/document-content reading, BPM/key estimation, full decode, semantic approval, or publication occurred. Exact-byte duplicate groups are recorded separately; equal hashes do not assign song identity. Local access may update OS access metadata; no source write, rename, move, deletion or reorganization was performed.

The reproducible scanner and offline validator are in p0e4/catalog. The task ledger projects to TASK_STATE; it does not replace the global control-plane reducer. Existing release gates, source binding and frozen phases remain unchanged.
