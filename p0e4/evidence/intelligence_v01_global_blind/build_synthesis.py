"""Post-freeze synthesis. Raw provider files are inputs only; no production writes."""
from pathlib import Path
from datetime import datetime, timezone
import json, csv, hashlib, statistics

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'SYNTHESIS'
OUT.mkdir(exist_ok=True)
def read(p): return json.loads((ROOT / p).read_text())
def save(name, obj): (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
gate = read('THREE_TRACK_FREEZE_GATE.json')
assert gate['synthesis_allowed']
B = read('CLAUDE_B/provider_artifacts/track_b/data/RAW_DATASET.json')['rows']
C = read('CHATGPT_C/RAW_DATASET.json')['songs']
CD = read('CHATGPT_C/RAW_DATASET.json')
CS = {s['source_id']:s for s in read('CHATGPT_C/SOURCES_PROVENANCE.json')}
BA = read('CLAUDE_B/provider_artifacts/track_b/data/ANALYSIS_RESULTS.json')
CA = read('CHATGPT_C/COMPUTED_SUMMARY.json')
now = datetime.now(timezone.utc).isoformat()

# A reference registry, not a pooled statistical sample. Track namespace is preserved.
refs = {}
pitch_classes={'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'Fb':4,'F':5,'E#':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11,'Cb':11}
def pc(key):
    if not key: return None
    return pitch_classes.get(key.replace('♯','#').replace('♭','b').split('/')[0].strip())
for r in B:
    if r.get('bpm') is None: continue
    ident = 'B_' + r['id']
    # Preserve modal and tonic differences which B's binary-mode flag omitted.
    comparable=all(r.get(k) is not None for k in ['key','mode','key_site_spotify_derived','mode_site_spotify_derived'])
    conflict = bool(comparable and (pc(r['key']) != pc(r['key_site_spotify_derived']) or r['mode'].lower()!=r['mode_site_spotify_derived'].lower()))
    views, age = r.get('success_yt_views_K4_exact'), r.get('upload_age_days_at_obs')
    refs[ident] = {
        'reference_id': ident, 'title': r['title'], 'artist': r['artist_as_listed'],
        'track': 'CLAUDE_B', 'raw_row_id': r['id'], 'cohort': r['cohort'],
        'reported_bpm': r['bpm'], 'reported_key': r.get('key'), 'reported_mode': r.get('mode'),
        'reported_duration_seconds': r.get('song_duration_sec'),
        'canonical_recording_key': None, 'canonical_recording_bpm': None,
        'feature_status': 'secondary_report_not_audio_verified',
        'key_mode_disagreement': conflict,
        'disagreement_flag_scope': 'Coordinator comparison of reported tonic pitch class and mode against preserved site labels; scope/version differences are not resolved.',
        'provider_binary_mode_disagreement_flag': bool(r.get('key_mode_conflict_site_vs_sheet')),
        'alternate_key': r.get('key_site_spotify_derived') if conflict else None,
        'alternate_mode': r.get('mode_site_spotify_derived') if conflict else None,
        'tempo_or_version_caveat': r.get('bpm_alt'),
        'reported_range': r.get('vocal_range_measured'),
        'range_kind': 'published_arrangement_not_measured_recording' if r.get('vocal_range_measured') else None,
        'measured_recording_range': None, 'tessitura': None,
        'feature_sources': r.get('feature_provenance_urls','').split(';'),
        'success_sources': r.get('success_sources'),
        'reported_youtube_views': views,
        'youtube_counter_as_of': None, 'youtube_official_upload_id': None,
        'official_status': 'ascribed_by_source_list_not_directly_channel_verified',
        'reported_upload_age_days': age,
        'descriptive_views_per_day_approx': round(views/age) if views and age else None,
        'normalization_status': 'approximate_counter_timestamp_unknown_not_launch_velocity',
        'source_row_path': '../CLAUDE_B/provider_artifacts/track_b/data/RAW_DATASET.json',
        'confidence': 'low_to_medium_metadata; low_transfer',
    }
for r in C:
    f = r['musical_features']
    if f['key'] is None: continue
    ident = r['song_id']
    refs[ident] = {
        'reference_id': ident, 'title': r['title'], 'artist': r['artist'], 'track': 'CHATGPT_C',
        'raw_row_id': ident, 'cohorts': sorted({o['cohort'] for o in CD['observations'] if o['song_id']==ident}),
        'success_observations': [o for o in CD['observations'] if o['song_id']==ident],
        'reported_bpm': f['bpm'], 'reported_key': f['key'], 'reported_mode': f['mode'],
        'reported_duration_seconds': f['duration_seconds'],
        'canonical_recording_key': None, 'canonical_recording_bpm': None,
        'feature_status': 'secondary_report_not_audio_verified',
        'key_mode_disagreement': False, 'alternate_key': None, 'alternate_mode': None,
        'tempo_or_version_caveat': 'BPM unresolved across sources' if f['bpm'] is None else 'Verify beat unit and exact master before session.',
        'scoped_feature_alternatives': [{**a,'source_urls':{v['source_id']:CS[v['source_id']]['url'] for v in a['reports']}} for a in CD['conflicts'] if a['song']==r['title']],
        'reported_range': None, 'measured_recording_range': None, 'tessitura': None,
        'feature_sources': sorted({v['url'] for v in r['feature_provenance'].values()}),
        'feature_provenance': r['feature_provenance'],
        'success_sources': '../CHATGPT_C/SUCCESS_OBSERVATIONS.csv',
        'reported_youtube_views': None, 'descriptive_views_per_day_approx': None,
        'normalization_status': 'annual_source_window_not_release_age_adjustment',
        'source_row_path': '../CHATGPT_C/RAW_DATASET.json',
        'confidence': 'low_to_medium_metadata; low_transfer',
    }
save('REFERENCE_REGISTRY_V01.json', {'purpose':'Provenance-preserving reference metadata; not a merged inferential sample', 'references':list(refs.values())})

# Counts below concern selected examples fitting reported fields, not all songs in a population.
def zone(i, name, band, mode, ids, hindi_listen, target, principle, test, caveat=''):
    rows = [refs[x] for x in ids]
    ys = [r['descriptive_views_per_day_approx'] for r in rows if r.get('descriptive_views_per_day_approx')]
    return {
        'zone_id':f'Z{i:02d}', 'rank':None, 'name':name, 'kind':'editorial_audition_zone_not_performance_ranking',
        'proposed_bpm_range':band, 'proposed_mode':mode, 'recommended_absolute_key':None,
        'reference_ids':ids, 'supporting_examples_n':len(ids),
        'examples_with_reported_key_conflict_n':sum(r['key_mode_disagreement'] for r in rows),
        'independent_tests_of_zone_effect_n':0, 'supporting_count_definition':'Selected source-reported examples; not trials, not independent datasets, and examples may recur in other zones.',
        'hindi_listening_candidates_without_zone_membership_claim':hindi_listen,
        'emotional_use_case':target, 'production_and_hook_experiment':principle,
        'production_description_kind':'Coordinator proposal to audition, not measured property of every reference',
        'vocal_implications_and_test':test,
        'performance_characteristics':{'signal':'Successful-list presence in source cohorts, not evidence of a zone advantage', 'approx_global_youtube_views_per_day_n':len(ys), 'approx_global_youtube_views_per_day_median':round(statistics.median(ys)) if ys else None, 'normalization_limit':'B counters lack exact as-of; lifetime-average only. Do not compare this median across zones/markets as treatment effect.', 'retention':None, 'replay_rate':None},
        'evidence_strength':'Low for musical transfer; no estimated performance association',
        'suitable_for_original_reference':'yes_as_audition_hypothesis_only',
        'caveat':caveat,
        'study_only':'Abstract groove, section contrast, density, repetition with variation; write original melody, lyrics and riffs. No sample or expressive passage clearance is implied.',
    }
zones = [
zone(1,'Intimate minor ballad',[72,82],'minor',['C_pehle-bhi-main'],['Agar Tum Saath Ho','Tujhe Kitna Chahne Lage','Baarishein'],'Heartbreak / private confession','Try a spacious original verse and a clearer, wider refrain; hold accompaniment back until the emotional pivot.','Audition the sustained chorus phrase in a comfortable key, then one semitone lower/higher only if comfortable. Prioritize phrase-end stability.','Pehle Bhi Main is reported at 77; arrangement pulse conflicts remain. Extra Hindi titles are success/listening references, with mode/BPM null.'),
zone(2,'Gentle major ballad',[75,85],'major',['B_G002','B_G015','B_G017','C_sajni'],['Tum Se Hi','Saibo'],'Tenderness / longing','Test sparse accompaniment, audible consonants and a contrasting final refrain without adding vocal height.','Compare repeated verse-to-chorus takes; keep the quiet low notes audible without forcing high phrases.'),
zone(3,'Minor romantic groove',[88,100],'minor',['B_G001','B_G003','B_G018','B_G019','C_maan-meri-jaan'],['Jo Tum Mere Ho','Husn'],'Romance with rhythmic movement','Write a new concise title motif over a stable bass/percussion pattern; compare literal hook return with one small rhythmic variation.','Test rhythmic diction at 92 and 96 BPM in the same comfortable key; then test key separately.','Despacito and Faded have key/mode conflicts. Do not claim all listed melodies share a mode from database consensus.'),
zone(4,'Major midtempo romance',[90,100],'major',['B_G020','B_G021','C_kesariya'],['Dil Diyan Gallan','Tera Hone Laga Hoon'],'Warm / open romantic address','Compare a stripped verse with a harmonically fuller refrain; study spacing and new instrumental answers, not existing signature riffs.','Choose a key where the chorus can be repeated at performance intensity with clear vowels.'),
zone(5,'Conversational bright pop',[100,110],'major',['B_G007','B_G014','C_espresso'],['Chaleya','Bom Diggy Diggy'],'Playful / danceable','Test conversational rhythmic phrasing and a brief new instrumental hook between vocal phrases. Novelty/video references are weak transfer evidence.','Use groove and articulation for lift; do not force the original singer’s register.','Sorry is reported as major by the arrangement quotation and minor by a database. Hindi candidates have unverified musical fields; A Chaleya values are excluded.'),
zone(6,'Percussive minor crossover sketch',[100,110],'minor',['B_G025'],['Chaleya','Maan Meri Jaan'],'Celebratory / rhythm-led','Try a new syncopated percussion identity under Hindi lyrics; compare an all-Hindi refrain and a naturally written bilingual alternative.','Test fast syllables and breath placement before increasing tempo.','Mi Gente is a global example, not evidence of Hindi crossover. Maan Meri Jaan is reported at 96 BPM in Track C and is outside this zone; listed only for language/phrase study.'),
zone(7,'Modal funk contrast',[110,120],'dorian_candidate',['B_G006'],['Kala Chashma','High Rated Gabru'],'Confident / live-band','Audition call-and-response between an original vocal phrase and rhythm section; contrast dense refrains with short rests.','Create a narrow original response phrase; disregard the reference arrangement’s extreme ad-lib range.','Uptown Funk D Dorian is a reported analysis, not a target tonic or a reason to require Dorian in an original.'),
zone(8,'Driving minor anthem',[118,135],'minor',['B_G009','B_G005','B_G012'],['Kala Chashma','Lehanga'],'Urgent / energetic','Compare a constant pulse with a deliberately planned lift; introduce a new instrumental motif that returns in changed texture.','Test chorus breath demand and repeated high-duration notes at moderate intensity before adding production density.','Counting Stars includes a reported tempo change; Dark Horse has a key conflict. Genre/visual spectacle confound commercial performance.'),
zone(9,'Slow major narrative',[65,74],'major',['C_luther'],['Sajni','Kabira'],'Reflective / restrained','Let a memorable original phrase arrive before the formal chorus; compare an earlier and later refrain in private demos.','Keep sustained phrases centered in Nitin’s comfortable tessitura; compare breath and diction over long gaps.','luther has a reported first chorus at 1:09. That is an observed structural example, not evidence for improved retention. Sajni is 80 and outside this zone.'),
zone(10,'Compound-feel romantic arrangement',None,'major_candidate',['B_G013'],['Dil Diyan Gallan','Tujhe Kitna Chahne Lage'],'Swaying / intimate to expansive','Test a compound subdivision against a straight version of an original phrase, recording beat unit explicitly; judge the feel before selecting a metronome number.','Check phrase duration and vowel sustain; audition complete phrase arcs, not a single top note.','Perfect carries incompatible version metadata and 95/190-style tempo descriptions plus 12/8 or 4/4-triplet notation. No canonical tempo/meter is accepted without beat-unit validation.'),
]
save('TOP_REFERENCE_ZONES_V01.json', {'ranking_supported':False,'zone_count':10,'note':'Ten practical experiment directions, not ten empirically best combinations. Extra Hindi songs are listening candidates, never counted as musical support. No zone has demonstrated causal or adjusted performance effect.','zones':zones})

matrix = [
('Absolute key predicts success','A initially implied a privileged C# key; not established','24 reported keys in 168 rows; several arrangement/database conflicts','7 reported keys in 42 entities; no controls','REJECT','No defensible winning key. Transpose for the voice.'),
('Winning tempo pocket','A asserted 94–96; broad claim retracted','25 global feature rows; median 110, heterogeneous beat units','6 BPM values in 42; sparse recent coverage','NOT_IDENTIFIED','No age/artist-adjusted BPM effect; zone ranges are proposals.'),
('Shorter/earlier always improves retention','A 200-second algorithmic claim retracted','Historical duration/intro trends; unsupported deadlines in zones','2025 US examples include later chorus arrivals','REJECT_UNIVERSAL_RULE','No private retention. Structure has several workable forms.'),
('Major versus minor','Tiny unverified A list','14 major,8 minor,2 modal,1 unknown in selected global feature cell','Reported Hindi examples include both labels','DESCRIPTIVE_ONLY','Era, market, source and selection differ; no preferred mode inferred.'),
('Indian crossover exists','No adequate defined export cohort','0 intersection in selected all-time top lists','8 named Indian export/diaspora examples','DEFINITION_DIFFERENCE','Top-list absence does not imply no export. Export does not prove broad non-diaspora adoption.'),
('Repeatability/replay','No observed repeat-listener data','Chart longevity and repetition literature','Annual recurrence/export presence','PROXY_ONLY','Population persistence is not individual replay rate.'),
('Age normalization','No valid timestamped official counter join','Approximate lifetime views/day for dated rows, undated counters','Annual outcome windows, not release-age normalization','PARTIAL','No validated launch-window comparison or regression across tracks.'),
('Vocal selection','Unsafe breaking-point idea retracted','Arrangement ranges and proposed hard constraints','Comfortable phrase-based audition; no observed Nitin range','VOICE_FIRST_REQUIREMENT','Prompt agreement is not independent scientific evidence; no numerical Nitin fit.'),
('Production and structure','Sparse unsourced production generalizations','No measured per-song hook/chorus timing; aggregate literature','One report-based chorus boundary; most fields missing','HYPOTHESIS_WORKBENCH','Annotate exact recordings before claiming reference structure as measured.'),
]
save('CROSS_VALIDATION_MATRIX_V01.json',{'created_at':now,'freeze_gate':'../THREE_TRACK_FREEZE_GATE.json','independent_agent_outputs_not_independent_source_studies':True,'rows':[dict(zip(['question','GEMINI_A','CLAUDE_B','CHATGPT_C','decision','accepted_statement'],r)) for r in matrix]})

consensus = {
 'version':'V01','created_at':now,
 'accepted_bounded_findings':['Exceptional songs occupy diverse reported tempos, modes and durations; available hit-only data cannot identify an optimum.','B provides a broader historical success registry; C provides recent annual/global and export coverage. They answer different sampling questions.','Published musical metadata must be bound to a recording version and beat unit before production use.','Private watch time, retention, unique-listener replay, Nitin vocal fit and own-data outcomes are absent.'],
 'prompt_constraints_not_empirical_consensus':['Association is not causation','Voice-first key selection','No hit probability','No production or publication authorization'],
 'disagreements':[r[-1] for r in matrix if r[4] in ['DEFINITION_DIFFERENCE','REJECT','REJECT_UNIVERSAL_RULE']],
 'excluded_from_accepted_quantitative_evidence':['All GEMINI_A initial key/BPM/view claims and purported measured addendum BPM','Claude universal chorus/intro deadlines and generic risk penalties','Claude inferred modern Indian major/minor balance','Claude pooled arrangement range as a typical male vocal target'],
 'source_dependency':'Spotify-derived mirrors may share upstream data; cross-model repetition of a source is one source, not independent replication.',
 'sample_sizes':'A 4 initial rows; B 168 mixed-unit rows; C 42 entities/49 observations. Do not sum these into a unique recordings n.',
 'status':'BOUNDED_SYNTHESIS_WITH_EXPLICIT_GAPS',
}
save('CONSENSUS_AND_DISAGREEMENT_V01.json',consensus)

optimizer = {
 'name':'VOCAL_KEY_OPTIMIZER','version':'V01','status':'DESIGN_ONLY_UNCALIBRATED',
 'current_nitin_measurements':None,'NITIN_FIT_SCORE':None,
 'required_inputs':{'melody':'Original melody note events: MIDI pitch, onset, duration, lyric vowel, section, register intention','voice':'Consented comfortable phrase takes, sustained tessitura, register behavior, effort, diction and repeatability','reference':'Version-bound tonic/mode, interval contour envelope and beat unit; not copied protected melody'},
 'algorithm':['Select a comfortable baseline key with Nitin and Vatsal.','Enumerate integer semitone shifts only within demonstrated comfortable limits. For every note, new_midi = original_midi + shift; tonic = (original_tonic + shift) mod 12.','Preserve intervals and mode under uniform transposition. Calculate duration-weighted pitch distribution by verse/chorus/climax, not merely min/max.','Check sustained demands, phrase endings, register transitions, vowel clarity, breath and repeated performance; range endpoints alone do not determine fit.','Audition a small number of nearby keys at comparable gain and tempo with rests; stop an uncomfortable take. Repeat the favored key on another occasion.','Select creative fit by listening with Nitin; instrument tone and arrangement may need adaptation after transposition.'],
 'prohibited_shortcuts':['No population hit key as Nitin target','No max-note/breaking-point test','No fixed safe semitone offset for all voices','No universal 2–5-semitone chorus-rise rule','No numerical fit without observations and an explicitly defined scoring protocol'],
 'outputs':{'candidate_keys':[],'recommended_key':None,'transposition_semitones':None,'NITIN_FIT_SCORE':None,'reason':'No Nitin audition measurements supplied'},
 'pitch_invariants':['Equal semitone shift preserves all pairwise intervals','Enharmonic spelling handled separately','Octave rewrites and mode changes require separate arrangement decisions'],
 'event_fields':['audition_id','song_id','recording_version_id','take_asset_sha256','key','shift_semitones','phrase_id','pitch_events','comfortable','effort_self_report','diction_review','tone_review','repeatability_review','observed_at','evidence_id'],
}
save('VOCAL_KEY_OPTIMIZER_V01.json',optimizer)

engine = {
 'name':'SONG_SUCCESS_INTELLIGENCE_ENGINE','version':'V01','status':'DESIGN_ONLY_NOT_DEPLOYED',
 'cohorts':['GLOBAL_SUCCESS','HINDI_INDIAN_SUCCESS','GLOBAL_HINDI_CROSSOVER','UNCHAINED_NITIN_OWN_DATA'],
 'required_input_fields':['key','mode','bpm','song_duration','emotion','energy','vocal_range','hook_characteristics','release_type','target_platform'],
 'additional_inputs':['recording_version_id','beat_unit','perceived_pulse','tempo_segments','time_signature','intro_duration','first_vocal_time','first_hook_time','first_chorus_time','hook_repetitions','section_boundaries','melodic_contour','tessitura','climax_time','arrangement_annotations','release_date','upload_date','market','language','artist_prior_popularity_window','film_status','promotion_exposure'],
 'field_record':{'value':None,'unit':None,'kind':'measured|secondary_estimate|interpretation|hypothesis|unknown','source_url':None,'source_id':None,'evidence_id':None,'observed_at':None,'recording_version_id':None,'method':None,'confidence':None,'missing_reason':None},
 'outputs':{
  'SUCCESS_SIGNAL_SCORE':{'value':None,'meaning':'Optional retrospective outcome percentile within a predeclared platform/market/age-window cohort; never predicted success from key/BPM.','requirements':['Observed outcomes, defined denominator and window','Direction and scaling documented','No mixing revenue, streams and views without an explicit utility model']},
  'EVIDENCE_CONFIDENCE':{'value':'INSUFFICIENT_FOR_PREDICTION','dimensions':['source_quality','version_binding','field_coverage','source_independence','measurement_agreement','market_transfer','bias_risk']},
  'REFERENCE_MATCH_SCORE':{'value':None,'meaning':'Descriptive feature similarity, not success likelihood','method':'Compare only jointly observed compatible features; report weights, distance, coverage and exclusions. Reject incompatible beat units/version mixtures. Never fill missing values with zero.'},
  'NITIN_FIT_SCORE':{'value':None,'depends_on':'VOCAL_KEY_OPTIMIZER_V01'},
  'EXPECTED_RETENTION_PROFILE':{'value':None,'reason':'No observed own retention curves or calibrated held-out model','future_requirement':'Versioned model with declared training n, uncertainty, calibration and temporal/artist leakage checks; no arbitrary five-curve activation threshold'},
  'RISKS':['Sparse and nonrandom musical metadata','Unresolved recording identity','Artist/exposure confounding','Mixed date windows','Tempo beat-unit ambiguity','Unmeasured vocal demands'],
  'COMPARABLE_SONGS':{'registry':'REFERENCE_REGISTRY_V01.json','selection':'Return source-linked matches with explicit limitations; no deterministic rank of likely hits'},
 },
 'score_policy':'No score emitted from musical criteria alone. No automatic penalty for chorus after 60s, long duration, minor/major choice or key changes.',
 'ten_million_architecture_binding':{
  'authority':'../ARCHITECTURE_BINDING_REVIEW.json','scope':'Additive research sidecar only; existing schema unchanged',
  'music_parameter_version':'Attach through CONTENT_MASTER.song_id and content_id with evidence_ids',
  'experiment':'DERIVATIVES.derivative_id, hypothesis_id, experiment_id, content_id',
  'distribution':'PUBLICATION -> PLATFORM_PACKAGES -> DERIVATIVES -> CONTENT_MASTER -> CAMPAIGNS',
  'metrics':'Link timestamped platform-post observations through publication_id/platform_post_id; preserve metric unit, window, denominator, source and availability',
  'business':'BUSINESS_FUNNEL and MONETIZATION through publication_id/funnel_id using the canonical contract; preserve lead_id/booking_id/attribution_method/code',
  'unknown_attribution':None,'causal_claim':'An attribution join is not proof that a musical feature caused a booking or revenue.',
  'goal_not_result':'10M is architectural context, not an achieved reach claim',
 },
 'future_study':['Prospectively include modest performers and failures; select releases before seeing outcomes.','Bind master, language version, remix, video and audio uploads; cluster related recordings and repeated artists.','Use matched exposure windows (e.g. first 7/28 days), market and platform; separately report recent velocity and lifetime accumulation.','Control artist prior success from a pre-release window, film context, era, duration and promotion where observed; do not use current popularity as prior popularity.','Use temporal holdout, artist grouping, prespecified hypotheses, multiple-comparison control and clustered uncertainty where inferential assumptions hold.','Join song to derivative and packaging decisions; performance of a short-form edit is not automatically performance of the master.'],
 'governance':{'PRODUCTION_DEPLOYMENT_AUTHORIZED':False,'PUBLICATION_AUTHORIZED':False,'FIRST_REAL_POSTER':'PAUSED_BY_NITIN','writes_to_operational_state':False},
}
save('SONG_SUCCESS_INTELLIGENCE_ENGINE_V01.json',engine)

annotation = {
 'status':'PROTOCOL_NOT_EXECUTED','unit':'exact recording/version and exact upload; audio and video timelines separate',
 'fields':{
  'intro_duration':'First substantive lead-vocal onset minus audio start; log opening adlibs separately.',
  'first_vocal_time':'Earliest human vocal sound; distinguish lyric-bearing lead, sample, adlib and backing vocal.',
  'first_hook_time':'First agreed salient recurring motif (vocal/instrumental); do not define automatically as chorus.',
  'first_chorus_time':'Section boundary by two annotators; for mukhda/antara or non-chorus forms retain original labels and null chorus if inappropriate.',
  'hook_repetitions':'Complete motif occurrences with timestamp spans; partial variants separately.',
  'tempo':'Meter plus beat unit, perceptual pulse and segment boundaries; math half/double alternatives are not evidence of listening ambiguity.',
  'key_mode':'Tonic evidence, pitch collection, harmony and melodic behavior; major/minor is not automatically a raga label.',
  'emotion_energy_groove':'Keep subjective labels, acoustic measurement and platform scores separate with their respective units.',
  'vocal_range_tessitura':'Measured lead-vocal notes with confidence and duration-weighted register occupancy; exclude or separately tag backing vocals and adlibs.',
  'climax':'Timestamp and criterion (intensity, texture, pitch, lyric); do not equate highest pitch with climax automatically.',
  'duration':'Exact version length; exclude pre-roll credits only under a recorded rule.'},
 'quality':'Disagreement adjudicated with evidence and inter-rater agreement; no invented timestamps for unplayed songs.',
}
save('STRUCTURAL_ANNOTATION_PROTOCOL_V01.json',annotation)

index={'created_at':now,'freeze_gate':gate,'outputs':{
 'GEMINI_INDEPENDENT_REPORT_V01':'../GEMINI_A/RAW_REPORT.md',
 'GEMINI_CORRECTION_ADDENDUM':'../GEMINI_A/ADDENDUM.md',
 'CLAUDE_INDEPENDENT_REPORT_V01':'../CLAUDE_B/provider_artifacts/track_b/REPORT_CLAUDE_B_FROZEN_V01.md',
 'CHATGPT_INDEPENDENT_REPORT_V01':'../CHATGPT_C/REPORT.md',
 'CROSS_VALIDATION_MATRIX_V01':'CROSS_VALIDATION_MATRIX_V01.json',
 'CONSENSUS_AND_DISAGREEMENT_V01':'CONSENSUS_AND_DISAGREEMENT_V01.json',
 'SONG_SUCCESS_INTELLIGENCE_V01':'SONG_SUCCESS_INTELLIGENCE_V01.md',
 'VOCAL_KEY_OPTIMIZER_V01':'VOCAL_KEY_OPTIMIZER_V01.json',
 'VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01':'VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01.md'},
 'raw_track_packages':{'GEMINI_A':'../GEMINI_A/','CLAUDE_B':'../CLAUDE_B/','CHATGPT_C':'../CHATGPT_C/'},
 'limitations':'Three independent dispatches with disclosed prior context; source independence and claim quality are assessed separately. A is inadequate for quantitative inference. B/C freeze integrity and code replay verified.'}
save('DELIVERY_INDEX_V01.json',index)

table = '| Zone (unordered) | Reported reference key/mode and BPM | Supporting examples | Proposed use / production study |\n|---|---|---:|---|\n'
for z in zones:
    names=[]
    for rid in z['reference_ids']:
        r=refs[rid]; star='†' if r['key_mode_disagreement'] else ''
        names.append(f"{r['title']}: {r['reported_key']} {r['reported_mode']}, {r['reported_bpm'] or 'unresolved'}{star}")
    table += f"| {z['zone_id']} {z['name']} | {'; '.join(names)} | {z['supporting_examples_n']} | {z['emotional_use_case']}; {z['production_and_hook_experiment']} |\n"
brief = '''# VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01

Use these ten **unordered audition directions**, not ten proven hit formulas. The evidence is strongest for which recordings performed well and much weaker for why. No Nitin key, vocal fit, expected retention or hit probability is known. Source metadata is a starting point for listening, not a production prescription.

Every tempo/key below is reported by a secondary source, not measured by us from the master. † means a material key/mode disagreement; preserve alternatives in REFERENCE_REGISTRY_V01.json and verify the recording before using the label. Perfect additionally has unresolved version/beat-unit issues. Original keys are reference metadata only; select the original song key for Nitin's voice.

'''+table+'''
## How to use the references

The registry supplies per-song URLs, original reported key, duration, measurement status and source-row IDs. The global examples mostly come from an older YouTube success cohort, while the Hindi examples with musical metadata come from a small recent streaming/export sample. Do not add these counts or use the table order as a success ranking. A repeated example in two listening discussions is still one example.

Only four Hindi/Indian candidates have source-linked musical metadata in C: Pehle Bhi Main (77, A#/Bb minor), Maan Meri Jaan (96, F#/Gb minor), Kesariya (94, C major), Sajni (80, C major). These are still unverified against original audio. There is no evidence basis to supply three to five *verified musical matches* for every zone. The listening candidates below fill an audition queue, not a statistical evidence gap.

'''
for z in zones:
    brief+=f"### {z['zone_id']} — {z['name']}\n\n"
    brief+=f"**Voice test:** {z['vocal_implications_and_test']}\n\n"
    brief+=f"**Additional Hindi listening:** {', '.join(z['hindi_listening_candidates_without_zone_membership_claim'])}. Their inclusion does not assert zone membership, key, tempo or measured structure.\n\n"
    brief+=f"**Evidence:** {z['evidence_strength']}. {z['caveat']}\n\n"
brief+='''## First production session

1. Start with Z01, Z02 and Z03 as a manageable editorial shortlist, not a performance prediction. Nitin and Vatsal may choose differently after listening.
2. Bind each selected reference to the intended official recording; tap and label the beat unit, verify the tonic/mode, and timestamp first vocal, hook, refrain and climax using STRUCTURAL_ANNOTATION_PROTOCOL_V01.json.
3. Write an original verse, hook and climax phrase. Study arrangement density, pauses and repetition-with-variation. Do not reproduce a reference melody, lyric, signature riff, sample or identifiable expressive passage.
4. Find Nitin's comfortable baseline key. Record the chorus and climax there; compare nearby semitone transpositions only within comfort. Keep tempo and gain comparable; note phrase-end pitch, vowels, register transitions, effort and repeatability. Stop an uncomfortable take. Revisit the favored key later.
5. After choosing the vocal key, test one structural question at a time: earlier vs later refrain, sparse vs full first hook, or compact vs extended arrangement. These are private demos; release testing requires separate authorization.
6. Store take hashes, decisions, annotation disagreements and experiment IDs. Do not award a SUCCESS_SIGNAL_SCORE for sounding like a hit. Outcomes must be observed and joined through the existing attribution chain.

No exact intro, hook, climax percentage or duration is prescribed as universally superior. The useful principle is to make a clear musical promise, develop it and test whether the intended audience responds. That remains a hypothesis until audience data exists.
'''
(OUT/'VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01.md').write_text('\n'.join(line.rstrip() for line in brief.splitlines()) + '\n')
save('VATSAL_ORIGINAL_PRODUCTION_REFERENCE_BRIEF_V01.json',{'version':'V01','zones':zones,'vocal_optimizer':'VOCAL_KEY_OPTIMIZER_V01.json','metadata':'REFERENCE_REGISTRY_V01.json','scope':'Private original-production planning only; no production system mutation or publication','copy_policy':'Abstract structure and production principles only; original melody/lyrics/riffs required; no rights clearance implied'})

save('SONG_SUCCESS_INTELLIGENCE_V01.json',{'version':'V01','status':'BOUNDED_RESEARCH_COMPLETE_NO_PREDICTIVE_MODEL','created_at':now,'consensus':consensus,'cross_validation':'CROSS_VALIDATION_MATRIX_V01.json','track_counts':{'A_initial_rows':4,'B_mixed_unit_rows':168,'C_song_entities':42,'C_success_observations':49},'unique_recordings_total':None,'pooled_analysis_performed':False,'top_zones':zones,'engine':'SONG_SUCCESS_INTELLIGENCE_ENGINE_V01.json','vocal_optimizer':'VOCAL_KEY_OPTIMIZER_V01.json','structural_annotation':'STRUCTURAL_ANNOTATION_PROTOCOL_V01.json','watch_hours':None,'retention':None,'individual_replay':None,'NITIN_FIT_SCORE':None})

matrix_md = '# CROSS_VALIDATION_MATRIX_V01\n\nComparison began only after THREE_TRACK_FREEZE_GATE.json passed. Model agreement is not source replication.\n\n| Question | Gemini A | Claude B | ChatGPT C | Decision | Accepted statement |\n|---|---|---|---|---|---|\n'
for row in matrix: matrix_md += '| ' + ' | '.join(row) + ' |\n'
(OUT/'CROSS_VALIDATION_MATRIX_V01.md').write_text(matrix_md)
consensus_md = '# CONSENSUS_AND_DISAGREEMENT_V01\n\n'
for label, field in [('Accepted bounded findings','accepted_bounded_findings'),('Instructions shared by all tracks; not empirical consensus','prompt_constraints_not_empirical_consensus'),('Disagreements and rejected claims','disagreements'),('Excluded quantitative/prescriptive claims','excluded_from_accepted_quantitative_evidence')]:
    consensus_md += '## ' + label + '\n\n' + '\n'.join('- '+x for x in consensus[field]) + '\n\n'
consensus_md += consensus['source_dependency']+'\n\n'+consensus['sample_sizes']+'\n'
(OUT/'CONSENSUS_AND_DISAGREEMENT_V01.md').write_text(consensus_md)
print(json.dumps({'created_at':now,'reference_registry_n':len(refs),'editorial_zones_n':len(zones),'freeze_gate_passed':True}))
