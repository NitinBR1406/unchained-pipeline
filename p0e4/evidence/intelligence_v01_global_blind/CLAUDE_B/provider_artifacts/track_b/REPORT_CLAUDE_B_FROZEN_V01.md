# INTELLIGENCE V01 — Track CLAUDE_B — FROZEN_V01

Independent, evidence-only research study: which musical and structural characteristics are associated with exceptional song performance globally, in Hindi/Indian music, and across those markets — and which reference principles suit new UNCHAINED NITIN originals (Nitin, producer Vatsal Chevli).

Observation date (all pages): 2026-09-22 UTC. Provider: Anthropic (Claude, Cowork session). No cross-track synthesis. No coordinator conclusions, previous UNCHAINED reports, project files, chat histories or other tracks were read.

**Read this first — collection limitation.** The success-signal layer (views, streams, chart longevity, upload dates) and the literature layer were completed. The per-song musical-feature layer (BPM, key, mode, duration, energy, structure timing, vocal range) was **halted by operator instruction**. Of six parallel per-song collectors, **one (batch G00, GLOBAL rows G001–G025) completed and wrote its output before the halt registered**; its raw output is preserved verbatim (`data/COLLECTOR_BATCH_G00_RAW.txt`) and merged. The other five (global G01–G02, all three Hindi/Indian batches) did not run. Feature fields are therefore populated for **25 of 168 rows** (all global YouTube mega-hits, 2009–2018 uploads), a published sheet-music vocal range exists for 10, and **no Hindi/Indian row has any musical feature**. Chorus-arrival/intro timing is null for every row. Hindi musical-parameter findings rest entirely on **verified published aggregate studies**. Nothing was padded; nothing was invented.

---

## 1. METHODOLOGY

**Research question (frozen).** As stated in the prompt. Cohorts are kept separate: GLOBAL_SUCCESS, HINDI_INDIAN_SUCCESS, GLOBAL_HINDI_CROSSOVER, UNCHAINED_NITIN_OWN_DATA (future; zero rows; nothing invented).

**Unit of record.** One recording as listed by the source: for YouTube lists, one official upload (a lyric video and an official video of the same song are separate rows only if both appear in a source — e.g. Aankh Marey lyrical vs. video); for Spotify lists, one track entity; for chart-longevity lists, one charting single. Deduplication: when the same song appears in two sources it is one row carrying both signals (e.g. G003 has W1, K4 and S2 values).

**Inclusion criteria.** Commercial songs by recording artists. Excluded: nursery/kids content, ads, animation episodes, devotional recitations (Shree Hanuman Chalisa, Sankat Mochan Hanuman Ashtak — logged, not used), and non-Indian repertoire found inside Indian sources (Starboy, Perfect, Pink Venom — recorded as crossover presence only). Two novelty acts (Crazy Frog "Axel F", El Chombo "Dame Tu Cosita") and one film-soundtrack song ("Let It Go") are kept and flagged.

**Market and era.** Global = worldwide YouTube/Spotify/Billboard lists; Hindi/Indian = Indian YouTube list (multilingual, language labelled), Spotify India chart totals, Billboard India Songs. Era: sources are "all-time" lists, so the sample is naturally concentrated in 2012–2022 uploads/releases with a small pre-2010 catalog tail (kept, flagged `catalog_pre2010`). Historical references from the literature go back to 1952.

**Sampling frame (largest reliable practical).**
- GLOBAL (n = 85): Wikipedia most-viewed YouTube videos top-30 (music rows, 16) ∪ kworb most-viewed music videos top-40 (38 music rows after exclusions) ∪ Wikipedia most-streamed Spotify songs top-40 ∪ Billboard Hot 100 "most total weeks at #1" top-15.
- HINDI/INDIAN (n = 83): Wikipedia most-viewed Indian YouTube videos (38 song rows) ∪ kworb Indian top-40 (adds 2) ∪ kworb Spotify India all-time chart totals top-40 (37 Indian songs) ∪ Billboard India Songs 2022 #1s (7 after exclusions).
- CROSSOVER (n = 0): no song present in both cohorts.

**Fields.** Success signals as observed (exact counts, page as-of dates, upload dates, chart days, peak position, days at peak, peak-day streams, weeks at #1). Descriptive views/day = views ÷ days since official upload (approximate: kworb pages print no update date). Watch hours, retention and repeat listens: **not observed anywhere; all null.** Musical fields: null unless read on a fetched page (see limitation above). Every measured value is tagged `feature_kind = secondary_estimate` with method and confidence; no value is from memory.

**Evidence classes used throughout:** (a) measured fact read on a page; (b) secondary estimate (Spotify-derived features republished by Tunebat/SongBPM/GetSongBPM); (c) analyst listening interpretation — **none made** (no audio was played); (d) hypothesis — labelled as such.

**Computation.** `code/build_dataset.py` (transcribed success-signal rows → CSV/JSON), `code/merge_batch_g00.py` (merges the completed collector batch; parses sheet-music key/tempo/range quotes), `code/literature.py` (verified literature table), `code/analyze.py` (descriptives, per-cell n, stratification), `code/machine_result.py` (findings, zones, engine and optimizer spec, receipt). Re-run order: build_dataset → merge_batch_g00 → literature → analyze → machine_result.

**Stratification attempted.** Era/upload year (both cohorts); language (Indian YouTube); film vs non-film (Indian YouTube; Hindi-only sub-cell); peak-position vs chart-days (Spotify India); platform (YouTube vs Spotify vs Billboard overlap). Not attemptable: duration, artist prior popularity (no field observed), age-of-artist.

**Frequency ≠ association ≠ causation.** All cohorts are hit-only. Descriptives here are frequencies among hits. Associations are cited only from studies that compared hits with non-hits (Interiano; Askin & Mauskapf; Nunes et al.; Morris). No causal claims are made anywhere.

---

## 2. SOURCES_PROVENANCE (summary; full table in `data/SOURCES_PROVENANCE.csv` and `data/LITERATURE_EVIDENCE.csv`)

| id | source | as-of | note |
|---|---|---|---|
| W1 | Wikipedia – most-viewed YouTube videos | 2026-08-30 | 30-row table, rounded to 10 M |
| K4 | kworb.net – most-viewed music videos | undated | exact counts + "Yesterday" |
| S2 | Wikipedia – Spotify streaming records | 2026-09-13 | billions, 3 dp |
| B3 | Wikipedia – Hot 100 achievements | chart dated 2026-01-03 (caveat: a 2026 entry present) | weeks at #1 |
| WI | Wikipedia – most-viewed Indian YouTube videos | 2026-02-18 | exact counts; language column |
| KI | kworb.net – Indian artists top videos | undated | |
| SI | kworb.net – Spotify India daily totals | charts 2019-02-27 → 2026-08-26 | chart-day totals only, not lifetime |
| BI | Wikipedia – India Songs | 2022 rows only | chart launched Feb 2022 |
| TB/SB/GB | Tunebat / SongBPM / GetSongBPM – Shape of You | — | secondary Spotify-derived features |
| L01–L24 | 24 verified literature sources (peer-reviewed: L01, L03, L04, L05, L16, L18, L21, L22, L24; industry/journalism/blog datasets otherwise) | — | numbers quoted as stated |

Collector batch G00 also read 74 pages (Tunebat, SongBPM, GetSongBPM, Wikipedia song pages) — every per-song URL is in `data/COLLECTOR_BATCH_G00_RAW.txt` and in each row's `feature_provenance_urls`.

Failed/inaccessible (recorded, not bypassed): Royal Society page for Interiano (403; eScholarship PDF used instead), Washington Post 2024 shorter-songs interactive (403), CBC 2019 chorus article (403), OhioLINK dissertation (robots), Uploading Substack (rate limit), Wikipedia "List_of_Billboard_India_Songs_number-one_songs" (not in cache / likely non-existent), kworb `topvideos_in.html` (404), audiostrip (JS-only), tunebat first attempt for Blinding Lights (429 — not retried after halt).

---

## 3. RAW_DATASET

`data/RAW_DATASET.csv` / `data/RAW_DATASET.json` — 168 rows × 78 columns. Success-signal columns are populated per source. Musical-feature columns are populated for the 25 rows of collector batch G00 (G001–G025) and null elsewhere. `exclusions`, `feature_layer_note` and `unchained_nitin_own_data` (empty) are inside the JSON. Missingness (from `ANALYSIS_RESULTS.json`): bpm/key/mode/duration present 25, null 143; energy 24; vocal range (sheet-music) 10; meter 17; intro, first-vocal, first-hook, chorus arrival, hook repetitions, structure, tessitura, climax placement present 0, null 168.

Feature provenance for the 25 rows: Spotify-derived features republished by Tunebat/SongBPM/GetSongBPM (BPM, key, mode, energy, danceability, valence, loudness, acousticness) **plus** Wikipedia "Composition" quotes citing published sheet music (Musicnotes/Kobalt) for key, tempo, meter and vocal range. Where both existed, the sheet-music key/mode was preferred, because the Spotify-derived key disagreed with the published key in **7 of 14** comparable cases — almost always by relative major/minor. Tunebat returned 429/403 for 12 of the 25 songs; SongBPM/GetSongBPM were used as fallbacks (both Spotify-sourced). All values are `feature_kind = secondary_estimate`, confidence medium (sheet-music-backed) or low-medium (single site). Sheet-music vocal ranges describe the published arrangement, not a measured recording.

---

## 4. GLOBAL_FINDINGS (n and confidence per item; full list in MACHINE_READABLE_RESULT.json)

**Per-song feature cell (batch G00: 25 global YouTube mega-hits, uploads 2009–2018; not random; no Spotify-only or Hot-100-only songs).**
- Tempo as recorded: median 110 BPM (p25 91, p75 130, range 75–190; the 190 is a 12/8 count for "Perfect", felt ≈ 95). Bands: < 90 20 %, 90–109 28 %, 110–129 24 %, 130–149 20 %, ≥ 150 8 %. **23 of 25 feature pages state a half- or double-time alternative** — perceived pulse is ambiguous for nearly every hit and must be resolved by listening before any BPM is used as a target. One documented tempo change (Counting Stars 107.6 → 122). Meter 4/4 where stated (17/25).
- Mode: major 56 % (14), minor 32 % (8), modal 8 % (D Dorian "Uptown Funk", G Mixolydian "Shake It Off"), 1 null. Pitch classes spread across D (5), B, B♭, E♭, G (3 each) — no single key dominates.
- Duration (Wikipedia infobox): median 3:44 (224 s), p25 3:32, p75 3:56, min 2:25 ("Dame Tu Cosita"), max 4:41 ("Thinking Out Loud"). These video mega-hits run ≈ 45 s longer than the 2024 Spotify-chart average (~3:00, L07) — era and platform effect.
- Spotify-derived energy median 74 (n = 24), danceability median 68 (n = 24), valence median 45 but bimodal (17–29 vs 69–96; n = 15), loudness median −6 dB (n = 15).
- Published vocal ranges (n = 10): span median 22 semitones (p25 17.5, p75 25.5; min 15 "Dark Horse", max 39 "Uptown Funk" incl. falsetto/ad-libs); lowest notes B2–B♭3 (median ≈ E3), highest A4–D6 (median ≈ C♯5). On paper, typical male-lead hits sit roughly E3–C♯5; three of ten span ≥ 26 semitones.
- Structural timing was stated on a fetched page for only 2 songs ("Blank Space": two-bar drum-machine intro; "Shake It Off": bridge 2:18–2:42). Chorus arrival is null for all rows.

**What was observed on the success-signal layer (frequencies among hits).**
- Spotify top-40: 82.5 % released 2012 or later; median release year 2016; 30/40 from the 2010s; catalog tail of 5 (1983–2008). n = 40, high.
- YouTube top-38 music videos: all > 3.1 bn; median exact views 3.93 bn; for the 17 rows with observed upload dates, median upload age ≈ 4,325 days and descriptive views/day ≈ 1.04 M (range 0.62–2.58 M). "Yesterday" views median ≈ 674 k — these totals are accumulated over a decade, not launched. n = 38/17, high/medium.
- Overlap is thin: 5 songs in both YouTube top-38 and Spotify top-40; 2 in both YouTube and Hot 100 longest-#1; 1 in both Spotify and Hot 100. Exceptional performance is platform-specific. n = 85, high.
- Hot 100 longest #1 runs (n = 15): 14–22 weeks; 7 of 15 are 2015 or later.

**What the verified literature says (aggregate, mostly era trends; association only where a non-hit comparison existed).**
- Duration: Hot 100 average ≈ 3:30 by 2018 (−20 s in five years; 6 % of 2018 hits ≤ 2:30) [L06]; Spotify charting average ≈ 3:00 in 2024, −30 s vs 2019, all major genres −17 s or more 2018→2024 [L07]; UK #1s ≈ 3:00 (1967) → ≈ 4:00 (1984) → ≈ 3:00 (2022) [L10, n = 1,404]. Era trend; not shown to predict success.
- Intro / first vocal: US top-10 intros > 20 s (mid-1980s) → ≈ 5 s (2015), −78 %; tempo +≈ 8 %; time-to-title −≈ 18 % [L01/L02, n = 303]. **Crucially, within-artist popular-vs-less-popular comparison showed no such pattern** — the shrinking intro is what everyone does, not what separates the winners. Trends "mostly continued" to 2020 with only weak Spotify-specific acceleration [L03].
- First chorus: industry sample Q3 2014 (n = 20): average first chorus 0:33, 47 % between 0:20–0:39, 5 % after 1:00; intros averaged 9 s [L09]. Informal 2021–2024 Hot 100 analysis (n ≈ 2,500, LLM-labelled): chorus at 30–60 s performed best, immediate-chorus songs worst, author reports no statistical significance [L17]. Low confidence either way.
- Tempo: US top-5 hits averaged 93.2 BPM (2017) and 92.6 BPM (2018), modal band 78–80 BPM; Spotify top-25 average fell 23 BPM 2012→2017 to 90.5 [L15]. 43 % of 2010s #1s < 100 BPM vs 25 % in 1960–1989 [L11]. #1s vs other charting songs: 117 vs 120 BPM — negligible [L14]. Half/double-time perception is unresolved in every source; a "90 BPM" hit is often felt as 180 double-time or 45 half-time.
- Mode: minor-key share of US #1s ≈ 25 % (pre-2000) → ≈ 55 % (post-2000) [L11]; UK #1s 55–58 % minor 2019–2022 [L10]. But #1s vs non-#1 charting songs: 65/35 vs 63/37 major/minor [L14] — mode is an era signature, not a success discriminator.
- Key: Hooktheory corpus (n > 1,300) skews to C major / A minor; B♭ only 4 % [L13] — instrument ergonomics, not a success effect.
- Key changes & endings: ≈ 25 % of #1s had key changes 1960s–1990s; one in 2010–2020 [L12]. Fade-outs: 93–100 % of UK #1s in 1971–1983, zero in 2011, 23 since [L10].
- Emotion/energy (association, hits vs. all releases, UK 1985–2015, n = 14,536 with features): successful songs happier, more party-like/danceable, less relaxed, more "female" than the average release, while the market as a whole trended sadder and less bright [L04]. Prediction accuracy ≈ 0.74 from features, ≈ 0.85 adding a "superstar" variable — artist prior popularity carries much of the signal.
- Typicality (association, n ≈ 27,000 Hot 100 1958–2016): inverted-U — moderately atypical songs relative to the previous 52 weeks reach higher peaks than highly typical ones [L05].
- Repetition (association): top-10 songs more lyrically repetitive than the rest in every year 1958–2017 (n = 15,000) [L23]; more chorus repetition → higher probability of #1 and faster climb, with excessive word repetition offsetting the benefit [L24].
- Melody (frequency, top-5/year 1950–2022, n = 366): since 2000 ≈ 2.8 notes/s, mean interval ≈ 2 semitones, two-thirds of pitches within ≈ 5.5 semitones; choruses have fewer notes, lower density and larger intervals than verses [L21, L22]. Tempo variability collapsed after 1979 (median yearly CV 1.51 → 0.03) [L16].

---

## 5. HINDI_FINDINGS

**Observed on this sample.**
- Indian YouTube top-40 song rows: Hindi 60 %, Punjabi 17.5 %, Haryanvi 5 %, Hindi/Punjabi 5 %, Tamil/Bhojpuri/Hindi-Bengali 2.5 % each, 2 unlabelled. Film 60 % / non-film 40 % overall; **Hindi-only rows: film 74 % (20/27)**. T-Series uploaded 45 % of the list. n = 40, high.
- Upload years cluster 2016–2020 (2019: 24 %; 2018: 18 %); median age ≈ 2,928 days; descriptive views/day median ≈ 436 k (≈ 40 % of the global top-video median). Non-film median views/day 466 k (n = 14) vs film 379 k (n = 22): small cells, era- and star-confounded; frequency only. Confidence low.
- Spotify India all-time chart totals (n = 37 Indian songs): two archetypes. (a) 17 songs peaked at #1, median chart life ≈ 863 days; six held #1 for ≥ 100 days (Jo Tum Mere Ho 105, Sahiba 124, Maan Meri Jaan 123, Excuses 101, Raataan Lambiyan 141, Pehle Bhi Main 124). (b) 10 songs never reached the top 3 yet stayed on the daily top-200 for > 1,900 days (Tum Se Hi, Kabira, Tera Hone Laga Hoon, Dil Diyan Gallan, Saibo, Baarishein, Humdard, Mere Sohneya, Kaise Hua, Agar Tum Saath Ho) — catalog longevity romantic ballads. Peak-day streams median ≈ 1.03 M; average streams per chart day median ≈ 346 k. High for counts.
- Only 27 % of Spotify India titles carry a "(From "Film")" tag and several untagged titles are film songs; film share on Spotify is unidentifiable from this source.
- **Zero overlap between the YouTube-view leaders and the Spotify-India-stream leaders.** YouTube India rewards dance/party and regional-language video hits; Spotify India totals are dominated by romantic ballads and streaming-native independent artists (Anuv Jain ×3, King ×2, Shubh ×2, Sachet–Parampara ×2). High.
- Billboard India Songs 2022 (n = 7 in cohort): longest #1 runs were Punjabi non-film (295: 18 wk; The Last Ride: 14 wk) and Telugu film (Srivalli: 9 wk); Hindi film Kesariya 3 wk. Single-year data; medium.

**Verified literature (India).**
- Melodic scale of Bollywood hits 1953–2013 (n = 310, expert-labelled): ≈ 25 % Asavari (natural-minor type), ≈ 25 % Bilawal (major), ≈ 25 % Bhairavi/Kafi/Khamaj, 8 % pentatonic, 4 % Kalyan; Kalyan declined after the 1960s, Bhairavi rose [L18]. Hindi hits split roughly evenly between minor-type and major frames — a different balance from the post-2000 Western minor majority.
- Lyric language: English words rose in 2006–2015 vs 1995–2005 Bollywood lyrics (n = 300); "baby" the most frequent English word [L19].
- Duration: 8-minute film songs of the 1970s–80s vs. songs that "often fade out after the four-minute mark" today [L20] — anecdotal; no quantified Indian duration or tempo dataset was found (searches logged as returning nothing useful).
- No India-specific study of intro length, chorus timing, hook repetition or vocal range was found.

---

## 6. CROSSOVER_FINDINGS

GLOBAL_HINDI_CROSSOVER n = 0. No Hindi/Indian song appears in any global list fetched. Observed cross-presence runs global → India only: Starboy (Spotify India chart total 353 M, 1,852 chart days, peak 9), Perfect (335 M, 2,085 days, peak 24), Pink Venom (India Songs #1, 1 week). The only Indian upload in the global YouTube top-30 is the devotional Hanuman Chalisa (5.67 bn; 4.4 M views "yesterday"), excluded from the song cohort but evidence that Indian repertoire reaches global-scale view counts through domestic daily repeat use. Crossover principles below are therefore editorial test directions, not empirical zones.

---

## 7. TOP_REFERENCE_ZONES

Ten fully empirical zones are **not supported** by the evidence gathered. Eight zones are listed; three rest on literature with n ≥ 300, five rest on observed success-signal shape with null musical features. Absolute keys are never a recommendation (see §9).

| id | zone | BPM / mode / emotion | hook–structure–production principle | examples (global / Hindi) | support | confidence |
|---|---|---|---|---|---|---|
| Z1 | Slow-groove minor pop, half-time feel | 78–96 perceived (verify half/double); minor; melancholic-yet-danceable | chorus by 0:30–0:45; intro ≤ 10 s; 1–2-bar repeated hook; no key change; hard ending; grid-tight | Shape of You (96, C♯m, 3:54, G♯3–G♯5), Despacito (89, Bm, 3:47, F♯3–B4), Faded (90, E♭m), Lean On (98, Gm), Sorry (100, E♭ major, E♭3–B♭4), Mi Gente (105, Bm) / Asavari-type ballads (untested) | L15, L11, L02; G00 cell (6 rows) | medium |
| Z2 | Mid-tempo major feel-good pop | 100–125; major or Dorian/Mixolydian; happy/party | title within 20–30 s; high chorus repetition; short verses; bright, danceable | Uptown Funk (115, D Dorian, 4:30, B2–D6), Sugar (120, D♭, 3:55, D♭3–F♭5), Girls Like You (125, C), Dame Tu Cosita (110, D, 2:25) / Bom Diggy Diggy, Kala Chashma (unmeasured) | L04, L14; G00 cell (5 rows) | medium |
| Z3 | Acoustic/piano ballad with emotional arc | 75–95 felt (often notated 150–190 in 6/8–12/8); major; sad/romantic | strongly repeated chorus; climax at ≈ 70–80 % of duration (hypothesis); minimal intro; vocal-forward | Perfect (190 in 12/8 ≈ 95 felt, A♭, 4:23), Let Her Go (75, G, 4:12), Thinking Out Loud (79, D, 4:41, B2–A4), Someone You Loved (unmeasured) / Agar Tum Saath Ho, Tujhe Kitna Chahne Lage, Tum Se Hi (unmeasured) | S2 + SI frequency; G00 cell (3 rows) | low-medium |
| Z4 | Catalog-longevity Hindi romantic ballad | unmeasured; Asavari/Bhairavi-type expected | mukhda–antara form; 1,900–2,600 chart days without peaking near #1 | — / Tum Se Hi, Kabira, Tera Hone Laga Hoon, Dil Diyan Gallan, Saibo, Baarishein | SI (10 songs) | medium (signal) / low (features) |
| Z5 | Streaming-native independent Hindi singer-songwriter | unmeasured; intimate/romantic | non-film single-artist brand; 100+ days at #1 | — / Jo Tum Mere Ho, Sahiba, Maan Meri Jaan, Excuses, Husn, Finding Her | SI (17 peak-#1; 6 with ≥ 100 days) | medium / features null |
| Z6 | Punjabi/Haryanvi dance video hit | unmeasured; celebratory | video-led, regional label channels; longest India Songs #1 runs | — / Lehanga, 52 Gaj Ka Daman, Laung Laachi, High Rated Gabru, 295 | WI (11 rows), BI | medium / features null |
| Z7 | Repetition-forward hook design | any | high chorus repetition, moderate word repetition, title-as-hook | (population-level) | L23 (15,000), L24 | medium-high (association) |
| Z8 | Optimal differentiation | any | one salient atypical element against an otherwise typical profile | (population-level) / Hinglish lyric mix trend | L05 (≈ 27,000), L19 | medium-high |

**Editorial test directions (not empirical):** E1 Hindi/Urdu ballad in the Z1 tempo band with an English hook phrase (crossover probe); E2 chorus-first edit vs 30–45 s chorus arrival, same recording; E3 2:45–3:15 master vs 3:45+ extended by platform; E4 Asavari vs Bilawal framing of the same lyric; E5 climax at 70–80 % of duration with a sustained top-of-tessitura note, measuring the retention curve.

**Structural principles that can be studied without copying protected melody or lyrics:** chorus arrival time, hook repetition count, section proportions, hook contour direction, tessitura width in semitones, climax placement as % of duration, tempo and half-time feel, mode and scale-degree emphasis, ending type.

---

## 8. Success signals, platform logic and what was not observed

Observed: official YouTube views and upload dates (W1/WI), exact views and "yesterday" deltas (K4/KI, undated), Spotify global streams (S2), Spotify India chart days / peak / days at peak / peak-day streams / chart totals (SI), weeks at #1 (B3/BI). Derived, descriptive only: views/day since upload. **Not observed: watch hours, retention, repeat listens, subscriber conversion. Views × duration was not computed and must not be used as watch time.**

---

## 9. VOCAL_KEY_OPTIMIZER (design)

Purpose: transpose a reference zone to Nitin's measured voice while preserving mode, intervals/contour envelope, groove and structure. **Nitin's actual range is unknown; NITIN_FIT_SCORE = null.** Inputs: reference mode; relative verse floor/ceiling and chorus/climax peak in semitones from the tonic (an envelope, not a copied melody); Nitin's measured comfortable tessitura, climax ceiling and passaggio (all currently null). Algorithm: enumerate tonics, map offsets to absolute notes, apply hard constraints (verse within tessitura; climax ≤ ceiling), preferences (chorus peak 2–5 semitones above verse ceiling and clear of the passaggio; instrument-friendly tonic if performed live), output the transposition interval and a fit score that stays null until measurements exist. The only range evidence in this track is arrangement-level: ten published sheet-music ranges for global hits span 15–39 semitones (median 22) and sit roughly E3–C♯5 for male leads; this is an envelope to test against, not a target for Nitin.

Safe audition/test protocol: 10–15 min warm-up; never push past discomfort; sessions ≤ 30 min; three separate days; measure lowest comfortable sustained note, highest comfortable chest/mix note at speaking dynamic, highest belt/mix note at performance dynamic (≥ 2 s), usable head-voice ceiling, passaggio region (5-note ascending scale on /a/), and a tessitura fatigue test (same 3-minute song at original, −2, +2 semitones, fatigue rated 1–5); record every take as WAV with metronome tag and log MIDI note numbers, date, time and fatigue into UNCHAINED_NITIN_OWN_DATA with a recording_id and metric_timestamp.

---

## 10. Design-only scoring engine and ID chain

Inputs: key, mode, bpm, perceived pulse flag, song_duration, emotion, energy, vocal_range (measured), hook_characteristics {chorus_arrival, hook_repetitions, title_in_hook, intro, first_vocal}, release_type, target_platform, structural_features. Outputs: SUCCESS_SIGNAL_SCORE as "k of m evidence-backed criteria met" (never a probability), EVIDENCE_CONFIDENCE (minimum over criteria used plus count of null inputs), REFERENCE_MATCH_SCORE per zone (null where zone fields are null), NITIN_FIT_SCORE (null until measured), EXPECTED_RETENTION_PROFILE (emitted only if ≥ 5 observed retention curves exist in own data; otherwise null with reason), RISKS (e.g. chorus > 60 s, duration > 4:00 for streaming, key change, excessive word repetition, highly typical profile, climax above measured ceiling), COMPARABLE_SONGS (by success-signal shape and release type until features exist). Explicitly never output: hit probability, view forecasts, numeric scores without evidence ids.

ID chain (proposed schema; no claim about any existing architecture): recording_id (versioned) → song_id → content_id → publication_id (platform × upload timestamp × official flag) → publication_metric rows (metric_name, value, metric_timestamp, source_api) → campaign_id / experiment_id (pre-registered metric) → lead_id (attribution_evidence rows with type and confidence) → booking_id → revenue_event_id. Rules: watch hours only from platform analytics exports; retention only from observed curves; every metric row timestamped and sourced.

---

## 11. UNCERTAINTIES_LIMITATIONS

1. **Feature layer incomplete (dominant limitation).** 143/168 rows lack BPM/key/mode/duration; 158/168 lack any vocal-range value; 168/168 lack chorus-arrival/intro timing; **0/83 Hindi/Indian rows have any musical feature.** The 25-row feature cell is a non-random subset (global YouTube mega-hits, 2009–2018) and its values are secondary estimates (Spotify-derived mirrors; sheet-music quotes). Spotify-derived keys disagreed with published keys in 7/14 comparable cases. Hindi musical-parameter conclusions are literature-derived only.
2. **Hit-only selection.** Every cohort is a top list; no controls; frequencies among hits cannot identify what distinguishes hits. Only L04, L05, L23, L24 compare against non-hits, and they establish association, not causation.
3. **Survivorship and age bias.** All-time lists favour uploads aged 6–12 years; recent exceptional songs are under-represented; views/day is a crude descriptor confounded by age, catalog promotion and platform growth.
4. **Source dependencies.** Wikipedia (editor-curated, as-of dates vary by table), kworb (undated pages; chart-day totals only since 2019-02-27 for India), Spotify-derived features via third-party mirrors (Spotify's own audio-features endpoint is no longer publicly available). One Wikipedia rank inconsistency (Sugar/Baby Shark) and one B3 as-of inconsistency were reported as read.
5. **Film-status and language labelling** rely on source annotations; untagged Spotify titles may be film songs; Indian list is multilingual.
6. **Half/double-time ambiguity** is not resolved by any source; BPM bands in zones are perceived-tempo guesses to be verified by listening.
7. **Unidentifiable relationships:** artist prior popularity, marketing spend, film star presence, playlist placement, and platform algorithms are unobserved and plausibly explain much of the variance (L04's superstar variable).
8. **Prior exposure disclosure.** Memory snapshot exposed the analyst to Nitin's name, channel name, producer's name and work domain — none used as evidence. Singer/film attributions the analyst typed into the sample file from recall were **not** used in the dataset.
9. **Not attempted:** any audio download or listening analysis; any fetch of blocked sites via alternate routes; any endpoint-variant loops after the halt.

---

## 12. Receipt — FROZEN_V01

Track CLAUDE_B (Anthropic Claude). Tools: WebSearch, WebFetch (3 collector subagents + lead), Python 3 scripts in `code/`. Pages fetched successfully: 13 data/list/feature pages (6 failed) + 24 verified literature pages (7 literature fetch failures); all failures logged (§2). Collector batch G00 (the one per-song collector that completed): 74 pages fetched OK, 14 failed or degraded (mostly Tunebat 429/403), raw output preserved verbatim. Rows: GLOBAL 85, HINDI/INDIAN 83, CROSSOVER 0, OWN_DATA 0; rows with musical features 25 (all global), with sheet-music vocal range 10; literature verified 24, cited-not-verified 5. Feature collection halted by operator instruction on 2026-09-22; five of six collectors never ran. Observation date 2026-09-22 UTC. Independence: no other track, coordinator conclusion, prior report or project file read. This freeze preserves the report; it does not certify its claims. SHA-256 of every delivered file is in `HASHES.txt`; the coordinator should recompute over received bytes.
