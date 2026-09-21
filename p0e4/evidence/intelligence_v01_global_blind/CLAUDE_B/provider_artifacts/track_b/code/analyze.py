#!/usr/bin/env python3
"""CLAUDE_B analyze.py — descriptive computation only. Reads RAW_DATASET.json, writes ANALYSIS_RESULTS.json.
Frequency != association != causation. All cohorts are hit-only (no control group), so nothing here identifies effects."""
import json, os, statistics as st
from collections import Counter
D = os.path.join(os.path.dirname(__file__), "..", "data")
ds = json.load(open(os.path.join(D,"RAW_DATASET.json"),encoding="utf-8"))
rows = ds["rows"]
def q(vals):
    v = sorted(x for x in vals if x is not None)
    if not v: return {"n":0}
    def pct(p):
        k=(len(v)-1)*p; f=int(k); c=min(f+1,len(v)-1); return v[f]+(v[c]-v[f])*(k-f)
    return {"n":len(v),"min":v[0],"p25":round(pct(.25),3),"median":round(st.median(v),3),"p75":round(pct(.75),3),"max":v[-1],"mean":round(st.mean(v),3)}
def share(cnt):
    n=sum(cnt.values()); return {k:{"n":c,"share":round(c/n,3)} for k,c in sorted(cnt.items(), key=lambda x:-x[1])} if n else {}

R = {"track":"CLAUDE_B","version":"FROZEN_V01","observed":"2026-09-22","n_rows_total":len(rows)}
G=[r for r in rows if r["cohort"]=="GLOBAL_SUCCESS"]; H=[r for r in rows if r["cohort"]=="HINDI_INDIAN_SUCCESS"]
R["cohort_n"]={"GLOBAL_SUCCESS":len(G),"HINDI_INDIAN_SUCCESS":len(H),"GLOBAL_HINDI_CROSSOVER":0,"UNCHAINED_NITIN_OWN_DATA":0}

# ---- missingness of musical feature fields
feat=["bpm","key","mode","song_duration_sec","energy","intro_length_sec","first_vocal_sec","first_hook_sec","chorus_arrival_sec","hook_repetitions","structure","vocal_range_measured","tessitura","climax_placement","meter"]
R["feature_missingness"]={f:{"n_present":sum(1 for r in rows if r.get(f) is not None),"n_null":sum(1 for r in rows if r.get(f) is None)} for f in feat}

# ---- GLOBAL success signals
gyt=[r for r in G if r.get("success_yt_views_K4_exact")]
gsp=[r for r in G if r.get("success_spotify_streams_S2_bn")]
gb3=[r for r in G if r.get("success_hot100_weeks_at_1_B3")]
R["global"]={
 "source_cells":{"youtube_K4":len(gyt),"spotify_S2":len(gsp),"hot100_B3":len(gb3),
                 "youtube_and_spotify_overlap":sum(1 for r in G if r.get("success_yt_views_K4_exact") and r.get("success_spotify_streams_S2_bn")),
                 "youtube_and_hot100_overlap":sum(1 for r in G if r.get("success_yt_views_K4_exact") and r.get("success_hot100_weeks_at_1_B3")),
                 "spotify_and_hot100_overlap":sum(1 for r in G if r.get("success_spotify_streams_S2_bn") and r.get("success_hot100_weeks_at_1_B3"))},
 "youtube_views_exact_K4":q([r["success_yt_views_K4_exact"] for r in gyt]),
 "youtube_upload_year_W1":share(Counter(str(r["era_year"]) for r in gyt if r.get("official_upload_date"))),
 "youtube_upload_age_days":q([r["upload_age_days_at_obs"] for r in gyt if r.get("upload_age_days_at_obs")]),
 "youtube_descriptive_views_per_day_since_upload":q([round(r["success_yt_views_K4_exact"]/r["upload_age_days_at_obs"]) for r in gyt if r.get("upload_age_days_at_obs")]),
 "youtube_yesterday_views_K4":q([r["success_yt_yesterday_K4"] for r in gyt]),
 "spotify_streams_bn_S2":q([r["success_spotify_streams_S2_bn"] for r in gsp]),
 "spotify_release_decade_S2":share(Counter(str(r["release_date_S2"][:3])+"0s" for r in gsp)),
 "spotify_release_year_S2":q([int(r["release_date_S2"][:4]) for r in gsp]),
 "spotify_share_released_2012_or_later":round(sum(1 for r in gsp if int(r["release_date_S2"][:4])>=2012)/len(gsp),3),
 "hot100_weeks_at_1_B3":q([r["success_hot100_weeks_at_1_B3"] for r in gb3]),
 "notes":["views/day = exact K4 views / days between W1 upload date and 2026-09-22; K4 page undated so ratio is approximate; NOT watch time.",
          "Spotify top-40 is dominated by 2012-2022 releases with a catalog tail (1983, 1998, 2000, 2003, 2008) — a hit-only, survivorship-biased frame."]}

# ---- HINDI/INDIAN success signals
hyt=[r for r in H if r.get("success_yt_views_WI_bn") or r.get("success_yt_views_KI_exact")]
hsp=[r for r in H if r.get("success_spotify_in_chart_total_streams_SI")]
hbi=[r for r in H if r.get("success_india_songs_weeks_at_1_BI")]
def fs(r):
    v=r.get("film_status") or "null"; return "film" if v.startswith("film") else ("non-film" if v.startswith("non-film") else "null")
R["hindi_indian"]={
 "source_cells":{"youtube_WI_or_KI":len(hyt),"spotify_india_SI":len(hsp),"india_songs_BI":len(hbi),
                 "youtube_and_spotify_overlap":sum(1 for r in H if (r.get("success_yt_views_WI_bn") and r.get("success_spotify_in_chart_total_streams_SI"))),
                 "spotify_and_billboard_overlap":sum(1 for r in H if r.get("success_spotify_in_chart_total_streams_SI") and r.get("success_india_songs_weeks_at_1_BI"))},
 "youtube_language_WI":share(Counter(r.get("language") or "null" for r in hyt)),
 "youtube_film_status":share(Counter(fs(r) for r in hyt)),
 "youtube_film_status_hindi_only":share(Counter(fs(r) for r in hyt if r.get("language") and "Hindi" in r["language"])),
 "youtube_uploader_WI":share(Counter(r.get("uploader") or "null" for r in hyt)),
 "youtube_upload_year":share(Counter(str(r["era_year"]) for r in hyt if r.get("era_year"))),
 "youtube_views_WI_bn":q([r["success_yt_views_WI_bn"] for r in hyt if r.get("success_yt_views_WI_bn")]),
 "youtube_views_KI_exact":q([r["success_yt_views_KI_exact"] for r in hyt if r.get("success_yt_views_KI_exact")]),
 "youtube_upload_age_days":q([r["upload_age_days_at_obs"] for r in hyt if r.get("upload_age_days_at_obs")]),
 "youtube_descriptive_views_per_day_since_upload":q([round(r["success_yt_views_KI_exact"]/r["upload_age_days_at_obs"]) for r in hyt if r.get("upload_age_days_at_obs") and r.get("success_yt_views_KI_exact")]),
 "youtube_views_per_day_by_film_status":{k:q([round(r["success_yt_views_KI_exact"]/r["upload_age_days_at_obs"]) for r in hyt if fs(r)==k and r.get("upload_age_days_at_obs") and r.get("success_yt_views_KI_exact")]) for k in ("film","non-film")},
 "spotify_india_film_tag_in_title":share(Counter("film (From \"...\" tag)" if r.get("film_status")=="film" else "no film tag (non-film or untagged)" for r in hsp)),
 "spotify_india_chart_days":q([r["success_spotify_in_chart_days_SI"] for r in hsp]),
 "spotify_india_top10_days":q([r["success_spotify_in_top10_days_SI"] for r in hsp if r.get("success_spotify_in_top10_days_SI")]),
 "spotify_india_peak_position":share(Counter(str(r["success_spotify_in_peak_pos_SI"]) for r in hsp)),
 "spotify_india_peak_day_streams":q([r["success_spotify_in_peak_day_streams_SI"] for r in hsp]),
 "spotify_india_chart_total_streams":q([r["success_spotify_in_chart_total_streams_SI"] for r in hsp]),
 "spotify_india_avg_streams_per_chart_day":q([round(r["success_spotify_in_chart_total_streams_SI"]/r["success_spotify_in_chart_days_SI"]) for r in hsp]),
 "spotify_india_longevity_vs_peak":{"n_peak1_songs":sum(1 for r in hsp if r["success_spotify_in_peak_pos_SI"]==1),
    "chart_days_peak1":q([r["success_spotify_in_chart_days_SI"] for r in hsp if r["success_spotify_in_peak_pos_SI"]==1]),
    "chart_days_never_top3":q([r["success_spotify_in_chart_days_SI"] for r in hsp if r["success_spotify_in_peak_pos_SI"]>3]),
    "reading":"Two routes into the all-time chart-total top-40: (a) peak-1 songs with high daily streams over ~1-3 years, (b) songs that never peaked near #1 but stayed on the top-200 for 5-7 years (catalog longevity). Descriptive only."},
 "india_songs_2022_weeks_at_1":q([r["success_india_songs_weeks_at_1_BI"] for r in hbi]),
 "notes":["Hindi YouTube list is multi-language: Punjabi/Haryanvi/Tamil/Bhojpuri rows kept and labelled; Hindi-only cells reported separately.",
          "kworb Spotify India 'Total' counts only chart days since 2019-02-27; older catalog (e.g. 2007-2015 film songs) is under-counted relative to lifetime streams.",
          "Film status for YouTube rows is inferred from Wikipedia 'from <Film>' annotation; for Spotify rows from the '(From \"Film\")' title tag — untagged rows may still be film songs (e.g. Kesariya, Tum Se Hi, Kabira are film songs but carry no tag in the kworb title)."]}


# ---- GLOBAL per-song feature cell (batch G00 only: 25 rows, all YouTube-top-list songs, uploads 2009-2018)
F=[r for r in G if r.get("bpm") is not None]
def modecat(m):
    if m is None: return "null"
    return m if m in ("major","minor") else "modal ("+m+")"
R["global_feature_cell_G00"]={
 "n":len(F),"selection":"first 25 rows of the GLOBAL YouTube-derived list (G001-G025); NOT random; no Spotify-only or Hot-100-only rows; era 2009-2018 uploads",
 "bpm_as_recorded":q([r["bpm"] for r in F]),
 "bpm_source":share(Counter(r.get("bpm_source") or "null" for r in F)),
 "bpm_band":share(Counter(("<90" if r["bpm"]<90 else "90-109" if r["bpm"]<110 else "110-129" if r["bpm"]<130 else "130-149" if r["bpm"]<150 else ">=150") for r in F)),
 "rows_with_half_or_double_time_alternative_stated":sum(1 for r in F if r.get("perceived_pulse_note")),
 "tempo_change_rows":[r["title"] for r in F if r.get("tempo_change")],
 "mode":share(Counter(modecat(r.get("mode")) for r in F)),
 "mode_source":share(Counter(r.get("mode_source") or "null" for r in F)),
 "key_mode_conflict_spotify_site_vs_sheet_music":{"n_conflict":sum(1 for r in F if r.get("key_mode_conflict_site_vs_sheet")),"n_compared":sum(1 for r in F if r.get("mode_site_spotify_derived") and r.get("mode_source")=="wikipedia_sheet_music_quote" and r.get("mode") in ("major","minor")),"reading":"Spotify-derived key detection often returns the relative major/minor of the published key; site-only mode values are unreliable."},
 "key_pitch_class":share(Counter((r.get("key") or "null").replace("♯","#").replace("♭","b") for r in F)),
 "duration_sec":q([r["song_duration_sec"] for r in F if r.get("song_duration_sec")]),
 "duration_source":share(Counter(r.get("duration_source") or "null" for r in F)),
 "energy_spotify_derived":q([r["energy"] for r in F if r.get("energy") is not None]),
 "danceability_spotify_derived":q([float(r["groove"].split()[-1]) for r in F if r.get("groove")]),
 "valence_spotify_derived":q([float(r["emotion"].split()[-1]) for r in F if r.get("emotion")]),
 "loudness_db_spotify_derived":q([r["loudness_db"] for r in F if r.get("loudness_db") is not None]),
 "vocal_range_semitones_sheet_music":q([r["vocal_range_semitones"] for r in F if r.get("vocal_range_semitones") is not None]),
 "vocal_range_low_midi":q([r["vocal_range_low_midi"] for r in F if r.get("vocal_range_low_midi") is not None]),
 "vocal_range_high_midi":q([r["vocal_range_high_midi"] for r in F if r.get("vocal_range_high_midi") is not None]),
 "vocal_range_rows":[{"title":r["title"],"range":r["vocal_range_measured"],"semitones":r["vocal_range_semitones"],"citation":r.get("vocal_range_citation")} for r in F if r.get("vocal_range_semitones") is not None],
 "structural_timing_observed":[{"title":r["title"],"note":r["structural_timing_note"]} for r in F if r.get("structural_timing_note")],
 "meter":share(Counter(r.get("meter") or "null" for r in F)),
 "notes":["Values are secondary estimates: Spotify-derived features republished by third-party sites, and sheet-music key/tempo/range as quoted on Wikipedia (Musicnotes/Kobalt citations). Sheet-music vocal ranges describe the published arrangement, not a measured recording.",
          "Frequencies among 25 mega-hits; no comparison group; no association claims."]}

# ---- crossover
R["crossover"]={"n":0,"finding":"No song appears in both the GLOBAL and HINDI/INDIAN success cohorts. Non-Indian songs present in Indian sources (Starboy, Perfect on Spotify India chart totals; Pink Venom on India Songs 2022) are the only observed cross-market presence, and it runs global->India, not India->global. No Hindi-language recording was observed in any global top list fetched.",
 "observed_cross_presence":[{"song":"Starboy","artist":"The Weeknd","india_signal":"kworb Spotify India chart total 353,039,859 (rank 37), 1,852 chart days, peak 9"},
                            {"song":"Perfect","artist":"Ed Sheeran","india_signal":"kworb Spotify India chart total 335,472,026 (rank 40), 2,085 chart days, peak 24"},
                            {"song":"Pink Venom","artist":"Blackpink","india_signal":"Billboard India Songs #1, 1 week, 2022-09-03"}]}

# ---- single measured row
R["measured_feature_rows"]=[{k:r[k] for k in ("id","title","bpm","bpm_alt","key","mode","song_duration_sec","energy","groove","emotion","meter","feature_method","feature_confidence")} for r in rows if r.get("bpm") is not None]

json.dump(R, open(os.path.join(D,"ANALYSIS_RESULTS.json"),"w",encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(R, indent=1, ensure_ascii=False)[:6000])
