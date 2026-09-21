# INTELLIGENCE V01 — three blind tracks

Start with [research report](SYNTHESIS/SONG_SUCCESS_INTELLIGENCE_V01.md) and [Vatsal production brief](SYNTHESIS/VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01.md).

The three independent provider reports were frozen before comparison. Completion means a bounded study and usable reference workbench; it does not establish a best key/BPM, hit probability or measured retention. Raw provider mistakes remain in the frozen folders and are corrected only in separate audits/synthesis.

- [Readable comparison](SYNTHESIS/CROSS_VALIDATION_MATRIX_V01.md)
- [Consensus and disagreement](SYNTHESIS/CONSENSUS_AND_DISAGREEMENT_V01.md)
- [Machine-readable intelligence](SYNTHESIS/SONG_SUCCESS_INTELLIGENCE_V01.json)
- [Factory feature design](SYNTHESIS/SONG_SUCCESS_INTELLIGENCE_ENGINE_V01.json)
- [Vocal key optimizer](SYNTHESIS/VOCAL_KEY_OPTIMIZER_V01.json)
- [Delivery index](SYNTHESIS/DELIVERY_INDEX_V01.json)

## Independent artifacts

GEMINI_A contains RAW_PROMPT, raw report/dataset/provenance, freeze receipt and a separately preserved correction addendum. Its quantitative findings are not accepted. CLAUDE_B contains the original downloaded ZIP, received-byte receipt and provider_artifacts/track_b with report, CSV/JSON, source registry, literature, code and provider hashes. CHATGPT_C contains report, raw data, success observations, source registry, code and freeze receipt.

All per-track prompts have identical SHA-256. Track C is an OpenAI GPT agent in Codex, not a consumer ChatGPT browser session. Prior-context and collection limits are disclosed in receipts. Neither agent's results were supplied to another before its freeze.

The freeze gate, replay audits, claim audit, final QA and QA-resolution files are at this folder's root. Run python3 verify_freezes.py and python3 validate_delivery.py for offline integrity/consistency checks. build_synthesis.py regenerates JSON/brief/matrix; the principal research report is editorially maintained.

MANIFEST.sha256 covers all delivered files except itself. Hashes establish bytes, not source truth. No deployment, publication, cost commitment or production-state change was performed.
