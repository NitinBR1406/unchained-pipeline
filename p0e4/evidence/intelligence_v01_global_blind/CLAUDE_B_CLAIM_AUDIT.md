# CLAUDE_B frozen claim audit

Read-only audit of frozen B report, data and code; three consequential literature checks; not a new independent study. No other tracks inspected.

**Verdict:** retain as a descriptive, incomplete evidence inventory. Correct the explicit denominator/missingness errors and downgrade unsupported musical zones and score rules before synthesis. Raw provider artifacts were not edited.

Coverage: 168 source rows; 25 global BPM rows; 24 key/mode rows; zero Hindi musical-feature rows.

## B01 — HIGH: Hindi-only denominator is actually Hindi-inclusive

analyze.py tests whether "Hindi" is a substring. Its 20 film / 27 rows includes Hindi/Punjabi and Hindi/Bengali. Exact language == Hindi returns 19 film / 24 rows (79.17%), not 74%.

**Required interpretation:** Rename existing figure Hindi-inclusive; use 19/24 only when reporting exact Hindi labels. These remain upload-row frequencies.

## B02 — MEDIUM: Key and mode coverage overstated

Report section 3 says bpm/key/mode/duration present 25, null 143. RAW_DATASET and ANALYSIS_RESULTS show key and mode present 24, null 144; G004 Axel F has neither.

**Required interpretation:** Separate field denominators. Preserve BPM and duration n=25.

## B03 — HIGH: Z1 violates its own membership rule

Z1 says 78–96 perceived BPM and minor, but lists Lean On 98, Sorry 100 and major, Mi Gente 105. Pulse has not been listened to or consistently normalized.

**Required interpretation:** Treat Z1 as an editorial mixed reference set; it is not an empirical minor 78–96 cluster.

## B04 — HIGH: Structure prescriptions exceed observations

All 168 first-hook/chorus timing, hook repetition, tessitura and climax fields are null. Z1 specifies chorus 30–45 seconds, intro <=10 seconds, 1–2 bar hook, ending and grid tightness; Z4 assigns mukhda–antara and expected scales.

**Required interpretation:** Label each unmeasured field as a hypothesis. Literature trends cannot establish this joint recipe, especially for Hindi songs with zero musical measurements.

## B05 — HIGH: Unit of analysis mixes uploads, recordings and releases

H015/H033 are explicitly lyrical/video uploads of Aankh Maarey. G083 is a double-title chart single. Methods admit platform-dependent units but also call the unit one recording. No recording_id or canonical audio/version join supports recording-level deduplication.

**Required interpretation:** 168 means source records, not 168 verified unique recordings. Preserve both uploads, link their song/recording identities separately, and do not count them as independent musical examples. No claim of bit-identical audio is made.

## B06 — HIGH: Platform reward claim is not identified

Zero YouTube/Spotify-India overlap is a property of these truncated, differently timed leader lists. No audio was played, Indian features/language for Spotify rows are null, and no genre coding protocol exists.

**Required interpretation:** The assertion that YouTube rewards dance and Spotify rewards romantic ballads is an untested interpretation; zero overlap alone cannot identify platform preference. Note the overlap code checks WI but omits KI-only rows, a latent join bug even if the current zero remains unchanged.

## B07 — HIGH: Current India/West scale contrast exceeds L18

L18 supports approximately one quarter each Asavari and Bilawal, not an exhaustive 50/50 major/minor result. Its 310 historical hits are composer-enriched; two experts double-label only 50, one labels the rest. Authors caution against strong claims.

**Required interpretation:** Retain the historical scale frequencies with sampling caveats. Remove the current India-vs-post-2000-West comparison: periods, selection and scale taxonomies differ; pentatonic/modal cases cannot silently be forced into binary mode.

Primary source: [source](https://archives.ismir.net/ismir2013/paper/000103.pdf)

## B08 — MEDIUM: Repetition caveat is generalized across outcomes

L24 reports greater chorus and word repetition associated with #1 versus never-above-#90 songs, and chorus repetition with faster ascent among #1s. The excessive-word attenuation concerns Top-40 debut specifically.

**Required interpretation:** Keep these outcomes separate. Z7 moderate-word advice is a test hypothesis, not a universal optimum. Lab fluency experiments do not establish a causal field success effect.

Primary source: [source](https://msbfile03.usc.edu/digitalmeasures/jnunes/intellcont/Power%20of%20Repetition%20Final-1.pdf)

## B09 — MEDIUM: Typicality association is sound; one-element prescription is not

L05 supports an inverted-U association, using genre-weighted multidimensional similarity and a preceding-52-week comparison. Main regression n is 25,077; near-27,000 describes the broader chart dataset.

**Required interpretation:** Retain historical conditional association. Z8 one salient atypical element is an editorial translation, not a measured optimum or a directly transferable Hindi success rule.

Primary source: [source](https://business.columbia.edu/sites/default/files-efs/pubfiles/25509/Mauskapf_productfeatures.pdf)

## B10 — HIGH: Vocal-range medians are not male tessitura

The 10 arrangement ranges include Dark Horse and Let It Go. E3 and C-sharp5 are separately pooled endpoint medians of all 10. Neither is a measured sustained register, male-only estimate, or a range occurring in a representative singer.

**Required interpretation:** Remove male-lead/tessitura inference; retain explicitly arrangement-level endpoint/span descriptives. Nitin fit remains null.

## B11 — MEDIUM: Meter/pulse alternatives are collapsed

G013 source quote explicitly permits 12/8 or 4/4 with triplets. merge_batch_g00.py selects 4/4 first on any matching token, yielding 190 BPM plus plain 4/4. A 23/25 half/double alternative count reflects website text, not perceptual validation.

**Required interpretation:** Preserve beat unit and alternate notation; plain 4/4 is not disproved, but the uncertainty is lost. Generic half/double text is not independent evidence that each song has perceptually ambiguous pulse.

## B12 — MEDIUM: Secondary features lack recording/arrangement binding

Perfect records a fallback site with mismatched 3:45 duration/G major versus 4:23 album source. Sheet music, Wikipedia duration and third-party feature pages are combined by title. Some third-party sites mirror the same upstream feature source.

**Required interpretation:** Treat third-party corroboration as dependent and version-sensitive. Validate ISRC/version/audio identity before using song-level numeric features as recording targets; arrangement range cannot substitute for audio measurement.

## B13 — MEDIUM: Key disagreement statistic actually counts mode disagreement

merge_batch_g00.py conflict flag tests wiki_mode != site_mode, restricted to major/minor. It never compares tonic. Thus 7/14 is not a complete key-disagreement rate; modal comparisons are excluded.

**Required interpretation:** Label it mode disagreement in the eligible binary-mode subset; do not infer overall key accuracy or relative-major/minor agreement without tonic-aware comparison.

## B14 — HIGH: Success scoring risks unsupported normative penalties

Design lists chorus >60 sec, duration >4:00, key change and high typicality as risks, although report says relevant era trends do not distinguish winners and provides no calibrated combined predictor. Five retention curves are an arbitrary sufficiency threshold.

**Required interpretation:** Use a descriptive evidence checklist only. Do not turn these into success penalties, predicted retention or ranking weights until prospectively validated within a defined market and outcome.

## B15 — MEDIUM: Zone confidence and support counts are not membership counts

Z5 says independent Hindi singer-songwriter and 100+ days at #1, yet its support is all 17 peak-#1 SI rows and six long-#1 rows, including film songs outside that archetype. Language/film data are null for many examples. Z6 combines WI regional examples with BI #1 longevity from different songs.

**Required interpretation:** Attach row-level membership/evidence for each property; mixed-source support cannot certify a coherent musical zone. Keep genre/emotion and independence claims unresolved where unmeasured.

## Verification limits

L18 and L05 official/author PDFs were read. L24 was checked against indexed primary-article passages hosted by USC; direct PDF opening failed. No audio, paid research, browser UI, other track, or production action was used. All literature entries and success counts were not exhaustively reverified. Full raw-file hashes observed during this audit are in the JSON.
