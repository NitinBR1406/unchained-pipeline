# CLAUDE_INDEPENDENT_REPORT_V01 — Song Success Intelligence, Hindi key/mode × tempo study

Status: FROZEN_V01 (frozen 2026-09-21 22:36 UTC). Author: Claude (Cowork session, model id claude-fable-5-1). This freeze records what was actually established. It does not validate any hypothesis listed below.

## 1. The question (unchanged)

Which absolute key/mode and tempo/BPM combinations are common, or associated with stronger success signals, among successful Hindi songs of roughly the last 10–15 years, and which ten zones merit original-production reference testing by Nitin (vocals) and Vatsal Chevli (production)? Correlation is never described as causation anywhere in this report.

## 2. Headline answer

The evidence retrieved in this run is too thin to answer the performance-association half of the question, and only barely enough to describe frequency. Eleven recordings have a key, mode and BPM from a traceable source; eight of those also have a view count; no recording outside the billion-view tier has a view count at all. That means frequency among top-tier songs can be described (cautiously), but frequency cannot be separated from performance association, no per-cell confidence interval is defensible, and a ten-zone empirical ranking is not supported. Section 8 therefore presents zones as labelled hypotheses drawn from the data that exist, not as empirical winners. This is a limitation report by design, which is preferable to invented values.

## 3. Isolation and prior-exposure declaration

Only this question and public sources were used. No other agent's output, no prior UNCHAINED song-success report, no chat history and no project research file was consulted. Six data-collection subagents were dispatched and rejected by the user before they ran; none contributed anything. Unavoidable prior exposure: the session's memory index lists a file about the user's channel and a Make.com project; neither was opened. General background familiarity with Hindi film music was used for exactly one thing, the emotion/use-case tags, which are labelled analyst judgement (hypothesis level) in the dataset and were never used for numeric fields.

## 4. Sample selection rule (recorded before collection)

Two strata were fixed from traceable public lists before any key or BPM was looked up.

Stratum A (top-tier, survivorship-biased): every music-video row flagged Hindi, Hindi/Punjabi, Hindi/Bengali or Hindi/Urdu in the English Wikipedia "List of most-viewed Indian YouTube videos" as fetched on 2026-09-21. That yields 26 recordings after deduplicating the two official uploads of "Aankh Marey" (the lyrical upload at 1,278,800,084 views was kept as primary; the full video at 1,049,354,582 is noted). Three rows (Bum Bum Bole, Tujh Mein Rab Dikhta Hai, Dil Laga Liya) are pre-2011 film songs and are flagged as outside the 10–15-year window but retained.

Stratum B (critically recognised, mixed view levels): every winner and nominee for the Filmfare Best Male and Best Female Playback Singer awards, ceremonies 2012–2025, deduplicated across the two lists. That yields 138 recordings. Its purpose was to provide a comparison group whose views are not all above one billion, so that frequency could be separated from performance.

Frame total: 164 candidate recordings. The frame is delivered in full (sample_frame_candidates.csv) so the selection can be audited.

## 5. What was actually retrieved — inclusion, exclusion and missingness

Counts are computed by build_dataset_and_analysis.py and stored in analysis_results_CLAUDE_V01.json.

Frame total 164. With a YouTube view count: 26 (all Stratum A, all from the Wikipedia list; the direct YouTube watch page returned HTTP 429 to the fetch tool, so none was read directly). With key and BPM: 11 (8 in Stratum A, 3 in Stratum B). With BPM only: 1 (Bum Bum Bole). With key, BPM and views: 8. With two or more concordant key sources: 4 (Vaaste, Dilbar, Lut Gaye, Zaroori Tha counts as one key source plus a BPM-only confirmation). Unresolved conflicts: 1 (Tere Vaaste — songdata lists Bb minor 95 BPM and C major 125 BPM for what appears to be the same recording; the row is set to null). Frame-only rows with no data at all: 135.

Streaming indicators: null for every row (no streaming source was retrieved). Vocal range/tessitura: null for every row. Retention, replay counts and watch hours: null for every row; public view counts are not retention, and nothing in this report multiplies views by duration.

Why coverage is small: Tunebat rate-limited parallel requests (HTTP 429 on 5 of 7 pages), songdata.io's search served the same cached result page for every query after the first, Tunebat and Musicstax search pages are disallowed by robots.txt, and one songbpm page was a 404. Per the operator's instruction, none of this was worked around with URL variants or repeated probing; each unavailable source is listed with its status in provenance_CLAUDE_V01.json.

## 6. Measurement method and confidence

Every key and BPM in the dataset is a secondary-source estimate. songbpm.com, songdata.io, tunebat.com, musicgateway.com and getsongbpm.com all republish Spotify-style audio-analysis output, so agreement between two of them confirms transcription rather than independent measurement. No audio was downloaded or analysed, so no recording has an independently measured key or BPM. Confidence is therefore capped at "medium" (two or more concordant secondary estimates) and is "low" for single-source rows. Analyser key detection on Hindi songs is also known to be fragile: modal melodies over a drone are often reported as the relative major or minor, and Ab minor versus B major (Zaroori Tha) or F minor versus Ab major (Mile Ho Tum) are exactly the kind of relative-key pairs an analyser confuses. Mode labels here should be read as "analyser mode", not as a musicological classification.

Half/double tempo: songbpm.com lists half- and double-time equivalents for every row it served (e.g., Vaaste 90 / 180; Tujh Mein Rab Dikhta Hai 85 / 170; Bum Bum Bole 61 / 121 / 242). The dataset stores the analyser's primary value and the note verbatim; no felt-tempo judgement was applied because that would require listening.

Alternate recordings: Mile Ho Tum is the Reprise (Neha/Tony Kakkar), not the original; Dilbar (2018) and Cham Cham are recreations of older songs; Aankh Marey is a recreation and has two official uploads. Spotify durations (e.g., Vaaste 3:16) are shorter than the YouTube video (4:06 per Wikipedia); both are recorded, and the source of each duration is labelled.

Upload age and views/day: computed from the Wikipedia upload date and the Wikipedia view figure at the fetch date. Views/day is a descriptive average over the whole life of an upload; it is not a causal adjustment for age and is flattened by the early-viral phase.

## 7. Results — measured versus hypothesised

### 7.1 Frequency (n = 11 with key and mode; n = 12 with BPM)

Mode: major 6, minor 5. Keys (analyser): Bb major 2, F minor 2, and one each of Ab minor, F major, A minor, Ab major, B minor, Db major, C major. BPM: min 80, median 94.5, mean 96.6, max 121. Tempo zones: mid 85–99 BPM 5, upper-mid 100–114 BPM 4, slow <85 BPM 2, fast 115+ BPM 1. Mode × tempo cells: major × mid 85–99 = 4; minor × upper-mid 100–114 = 3; every other cell ≤ 1.

Reading: within this tiny sample the centre of gravity is 85–105 BPM; flat keys (Bb, Ab, Db, F) dominate the analyser output. With n = 11, any "cell" count of 3 or 4 is compatible with chance; no key or mode is over-represented in a way that survives an honest look at the sample size.

### 7.2 Performance association (Stratum A only, n = 8 with key/BPM and views)

Views per day across all 26 Stratum A rows: median 394,816, range 206,210 to 1,282,262. Among the 8 rows with mode: minor (n = 4) median 411,333 views/day; major (n = 4) median 499,874 views/day. Among tempo zones: mid 85–99 (n = 3) median 630,184; upper-mid 100–114 (n = 4) median 411,333; slow and fast have n = 1 each. These are descriptive medians of four or fewer values and carry no inferential weight; the two highest views/day rows among those with key/BPM (Lut Gaye 745,042 and Vaaste 630,184) are both recent non-film T-Series releases, and the two highest overall (Aaj Ki Raat 1,282,262 and Jhoome Jo Pathaan 897,850) have no key/BPM data at all, which is a release-type and channel confound as much as a key/tempo signal.

Stratification by year, duration, artist popularity and film status was designed (fields exist in the dataset) but could not be run: with eight rows, every stratum has n ≤ 3.

### 7.3 Confidence intervals

None computed. With per-cell n ≤ 4, a bootstrap interval would span nearly the whole plausible range and could be misread as evidence.

### 7.4 Selection, survivorship and confounding

Stratum A is, by construction, only the songs that already reached ~1 billion views, so anything common in it is also common among the survivors of an unknown denominator. Stratum B was intended to supply that denominator and did not receive outcome data in this run. Confounds that cannot be controlled here: channel size (T-Series dominates), release type (non-film singles vs film songs), star casting in the video, recreation of an already-famous melody (Dilbar, Cham Cham, Aankh Marey, Lut Gaye's qawwali hook), and upload age.

### 7.5 Does the data support a top ten?

No. Eight recordings with key, BPM and views cannot populate ten distinct zones, and without a comparison stratum the ranking would reproduce frequency, not performance. The zones in section 8 are hypotheses.

## 8. Reference zones — hypotheses for testing, not empirical winners

Each zone lists supporting n from this dataset, the recordings that actually carry the label, and evidence strength. "Suitability" refers to whether the zone is a reasonable test candidate, not to any predicted outcome. Absolute keys are not prescriptions for Nitin's voice; every zone should be transposed to a comfortable key while keeping tempo, mode and arrangement principles.

Zone H1 — Major, 85–95 BPM, mid-tempo romance ballad. Supporting n = 3 with views (Vaaste F major 90; Lut Gaye Bb major 91; Tujh Mein Rab Dikhta Hai Ab major 85) plus Chaleya C major 95 and Raataan Lambiyan Bb major 81 without views. Observed: the two highest views/day rows among the eight with key/BPM sit here; the two highest in the whole Stratum A (Aaj Ki Raat, Jhoome Jo Pathaan) have no key/BPM data. Emotion: romance. Production principles worth studying: short instrumental intro, hook stated within the first 30 seconds, a chorus that returns at least three times, sparse verse arrangement building to a fuller chorus. Vocal implication: sustained mid-register phrases; test chorus tessitura for repeated singing. Evidence strength: low (secondary estimates, n = 3 with outcomes). Suitability as a test candidate: high, because it is the best-populated cell.

Zone H2 — Minor, 100–110 BPM, dance/recreation. Supporting n = 3 (Dilbar A minor 104; Bom Diggy Diggy B minor 104; Zaroori Tha Ab minor 114, the last one being a ballad by feel and possibly a double-time analyser reading). Emotion: dance, item. Principles: percussive hook, strong downbeat, repeated two-bar rhythmic motif, chant-like chorus. Vocal implication: rhythmic delivery over sustained notes; range demands moderate. Evidence strength: low. Suitability: medium.

Zone H3 — Minor, 78–95 BPM, longing/heartbreak ballad. Supporting n = 2 (Mile Ho Tum Reprise F minor 80; Tum Hi Ho F minor 94 without views). Principles: piano or guitar-led, slow harmonic rhythm, chorus climbs to the top of the range. Vocal implication: the highest tessitura demand of the zones; chorus-repeat tests are essential before committing a key. Evidence strength: low. Suitability: medium.

Zone H4 — Major, 100 BPM, recreation/pop (Leja Re Db major 100). n = 1. Hypothesis only.

Zone H5 — Uplifting/children's anthem, ~121 BPM (Bum Bum Bole; key unavailable). n = 1, BPM only. Hypothesis only.

Zones H6–H10 (devotional, cinematic, fast dance 120+, slow devotional <75, modal/raga-based) — no recording in this dataset carries the tag with a key and BPM. They are listed only so that the study design shows what the frame did not reach; there is no supporting evidence here for any of them.

## 9. Practical tests for Nitin and Vatsal (no assumption about Nitin's range)

Measure first. Nitin's comfortable range and tessitura are null in this study and must be measured from his own recordings, not assumed. A practical protocol: pick one reference from H1, H2 and H3; write an original chorus in the same tempo, mode and arrangement shape; record the chorus in three candidate keys a whole tone apart; sing each chorus four times back-to-back as it would repeat in a full song; keep the key where the fourth repetition is as clean as the first. That gives a tessitura decision grounded in his voice rather than in the hit song's absolute key. Study structure, dynamics and arrangement of the reference; do not copy melody or lyrics.

## 10. Engine specification (design only)

The SONG_SUCCESS_INTELLIGENCE_ENGINE specification is delivered as engine_spec_SONG_SUCCESS_INTELLIGENCE_ENGINE_design_only.json. Inputs: key, mode, bpm, song_duration, emotion, energy, vocal_range, hook_characteristics, release_type, target_platform. Outputs: SUCCESS_SIGNAL_SCORE (null until a calibrated cell with n ≥ 30 and a calibration_id exists), EVIDENCE_CONFIDENCE, REFERENCE_MATCH_SCORE (descriptive similarity, always with matched n), EXPECTED_RETENTION_PROFILE (null until first-party retention curves exist), RISKS, COMPARABLE_SONGS. There is no hit-probability field by design. The evidence chain uses campaign_id, song_id, derivative_id, experiment_id, publication_id, lead_id, booking_id, revenue_id and evidence_ids as separate linked tables, and a missing hop returns null downstream rather than an estimate. Nothing in it reads or writes any live system.

## 11. Limitations (summary)

Small n (11 key/BPM, 8 with outcomes); no comparison stratum with outcomes; secondary-source key/BPM only, from one analyser family; analyser mode labels unreliable for modal Hindi melodies; possible half/double-tempo readings unverified; Wikipedia view figures of unknown snapshot date (one live comparison: Vaaste 1,717,251,224 on the list vs 1,759,265,677 on a third-party mirror the same evening); no streaming, retention, replay or watch-hour data; emotion tags are analyst judgement; survivorship in Stratum A; channel and release-type confounds.

## 12. Deliverables in this folder

CLAUDE_INDEPENDENT_REPORT_V01.md (this report); dataset_CLAUDE_V01.csv and dataset_CLAUDE_V01.json (164 rows, one per frame recording, null where unavailable, per-field source URLs and confidence); sample_frame_candidates.csv (selection frame); provenance_CLAUDE_V01.json (every URL fetched, timestamp, what it was used for, and the unavailable endpoints with reasons); analysis_results_CLAUDE_V01.json (all computed counts and medians); build_dataset_and_analysis.py (the exact code that produced the dataset and results); engine_spec_SONG_SUCCESS_INTELLIGENCE_ENGINE_design_only.json.

## 13. Completion receipt

Report identifier: CLAUDE_INDEPENDENT_REPORT_V01. Status: FROZEN_V01. Tools actually used: WebFetch, WebSearch, Bash/Python 3. Not used: audio analysis, YouTube Data API, Spotify API, browser automation, subagents (rejected before running), any other track's findings, any prior project file. Observation window: 2026-09-21 22:05–22:36 UTC; data cutoff is the state of the fetched pages at those timestamps. No publication, production mutation, purchase, new paid service, credential request or approval fabrication occurred. What is frozen is the evidence above and its limits; hypotheses H1–H10 remain unvalidated.
