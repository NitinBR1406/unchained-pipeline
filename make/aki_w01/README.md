# AKI W01 — Make scenario builders and checks (P2 / P3 / M1 / R1)

Builders that generate the Make blueprints for the AKI W01 placement publisher (P2 9974134), TikTok direct post (P3 9975129),
metrics collector (M1 9974218) and publication reconcile (R1 9975098). All four are stored **inactive / on-demand** in Make;
nothing here activates, schedules or runs them. `PRODUCTION_DEPLOYMENT_AUTHORIZED = FALSE`, `PUBLICATION_AUTHORIZED = FALSE`.

Campaign data (registry, captions, Drive ids, read-backs) is deliberately **not** in this public repo.

| file | purpose |
|---|---|
| `build_p2.py` | P2 f2: lock-before-claim (`plock:<placement>:a<n>`, insert-only), per-run owner `{{uuid}}`, ownership fence (GetRecord, `returnWrapped:false`) before every status write / upload / write-back, hash over fetched bytes, gate call, IG hosting register + strict signed-URL filter for a private GCS bucket (`AKI_IG_BUCKET`, not committed; unset = `UNCONFIGURED` = IG always BLOCKED), module-bound `error.type`/`error.message` with `ifempty`, unknown upload outcome -> `OUTCOME_UNKNOWN` |
| `build_p3.py`, `make_fence.py` | same fencing for TikTok; photo hosting `UNCONFIGURED` |
| `build_m1.py` | metrics collector; run token `{{uuid}}` (`var.execution.id` is empty at runtime). Needs `AKI_M1_SHEET_ID` |
| `build_r1.py` | R1 v2: `PUBLISHED` only via a stored platform id verified by id (account/type/window/text); otherwise `CANDIDATE_UNVERIFIED` / `MULTIPLE_CANDIDATES` / `NOT_FOUND` / `STORED_ID_MISMATCH` / `STORED_ID_NOT_VERIFIABLE` / `CONFLICTING_STORED_IDS`. R1 **does** update internal registrations (status/reconcile fields in data store 196442), never platform content |
| `make_error_refs.py` | binds `error.*` to the handler's module |
| `make_contract_fixture.py` | regenerates `tests/fixtures/p2_gate_contract_20261014.json` from a stored P2 read-back |
| `build_test_lock_v2.py`, `eval_lock_tests.py` | synthetic lock/ownership tests run in Make on an empty test data store (not the campaign store) |
| `test_*.py`, `check_stored_vs_builders.py` | local model tests over the real filter JSON; `test_p2_safety.py` needs the (local) campaign registry, `test_media_binding.py` needs `AKI_SYN_DIR` |

Build: `AKI_IG_BUCKET=... python3 build_p2.py && python3 build_p3.py && AKI_M1_SHEET_ID=... python3 build_m1.py && python3 build_r1.py`, then run the tests from this directory.
