#!/usr/bin/env python3
"""Merge the one completed per-song feature batch (COLLECTOR_BATCH_G00_RAW.txt, 25 GLOBAL rows, collected 2026-09-22 before the
operator halt registered) into RAW_DATASET.json/csv. Values are taken verbatim from the collector's pipe table; key/mode/BPM/
vocal range from Wikipedia 'Composition' quotes are parsed by regex and kept alongside the Spotify-derived site values.
Run AFTER build_dataset.py and BEFORE analyze.py."""
import json, os, re, csv
D = os.path.join(os.path.dirname(__file__), "..", "data")
src = os.path.join(D, "COLLECTOR_BATCH_G00_RAW.txt")
ds = json.load(open(os.path.join(D,"RAW_DATASET.json"), encoding="utf-8"))
rows = {r["id"]: r for r in ds["rows"]}
lines = [l for l in open(src, encoding="utf-8").read().splitlines() if re.match(r"^G\d{3}\|", l)]
hdr = "id|title|artist_verified|bpm_site1|key_site1|mode_site1|duration_site1|energy|danceability|valence|loudness_db|acousticness|release_date_site1|site1_url|bpm_site2|key_site2|mode_site2|site2_url|bpm_alt_note|wiki_url|wiki_length|wiki_release|wiki_genre|wiki_composer|wiki_singers|wiki_film|wiki_key_tempo_quote|wiki_vocal_range_quote|wiki_range_citation|structural_timing_note".split("|")
NOTE = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"Fb":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11,"Cb":11}
def midi(n):
    n = n.replace("♯","#").replace("♭","b")
    m = re.match(r"([A-G][#b]?)(\d)", n)
    return NOTE[m.group(1)] + 12*(int(m.group(2))+1) if m else None
def nul(v): return None if v in ("null","",None) else v
def num(v):
    v = nul(v)
    if v is None: return None
    m = re.match(r"^-?\d+(\.\d+)?", v.strip()); return float(m.group(0)) if m else None
def dur(v):
    v = nul(v)
    if v is None: return None
    m = re.search(r"(\d+):(\d\d)", v); return int(m.group(1))*60+int(m.group(2)) if m else None
merged = 0
for l in lines:
    f = l.split("|")
    if len(f) != 30: raise SystemExit(f"bad field count {len(f)} in {l[:40]}")
    d = dict(zip(hdr, f)); r = rows[d["id"]]
    q = nul(d["wiki_key_tempo_quote"]) or ""
    qn = q.replace("♯","#").replace("♭","b").replace("-sharp","#").replace("-flat","b")
    mk = (re.search(r"key of ([A-G][#b]?)[ -]?(major|minor|dorian|mixolydian)", qn, re.I)
          or re.search(r"in the ([A-G][#b]?) (major|minor) key", qn, re.I)
          or re.search(r"composed in ([A-G][#b]?) (mixolydian|dorian)", qn, re.I))
    tempo_change = re.search(r"(\d{2,3}(?:\.\d)?) beats per minute before increasing to (\d{2,3})", qn)
    mb = re.search(r"(\d{2,3}(?:\.\d)?) beats per minute", qn)
    if not mb: mb = re.search(r"(\d{2,3}) BPM", qn)
    vr = nul(d["wiki_vocal_range_quote"]) or ""
    vn = re.findall(r"[A-G][♯♭#b]?\d", vr.replace("-flat","♭").replace("-sharp","♯"))
    lo, hi = (midi(vn[0]), midi(vn[1])) if len(vn) >= 2 else (None, None)
    site_bpm = num(d["bpm_site1"]) or num(d["bpm_site2"])
    site_mode = nul(d["mode_site1"]) or nul(d["mode_site2"])
    site_key = nul(d["key_site1"]) or nul(d["key_site2"])
    wiki_mode = mk.group(2).lower() if mk else None
    wiki_key = mk.group(1) if mk else None
    mode_final = wiki_mode if wiki_mode else site_mode
    mode_src = "wikipedia_sheet_music_quote" if wiki_mode else ("spotify_derived_site" if site_mode else None)
    key_final = wiki_key if wiki_key else site_key
    conflict = bool(wiki_mode and site_mode and wiki_mode in ("major","minor") and wiki_mode != site_mode)
    r.update({
      "artist_verified": nul(d["artist_verified"]),
      "bpm": (float(tempo_change.group(2)) if tempo_change else (num(mb.group(1)) if mb else site_bpm)),
      "tempo_change": (f"{tempo_change.group(1)} -> {tempo_change.group(2)} BPM (Wikipedia sheet-music quote)" if tempo_change else None),
      "bpm_source": "wikipedia_sheet_music_quote" if mb else ("spotify_derived_site" if site_bpm else None),
      "bpm_site_spotify_derived": site_bpm, "bpm_site2": num(d["bpm_site2"]),
      "bpm_alt": nul(d["bpm_alt_note"]),
      "perceived_pulse_note": ("half/double-time alternative stated by feature site" if (d["bpm_alt_note"] and re.search(r"half-time|double-time", d["bpm_alt_note"])) else None),
      "key": key_final, "mode": mode_final, "mode_source": mode_src,
      "key_site_spotify_derived": site_key, "mode_site_spotify_derived": site_mode,
      "key_mode_conflict_site_vs_sheet": conflict,
      "song_duration_sec": dur(d["wiki_length"]) or dur(d["duration_site1"]),
      "duration_source": "wikipedia_infobox" if dur(d["wiki_length"]) else ("feature_site" if dur(d["duration_site1"]) else None),
      "energy": num(d["energy"]), "groove": (f"danceability {num(d['danceability']):.0f}" if num(d["danceability"]) is not None else None),
      "emotion": (f"valence/happiness {num(d['valence']):.0f}" if num(d["valence"]) is not None else None),
      "loudness_db": num(d["loudness_db"]), "acousticness": num(d["acousticness"]),
      "meter": ("4/4" if re.search(r"4/4|common time|quadruple", (d["bpm_alt_note"] or "")+q) else ("12/8 or 4/4 triplets" if "12/8" in q else None)),
      "vocal_range_measured": (f"{vn[0]}-{vn[1]}" if len(vn)>=2 else None),
      "vocal_range_low_midi": lo, "vocal_range_high_midi": hi,
      "vocal_range_semitones": (hi-lo) if (lo is not None and hi is not None) else None,
      "vocal_range_kind": "secondary_estimate (published sheet-music range quoted on Wikipedia; not the recording's measured pitch)" if len(vn)>=2 else None,
      "vocal_range_citation": nul(d["wiki_range_citation"]),
      "wiki_genre": nul(d["wiki_genre"]), "wiki_release": nul(d["wiki_release"]), "wiki_film": nul(d["wiki_film"]),
      "wiki_key_tempo_quote": nul(d["wiki_key_tempo_quote"]), "wiki_vocal_range_quote": nul(d["wiki_vocal_range_quote"]),
      "structural_timing_note": nul(d["structural_timing_note"]),
      "feature_provenance_urls": ";".join(u for u in (nul(d["site1_url"]), nul(d["site2_url"]), nul(d["wiki_url"])) if u),
      "feature_method": "Collector batch G00 (2026-09-22): Spotify-derived features via Tunebat/SongBPM/GetSongBPM + Wikipedia Composition quotes (sheet-music citations). Site keys frequently disagree with sheet music by relative major/minor; sheet-music value preferred when present.",
      "feature_confidence": ("medium" if (mb or mk) else "low-medium (single secondary site)") ,
      "feature_kind": "secondary_estimate",
      "arrangement_production_era": r.get("arrangement_production_era") or (f"loudness {num(d['loudness_db'])} dB; acousticness {num(d['acousticness'])}" if num(d["loudness_db"]) is not None else None),
    })
    merged += 1
ds["feature_layer_note"] = f"{merged} GLOBAL rows carry per-song features from the one collector batch that completed before the operator halt (COLLECTOR_BATCH_G00_RAW.txt). All other rows: feature fields null."
json.dump(ds, open(os.path.join(D,"RAW_DATASET.json"),"w",encoding="utf-8"), indent=1, ensure_ascii=False)
first=["id","cohort","title","artist_as_listed"]; cols = first + sorted({k for r in ds["rows"] for k in r} - set(first))
with open(os.path.join(D,"RAW_DATASET.csv"),"w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for r in ds["rows"]: w.writerow({k:("" if r.get(k) is None else r.get(k)) for k in cols})
print("merged", merged, "rows; cols", len(cols))
for r in ds["rows"][:25]:
    print(r["id"], r["title"][:22].ljust(22), r["bpm"], r["key"], r["mode"], r["song_duration_sec"], r["vocal_range_measured"], r["vocal_range_semitones"], "conflict" if r.get("key_mode_conflict_site_vs_sheet") else "")
