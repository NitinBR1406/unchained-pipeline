import csv, json, math, statistics as st
from datetime import date, datetime

OUT = "/mnt/user-data/outputs/CLAUDE_INDEPENDENT_REPORT_V01/"
WIKI_LIST = "https://en.wikipedia.org/wiki/List_of_most-viewed_Indian_YouTube_videos"
WIKI_LIST_OBS = "2026-09-21T22:19Z"   # WebFetch of the list page (approx., ±5 min)
RYD_OBS = "2026-09-21T22:21Z"        # returnyoutubedislikeapi fetch for Vaaste (approx., ±5 min)
SD_VAASTE = "https://songdata.io/search?query=vaaste"  # only songdata page whose results were actually served

# ---------- Stratum A: Hindi rows of the Wikipedia most-viewed list (views + upload date from that page) ----------
# (title, film/non-film, artist hint, wiki views, upload date, wiki_channel, language flag)
A = [
 ("A01","Zaroori Tha","non-film","Rahat Fateh Ali Khan",1729955594,"2014-06-09","The Folk & Soul Studio","Hindi/Urdu"),
 ("A02","Vaaste","non-film","Dhvani Bhanushali, Nikhil D'Souza",1717251224,"2019-04-06","T-Series","Hindi"),
 ("A03","Dilbar (Lyrical)","Satyameva Jayate","Neha Kakkar, Dhvani Bhanushali, Ikka",1537373784,"2018-07-09","T-Series","Hindi"),
 ("A04","Lut Gaye","non-film","Jubin Nautiyal",1521375840,"2021-02-17","T-Series","Hindi"),
 ("A05","Bum Bum Bole","Taare Zameen Par","Shaan",1453193441,"2011-05-25","T-Series","Hindi"),
 ("A06","Tujh Mein Rab Dikhta Hai","Rab Ne Bana Di Jodi","Roop Kumar Rathod",1423315007,"2012-01-19","Yash Raj Films","Hindi"),
 ("A07","Mile Ho Tum (Reprise)","Fever","Neha Kakkar, Tony Kakkar",1390041180,"2016-07-27","Zee Music Company","Hindi"),
 ("A08","Cham Cham","Baaghi","Monali Thakur",1391803282,"2016-05-06","T-Series","Hindi"),
 ("A09","Bom Diggy Diggy","Sonu Ke Titu Ki Sweety","Zack Knight, Jasmin Walia",1375607180,"2018-02-08","T-Series","Hindi"),
 ("A10","Aankh Marey (Lyrical)","Simmba","Neha Kakkar, Mika Singh, Kumar Sanu",1278800084,"2018-12-11","T-Series","Hindi"),
 ("A11","Dil Laga Liya","Dil Hai Tumhaara","Udit Narayan, Alka Yagnik",1264066276,"2009-12-09","Tips Industries","Hindi"),
 ("A12","Khairiyat","Chhichhore","Arijit Singh",1231107555,"2019-09-26","T-Series","Hindi"),
 ("A13","Tum Hi Aana","Marjaavaan","Jubin Nautiyal",1237271026,"2019-10-15","T-Series","Hindi"),
 ("A14","Jhoome Jo Pathaan","Pathaan","Arijit Singh, Sukriti Kakar",1229156160,"2022-12-22","Yash Raj Films","Hindi"),
 ("A15","Humnava Mere","non-film","Jubin Nautiyal",1229627869,"2018-05-23","T-Series","Hindi"),
 ("A16","Abhi Toh Party Shuru Hui Hai","Khoobsurat","Badshah, Aastha Gill",1214804650,"2014-11-11","T-Series","Hindi"),
 ("A17","Phir Bhi Tumko Chaahunga","Half Girlfriend","Arijit Singh, Shashaa Tirupati",1208851433,"2017-07-06","Zee Music Company","Hindi"),
 ("A18","Filhall","non-film","B Praak",1186610265,"2019-11-09","Desi Melodies","Hindi/Punjabi"),
 ("A19","Kala Chashma","Baar Baar Dekho","Badshah, Neha Kakkar, Amar Arshi",1132995629,"2016-07-27","Zee Music Company","Hindi/Punjabi"),
 ("A20","Galti Se Mistake","Jagga Jasoos","Arijit Singh, Amit Mishra",1109271065,"2017-06-09","T-Series","Hindi"),
 ("A21","Jaha Tum Rahoge","Maheruh","Altamash Faridi",1094199378,"2017-11-02","Zee Music Company","Hindi"),
 ("A22","Leja Re","non-film","Dhvani Bhanushali",1056213636,"2018-11-24","T-Series","Hindi"),
 ("A23","Genda Phool","non-film","Badshah, Payal Dev",1051177033,"2020-03-26","Sony Music India","Hindi/Bengali"),
 ("A24","O Saki Saki","Batla House","Neha Kakkar, Tulsi Kumar, B Praak",1047706419,"2019-08-29","T-Series","Hindi"),
 ("A25","Prem Ratan Dhan Payo","Prem Ratan Dhan Payo","Palak Muchhal",1025149571,"2015-12-01","T-Series","Hindi"),
 ("A26","Aaj Ki Raat","Stree 2","Madhubanti Bagchi",1011705060,"2024-07-24","Saregama Music","Hindi"),
]
# Aankh Marey full video (1,049,354,582; 2018-12-06) is a second official upload of the same recording -> dedup: keep the larger (lyrical) as primary, note both.

# ---------- Key/BPM evidence actually retrieved (secondary-source estimates; all Spotify-analysis-derived) ----------
# song_id -> dict of source records
KB = {
 "A01": {"sources":[
    {"src":"songbpm.com","url":"https://songbpm.com/@rahat-fateh-ali-khan/zaroori-tha","key":"G#/Ab","mode":"minor","bpm":114,"duration":"5:42","note":"half-time 57 / double-time 228 listed"},
    {"src":"getsongbpm.com","url":"https://getsongbpm.com/song/zaroori-tha/vlzq6V","key":None,"mode":None,"bpm":114,"duration":"5:42","note":"key not on page; 4/4"}]},
 "A02": {"sources":[
    {"src":"songbpm.com","url":"https://songbpm.com/@dhvani-bhanushali/vaaste","key":"F","mode":"major","bpm":90,"duration":"3:16","note":"double-time 180 listed; Spotify single edit is shorter than the 4:06 video"},
    {"src":"songdata.io","url":SD_VAASTE,"key":"F","mode":"major","bpm":90,"duration":None,"note":"camelot 7B; Spotify id 0mJTAdmY8olbGQjopDYff3"}]},
 "A03": {"sources":[
    {"src":"tunebat.com","url":"https://tunebat.com/Info/Dilbar-From-Satyameva-Jayate-Neha-Kakkar-Dhvani-Bhanushali-Ikka-Tanishk-Bagchi/4tjLYTXFqZhkUDga4bQ0yl","key":"A","mode":"minor","bpm":104,"duration":"3:04","note":"camelot 8A; energy 91 dance 73 valence 67; release 2018-07-04"},
    {"src":"songbpm.com","url":"https://songbpm.com/@neha-kakkar/dilbar-from-satyameva-jayate","key":"A","mode":"minor","bpm":104,"duration":"3:04","note":"half 52 / double 208 listed"}]},
 "A04": {"sources":[
    {"src":"musicgateway.com","url":"https://www.musicgateway.com/song-key-bpm/jubin-nautiyal/lut-gaye","key":"Bb","mode":"major","bpm":91,"duration":"3:48","note":"camelot 6B; energy 78 dance 64; release 2021-02-17"},
    {"src":"songbpm.com","url":"https://songbpm.com/@jubin-nautiyal/lut-gaye","key":"A#/Bb","mode":"major","bpm":91,"duration":"3:48","note":"double-time 182 listed"},
    {"src":"songdata.io","url":SD_VAASTE,"key":"Bb","mode":"major","bpm":91,"duration":None,"note":"camelot 6B; appeared in related results"}]},
 "A05": {"sources":[
    {"src":"songbpm.com","url":"https://songbpm.com/@shaan/bum-bum-bole-from-taare-zameen-par","key":None,"mode":None,"bpm":121,"duration":"5:36","note":"key/mode not shown on page; half 61 / double 242 listed"}]},
 "A06": {"sources":[
    {"src":"songbpm.com","url":"https://songbpm.com/@roop-kumar-rathod/tujh-mein-rab-dikhta-hai-from-rab-ne-bana-di-jodi","key":"G#/Ab","mode":"major","bpm":85,"duration":"4:42","note":"double-time 170 listed"}]},
 "A07": {"sources":[
    {"src":"songbpm.com","url":"https://songbpm.com/@neha-kakkar/mile-ho-tum-reprise","key":"F","mode":"minor","bpm":80,"duration":"5:06","note":"double-time 160 listed"}]},
 "A09": {"sources":[
    {"src":"tunebat.com","url":"https://tunebat.com/Info/Bom-Diggy-Diggy-Zack-Knight-Jasmin-Walia/6qCNaRRr5xJALfNJvh0NAw","key":"B","mode":"minor","bpm":104,"duration":"3:59","note":"camelot 10A; energy 83 dance 78 valence 50; release 2018-02-08"}]},
 "A22": {"sources":[
    {"src":"songdata.io","url":SD_VAASTE,"key":"Db","mode":"major","bpm":100,"duration":None,"note":"camelot 3B; appeared in related results of the 'vaaste' search"}]},
 "B11": {"sources":[
    {"src":"songdata.io","url":SD_VAASTE,"key":"F","mode":"minor","bpm":94,"duration":None,"note":"camelot 4A; appeared in related results"}]},
 "B58": {"sources":[
    {"src":"songdata.io","url":SD_VAASTE,"key":"Bb","mode":"major","bpm":81,"duration":None,"note":"camelot 6B; appeared in related results"}]},
 "B69": {"sources":[
    {"src":"songdata.io","url":SD_VAASTE,"key":"Bb","mode":"minor","bpm":95,"duration":None,"note":"camelot 3A; entry 'Tere Vaaste' (Varun Jain et al.)"},
    {"src":"songdata.io","url":SD_VAASTE,"key":"C","mode":"major","bpm":125,"duration":None,"note":"camelot 8B; entry 'Tere Vaaste (From Zara Hatke Zara Bachke)' — CONFLICTING estimate for what appears to be the same recording; unresolved"}]},
 "B130": {"sources":[
    {"src":"songdata.io","url":SD_VAASTE,"key":"C","mode":"major","bpm":95,"duration":None,"note":"camelot 8B; appeared in related results"}]},
}

# Emotion / use-case tags: analyst judgement from the songs' general reception, NOT measured. Labelled as such.
EMO = {"A01":"heartbreak/romantic ballad","A02":"romance (ballad, mid-tempo)","A03":"dance/item (recreation)","A04":"romance (ballad, qawwali-derived hook)",
 "A05":"uplifting/children's anthem","A06":"romance (devotional-tinged ballad)","A07":"romance/longing ballad","A08":"dance/romance (recreation)",
 "A09":"dance/party","A10":"dance/item (recreation)","A11":"romance","A12":"romance/nostalgia ballad","A13":"romance ballad","A14":"dance/party",
 "A15":"romance ballad","A16":"party","A17":"romance ballad","A18":"heartbreak","A19":"party (recreation)","A20":"upbeat/comic",
 "A21":"romance ballad","A22":"romance (recreation)","A23":"dance/folk-sample","A24":"dance/item (recreation)","A25":"romance/celebration","A26":"dance/item",
 "B11":"romance/heartbreak ballad","B58":"romance ballad","B69":"romance (playful)","B130":"romance (mid-tempo)"}

# ---------- Build dataset ----------
frame = list(csv.DictReader(open("/tmp/claude-0/-home-claude/fdced15d-acaf-5749-b0b2-214101ca889e/scratchpad/ssi/frame.csv")))
frame_by_id = {r["song_id"]: r for r in frame}
A_by_id = {a[0]: a for a in A}

def tempo_zone(b):
    if b is None: return None
    if b < 85: return "slow <85"
    if b < 100: return "mid 85-99"
    if b < 115: return "upper-mid 100-114"
    return "fast 115+"

def year(d): return int(d[:4]) if d else None

rows = []
for r in frame:
    sid = r["song_id"]
    a = A_by_id.get(sid)
    kb = KB.get(sid)
    srcs = kb["sources"] if kb else []
    ENH = {"A#/Bb":"Bb","G#/Ab":"Ab","C#/Db":"Db","D#/Eb":"Eb","F#/Gb":"F#"}
    keys = [(ENH.get(s["key"], s["key"]), s["mode"]) for s in srcs if s["key"]]
    bpms = [s["bpm"] for s in srcs if s["bpm"]]
    key = keys[0][0] if keys else None
    mode = keys[0][1] if keys else None
    conflict = None
    if len(set(keys)) > 1: conflict = "key/mode conflict between sources: " + "; ".join(f"{k} {m}" for k, m in keys)
    if len(set(bpms)) > 1: conflict = (conflict + " | " if conflict else "") + "BPM conflict: " + ", ".join(map(str, bpms))
    bpm = bpms[0] if bpms and not (len(set(bpms)) > 1) else None
    if sid == "B69": key = mode = bpm = None  # unresolved conflict -> null
    n_src = len(srcs)
    if key and n_src >= 2 and not conflict: conf = "medium (2+ concordant secondary estimates, same underlying analyser family)"
    elif key and n_src == 1: conf = "low (single secondary estimate)"
    elif bpm and not key: conf = "low (BPM only)"
    else: conf = None
    up = a[5] if a else None
    obs_date = date(2026, 9, 21)
    age_days = (obs_date - date.fromisoformat(up)).days if up else None
    views = a[4] if a else None
    rows.append({
        "song_id": sid, "stratum": r["stratum"], "title": a[1] if a else r["title"], "film": (None if (a and a[2]=="non-film") else (a[2] if a else r["film"])),
        "film_or_nonfilm": ("non-film" if (a and a[2]=="non-film") else ("non-film" if r["film"]=="non-film" else "film")),
        "singer_artist": a[3] if a else r["artist_hint"], "language_flag": a[7] if a else "Hindi (frame assumption; not verified)",
        "release_year": year(up) if a else (int(r["year_hint"]) if r["year_hint"] else None),
        "release_year_source": (WIKI_LIST if a else "Filmfare nominee pages (film year; ceremony year minus 1)"),
        "key": key, "mode": mode, "key_mode_classification": (f"{key} {mode}" if key else None),
        "bpm": bpm, "tempo_zone": tempo_zone(bpm), "half_double_tempo_note": next((s["note"] for s in srcs if s.get("note") and ("half" in s["note"] or "double" in s["note"])), None),
        "meter": ("4/4 (source-stated)" if any(s["src"] in ("songbpm.com","getsongbpm.com") for s in srcs) else None),
        "duration_source_audio": next((s["duration"] for s in srcs if s["duration"]), None),
        "yt_video_id": ("BBAyRBTfsOU" if sid=="A02" else None),
        "yt_url": ("https://www.youtube.com/watch?v=BBAyRBTfsOU" if sid=="A02" else None),
        "yt_channel": a[6] if a else None, "yt_upload_variant": ("lyrical" if "Lyrical" in (a[1] if a else "") else ("official video/audio per list; variant not verified" if a else None)),
        "yt_official": (True if a else None),
        "yt_views": views, "yt_views_source": (WIKI_LIST if a else None), "yt_views_observed_at": (WIKI_LIST_OBS if a else None),
        "yt_views_alt": (1759265677 if sid=="A02" else None), "yt_views_alt_source": ("https://returnyoutubedislikeapi.com/votes?videoId=BBAyRBTfsOU (third-party cached mirror; likes 14,001,366)" if sid=="A02" else None), "yt_views_alt_observed_at": (RYD_OBS if sid=="A02" else None),
        "yt_upload_date": up, "yt_upload_date_source": (WIKI_LIST if a else None),
        "upload_age_days_at_obs": age_days, "views_per_day": (round(views/age_days,1) if (views and age_days) else None),
        "streaming_indicators": None, "streaming_observed_at": None,
        "emotion_energy_tag": EMO.get(sid), "emotion_tag_basis": ("analyst judgement (hypothesis-level, not measured)" if EMO.get(sid) else None),
        "vocal_range_tessitura": None,
        "key_bpm_sources": [ {k:v for k,v in s.items()} for s in srcs ] if srcs else None,
        "n_key_bpm_sources": n_src, "measurement_method": ("secondary-source estimate (Spotify audio-analysis-derived, as republished by the listed sites); no independent audio measurement performed" if srcs else None),
        "key_bpm_confidence": conf, "conflicts": conflict,
        "evidence_tier": ("verified-secondary" if key or bpm else "frame-only"),
        "inclusion_status": ("included_full" if (a and key and bpm) else ("included_views_only" if a else ("included_keybpm_only" if (key or bpm) else "frame_only_no_data"))),
        "notes": ("second official upload of same recording: full video 1,049,354,582 views, uploaded 2018-12-06 (same list) — deduplicated to the lyrical upload" if sid=="A10" else ("pre-2011 film; outside the 10–15-year window, retained as flagged" if sid in ("A05","A06","A11") else ("YouTube watch page returned HTTP 429 to the fetch tool; direct view count unavailable" if a and sid!="A02" else None))),
    })

# ---------- Write dataset ----------
with open(OUT+"dataset_CLAUDE_V01.json","w") as f: json.dump({"report_id":"CLAUDE_INDEPENDENT_REPORT_V01","status":"FROZEN_V01","rows":rows}, f, indent=1, ensure_ascii=False)
flat_fields = [k for k in rows[0].keys() if k!="key_bpm_sources"] + ["key_bpm_source_urls"]
with open(OUT+"dataset_CLAUDE_V01.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=flat_fields); w.writeheader()
    for r in rows:
        rr = {k:v for k,v in r.items() if k!="key_bpm_sources"}
        rr["key_bpm_source_urls"] = " | ".join(s["url"] for s in (r["key_bpm_sources"] or []))
        w.writerow({k:("" if v is None else v) for k,v in rr.items()})

# ---------- Analysis ----------
full = [r for r in rows if r["key"] and r["bpm"] and r["yt_views"]]
kb_any = [r for r in rows if r["key"] and r["bpm"]]
A_rows = [r for r in rows if r["stratum"]=="A"]
res = {}
res["counts"] = {"frame_total":len(rows),"stratum_A":len(A_rows),"stratum_B":len(rows)-len(A_rows),
  "with_views":sum(1 for r in rows if r["yt_views"]),"with_key_and_bpm":len(kb_any),"with_bpm_only":sum(1 for r in rows if r["bpm"] and not r["key"]),
  "with_key_bpm_and_views":len(full),"with_two_concordant_key_sources":sum(1 for r in rows if r["n_key_bpm_sources"]>=2 and not r["conflicts"] and r["key"]),
  "unresolved_conflicts":sum(1 for r in rows if r["conflicts"]),"frame_only_no_data":sum(1 for r in rows if r["inclusion_status"]=="frame_only_no_data")}
def dist(lst,f):
    d={}
    for r in lst:
        d[f(r)]=d.get(f(r),0)+1
    return dict(sorted(d.items(), key=lambda x:-x[1]))
res["mode_frequency_all_with_key"] = dist(kb_any, lambda r:r["mode"])
res["key_frequency_all_with_key"] = dist(kb_any, lambda r:r["key_mode_classification"])
res["tempo_zone_frequency_all_with_bpm"] = dist([r for r in rows if r["bpm"]], lambda r:r["tempo_zone"])
bp=[r["bpm"] for r in rows if r["bpm"]]
res["bpm_summary_all_with_bpm"] = {"n":len(bp),"min":min(bp),"median":st.median(bp),"max":max(bp),"mean":round(st.mean(bp),1)}
res["cells_mode_x_tempo"] = dist(kb_any, lambda r:f"{r['mode']} × {r['tempo_zone']}")
# performance association within stratum A (views/day) split by mode — descriptive only
vpd_A=[r["views_per_day"] for r in A_rows if r["views_per_day"]]
res["stratum_A_views_per_day"]={"n":len(vpd_A),"median":round(st.median(vpd_A)),"min":round(min(vpd_A)),"max":round(max(vpd_A))}
by_mode={}
for r in A_rows:
    if r["mode"] and r["views_per_day"]: by_mode.setdefault(r["mode"],[]).append(r["views_per_day"])
res["stratum_A_views_per_day_by_mode"]={m:{"n":len(v),"median":round(st.median(v)),"values":[round(x) for x in v]} for m,v in by_mode.items()}
by_tz={}
for r in A_rows:
    if r["tempo_zone"] and r["views_per_day"]: by_tz.setdefault(r["tempo_zone"],[]).append(r["views_per_day"])
res["stratum_A_views_per_day_by_tempo_zone"]={m:{"n":len(v),"median":round(st.median(v))} for m,v in by_tz.items()}
res["ci_statement"]="No confidence intervals computed: per-cell n ≤ 3 in every key/mode × tempo cell; bootstrap intervals on such cells would be uninformative and could be misread as evidence."
res["top_ten_supported"]=False
res["top_ten_reason"]="Only %d recordings have key, BPM and a views figure; no stratum-B (non-billion-view) recording has views, so frequency cannot be separated from performance association. A ten-zone empirical ranking is not supported."%len(full)
with open(OUT+"analysis_results_CLAUDE_V01.json","w") as f: json.dump(res,f,indent=1)
print(json.dumps(res,indent=1))
for r in kb_any: print(r["song_id"],r["title"],r["key_mode_classification"],r["bpm"],r["tempo_zone"],r["yt_views"],r["views_per_day"])
