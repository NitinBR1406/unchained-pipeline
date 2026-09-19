# Catalog bootstrap V01

Pure `compile_catalog(inventory, observations=None, resolver=None)` creates the
master catalog, gap report, four queues, offline operational sheet view and
authorized expansion backlog. It performs no filesystem reads, sheet writes or
external dispatch. Existing Factory identifiers are referenced as nullable
attribution links until real canonical records are available; no alternate
canonical approvals/financial engine is created.

Inventory requires exact top-level fields: `schema=CATALOG_INVENTORY_V01`,
`schema_version=1`, UTC `observed_at`, `source_root`, `scope_status`, `folders`.
Folder fields: `relative_path`, `entries`, `source_ref`, boolean `complete`.
Entry fields: `relative_path`, `kind`, nullable integer `bytes`, nullable `sha256`,
`availability`, `source_ref`. Entry paths are root-relative and folder-prefixed.
References are nonempty evidence URIs or `{uri,sha256}`. URI-only Finder evidence
records observations; it does not prove asset bytes. Hashes absent from a
read-only UI inventory remain null. Completeness is explicit, never inferred.

Folder labels are not verified titles. Files give candidate role hints only.
Music/lyrics/vocal/tuning/mix/master/stems/backing/MIDI/BPM/key/video status stays
UNKNOWN. Filename years do not prove 2008 recreation; extensions do not establish
decode success; `master` does not establish mastering completion or approval.

Optional semantic observations require exact fields `relative_path`, `field`,
`value`, `evidence_refs` and a byte resolver that validates evidence hashes.
Evidence must substantiate the asserted semantic fact before calling this API;
hash equality alone is not attestation authenticity. Accepted fields and statuses
are strict enums in `engine.py`; no approvals, payment/revenue values, rights or
publication claims are accepted. An explicit production status plus its required
component facts routes work; presence alone never marks readiness. Nitin reviews
unresolved identity by default. No message is sent to Vatsal by queue generation.

LIVE_READY means the expressly evidenced library status, not performance rights
or publish approval. Reactivation readiness similarly remains release-gated.
Shared Nitin × Vatsal view is an offline projection pending separately authorized
Shared Drive/Sheets implementation and operational change control.
