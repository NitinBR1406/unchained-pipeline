"""
Unchained Nitin — Media Service (Cloud Run)
Twee functies:

1) POST /beats  { "audio_url": "<publieke/Drive-URL>", "every": 4 }  (of file-upload veld "file")
   -> { duration, bpm, num_beats, beats: [...], downbeats: [...] }
   Beat/BPM-detectie met numpy + ffmpeg (geen librosa nodig).

2) POST /prep   { "video_url": "<Drive/URL>", "audio_url": "<Drive/URL, optioneel>", "title": "..." }
   -> { url, bucket, object, size_mb, duration }
   Voegt losse (gesyncte) video + audio samen, normaliseert de audio naar -14 LUFS
   en rendert een social-ready H.264/AAC MP4 (+faststart). Zet het bestand in een
   publieke GCS-bucket en geeft de publieke MP4-URL terug -> geschikt als OpusClip-bron
   ("Any public video S3 link of an MP4 file").

Beide endpoints zijn beveiligd met header 'X-API-Key' == env BEAT_API_KEY (health / blijft open).
Google Drive-downloads (incl. grote bestanden met bevestigings-token) worden afgehandeld.
"""
import os, re, subprocess, tempfile, uuid, json, math
import numpy as np
import requests
from flask import Flask, request, jsonify

import lyrics as L  # pure lyrics-logica (parsing, regel-splitsing, per-fragment offset, pill-PNG)
import clip_fx as FX  # kick/snare-detectie + beat-synced zoom-punch/shake voor gefilmde clips

app = Flask(__name__)
APP_VERSION = "v19-hostasset"
SR, HOP, NFFT = 22050, 512, 2048
EXPECTED_KEY = os.environ.get("BEAT_API_KEY")
BUCKET_NAME = os.environ.get("BUCKET_NAME")  # publieke bucket voor prepped MP4's
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")            # voor /transcribe (Whisper + romanize)
TRANSCRIBE_MODEL = os.environ.get("TRANSCRIBE_MODEL") or "gpt-4o-transcribe"
ROMANIZE_MODEL = os.environ.get("ROMANIZE_MODEL") or "gpt-4o-mini"

# --- Assets voor /visualizer (meegeleverd in de container-map, of via env-URL) ---
ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.environ.get("LOGO_PATH") or os.path.join(ASSET_DIR, "unchained_chain_emblem.png")
FONT_BOLD = os.environ.get("FONT_BOLD") or os.path.join(ASSET_DIR, "Poppins-Bold.ttf")
FONT_MED = os.environ.get("FONT_MED") or os.path.join(ASSET_DIR, "Poppins-Medium.ttf")
CIRCLE_MASK = os.path.join(ASSET_DIR, "vis_circle720.png")   # voorgerekend rond masker (stijl C)
RING_IMG = os.path.join(ASSET_DIR, "vis_ring800.png")        # voorgerekende gouden ring (stijl C)
OUTRO_PATH = os.environ.get("OUTRO_PATH") or os.path.join(ASSET_DIR, "visualizer_outro.png")
OUTRO_DUR = float(os.environ.get("OUTRO_DUR") or 4.0)   # end-card: laatste N seconden
LUFS = os.environ.get("LUFS") or "-14"                  # social-standaard loudness
STYLE_ORDER = "ABCD"  # rotatie A->B->C->D (spectrum = schone showwaves p2p i.p.v. showfreqs)
GOLD = "0xD4AF37"


def _authorized():
    return not EXPECTED_KEY or request.headers.get("X-API-Key") == EXPECTED_KEY


def _download_drive(fid, dest):
    s = requests.Session()
    url = "https://drive.usercontent.google.com/download"
    r = s.get(url, params={"id": fid, "export": "download", "confirm": "t"},
              stream=True, timeout=300)
    ct = r.headers.get("Content-Type", "")
    if "text/html" in ct:  # bevestigings-pagina -> formulier opnieuw indienen
        html = r.text
        action = re.search(r'action="([^"]+)"', html)
        inputs = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', html))
        if action and inputs:
            r = s.get(action.group(1).replace("&amp;", "&"), params=inputs,
                      stream=True, timeout=300)
    r.raise_for_status()
    total = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            if chunk:
                f.write(chunk); total += len(chunk)
    if total < 2000:
        raise ValueError("Drive-download te klein/leeg — bestand niet publiek gedeeld?")


def download(url, dest):
    if "drive.google.com" in url or "drive.usercontent.google.com" in url:
        fid = None
        for pat in (r"/d/([\w-]+)", r"[?&]id=([\w-]+)"):
            m = re.search(pat, url)
            if m:
                fid = m.group(1); break
        if fid:
            return _download_drive(fid, dest)
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            if chunk:
                f.write(chunk)


def _download_drive_api(file_id, dest):
    """Authenticated download van een Drive-bestand (ook uit een Shared Drive) via de
    Cloud Run service-account (ADC + drive.readonly). Geen publieke link nodig.
    Vereist: Drive API enabled + de service-account als member van de Shared Drive."""
    import io
    import google.auth
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _status, done = dl.next_chunk()


def _ffprobe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path], stdout=subprocess.PIPE, check=True).stdout
        return round(float(json.loads(out)["format"]["duration"]), 1)
    except Exception:
        return None


def _upload_gcs(local_path, object_name, content_type="video/mp4"):
    from google.cloud import storage
    if not BUCKET_NAME:
        raise ValueError("BUCKET_NAME env-var niet gezet")
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_path, content_type=content_type)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"


def _download_gcs(object_name, dest):
    from google.cloud import storage
    storage.Client().bucket(BUCKET_NAME).blob(object_name).download_to_filename(dest)


def _drive_find_in_folder(svc, folder_id, name):
    q = "name = '%s' and '%s' in parents and trashed = false" % (name.replace("'", "\\'"), folder_id)
    res = svc.files().list(q=q, spaces="drive", fields="files(id,name)",
                           supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    return res.get("files", [])


def _upload_to_drive(local_path, folder_id, filename, mime="video/mp4", allow_version=False):
    """Upload naar een (Shared) Drive-map. Veilige schrijfregels: nooit stil overschrijven.
    Bestaat de naam al -> conflict (tenzij allow_version: dan _V02/_V03...). Retourneert dict."""
    import google.auth
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    existing = _drive_find_in_folder(svc, folder_id, filename)
    final_name = filename
    conflict = False
    if existing:
        conflict = True
        if not allow_version:
            return {"uploaded": False, "conflict": True, "existing_id": existing[0]["id"],
                    "name": filename, "note": "file exists; not overwritten"}
        stem, dot, ext = filename.rpartition(".")
        n = 2
        while _drive_find_in_folder(svc, folder_id, "%s_V%02d.%s" % (stem, n, ext)):
            n += 1
        final_name = "%s_V%02d.%s" % (stem, n, ext)
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
    f = svc.files().create(body={"name": final_name, "parents": [folder_id]},
                           media_body=media, fields="id,name,size",
                           supportsAllDrives=True).execute()
    return {"uploaded": True, "conflict": conflict, "id": f.get("id"),
            "name": f.get("name"), "size": f.get("size")}


def _make_contact_sheet(video_path, out_jpg):
    """Contactvel: rooster van frames uit de clip -> 1 JPEG (voor snelle review)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video_path,
                    "-vf", "fps=1,scale=240:-1,tile=5x5", "-frames:v", "1",
                    "-q:v", "3", out_jpg], check=True)


def prep_media(video_path, audio_path, out_path):
    """Mux video + (optioneel) losse audio, normaliseer -14 LUFS, render social-MP4."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video_path]
    if audio_path:
        cmd += ["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-movflags", "+faststart", "-shortest", out_path,
    ]
    subprocess.run(cmd, check=True)


def detect_beats(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        stdout=subprocess.PIPE, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32).copy()
    dur = len(y) / SR
    win = np.hanning(NFFT).astype(np.float32)
    nframes = 1 + (len(y) - NFFT) // HOP
    if nframes < 4:
        raise ValueError("audio te kort")
    S = np.empty((NFFT // 2 + 1, nframes), dtype=np.float32)
    for i in range(nframes):
        S[:, i] = np.abs(np.fft.rfft(y[i * HOP:i * HOP + NFFT] * win))
    Smag = np.log1p(S)
    flux = np.maximum(0, Smag[:, 1:] - Smag[:, :-1]).sum(axis=0)
    onset = np.concatenate([[0], flux])
    onset = np.maximum(onset - onset.mean(), 0)
    if onset.max() > 0:
        onset /= onset.max()
    fps = SR / HOP
    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    lags = np.arange(len(ac))
    with np.errstate(divide="ignore"):
        bpm = 60.0 * fps / np.maximum(lags, 1e-9)
    mask = (bpm >= 60) & (bpm <= 200)
    prior = np.exp(-0.5 * ((np.log2(np.where(mask, bpm, 120) / 120)) / 0.9) ** 2)
    best_lag = int(np.argmax(ac * mask * prior))
    tempo = 60.0 * fps / best_lag
    period = best_lag
    tightness = 100.0
    N = len(onset)
    cumscore = np.zeros(N)
    backlink = -np.ones(N, dtype=int)
    w = np.arange(-int(round(2 * period)), -int(round(period / 2)) + 1)
    txcost = -tightness * (np.log(-w / period)) ** 2
    for n in range(N):
        idx = n + w
        valid = idx >= 0
        if not valid.any():
            cumscore[n] = onset[n]
            continue
        scores = np.full(len(w), -1e9)
        scores[valid] = txcost[valid] + cumscore[idx[valid]]
        b = int(np.argmax(scores))
        cumscore[n] = onset[n] + max(scores[b], 0)
        if scores[b] > 0:
            backlink[n] = idx[b]
    start = int(N * 0.9) + int(np.argmax(cumscore[int(N * 0.9):]))
    beats = []
    n = start
    while n >= 0:
        beats.append(n); n = backlink[n]
    beats = np.array(sorted(beats))
    bt = (beats / fps).round(3)
    return dur, tempo, bt


FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
CINZEL_SEMIBOLD = os.path.join(FONT_DIR, "Cinzel-SemiBold.ttf")
MONTSERRAT_REGULAR = os.path.join(FONT_DIR, "Montserrat-Regular.ttf")
MONTSERRAT_MEDIUM = os.path.join(FONT_DIR, "Montserrat-Medium.ttf")


@app.get("/")
def health():
    return "media-service ok " + APP_VERSION, 200


@app.get("/fonts")
def fonts():
    """Verifieer dat de branded-master fonts (Cinzel SemiBold, Montserrat Regular/Medium)
    aanwezig zijn en de juiste family/subfamily rapporteren. FONT_ASSET_GATE = PASS/FAIL."""
    out = {}
    checks = [("cinzel_semibold", CINZEL_SEMIBOLD, "Cinzel", "SemiBold"),
              ("montserrat_regular", MONTSERRAT_REGULAR, "Montserrat", "Regular"),
              ("montserrat_medium", MONTSERRAT_MEDIUM, "Montserrat", "Medium")]
    for key, p, fam, sub in checks:
        info = {"path": p, "exists": os.path.exists(p)}
        if info["exists"]:
            info["size"] = os.path.getsize(p)
            try:
                from fontTools.ttLib import TTFont
                nm = TTFont(p)["name"]
                info["family"] = str(nm.getName(16, 3, 1, 0x409) or nm.getName(1, 3, 1, 0x409) or "")
                info["subfamily"] = str(nm.getName(17, 3, 1, 0x409) or nm.getName(2, 3, 1, 0x409) or "")
            except Exception as e:
                info["name_error"] = str(e)
        out[key] = info
    allok = all(out[k]["exists"] for k in out)
    return jsonify(version=APP_VERSION, fonts=out,
                   font_asset_gate="PASS" if allok else "FAIL")


@app.post("/host_asset")
def host_asset():
    """POST { name } -> upload een gebundeld brand-asset naar de publieke GCS-bucket en
    retourneer de publieke HTTPS-URL (voor externe renderers zoals Shotstack)."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    name = b.get("name", "unchained_chain_emblem.png")
    allowed = {"unchained_chain_emblem.png", "unchained_nitin_logo.png", "visualizer_outro.png"}
    if name not in allowed:
        return jsonify(error="asset niet toegestaan", allowed=sorted(allowed)), 400
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    if not os.path.exists(path):
        return jsonify(error="asset niet gevonden in service", name=name), 404
    obj = "assets/%s" % name
    url = _upload_gcs(path, obj, "image/png")
    return jsonify(version=APP_VERSION, name=name, object=obj, url=url,
                   sha256=_sha256_file(path))


@app.post("/stage_to_drive")
def stage_to_drive():
    """POST { gcs_object|gcs_url, drive_folder_id, output_filename, allow_version? }
    Kopieert een BESTAANDE GCS-render byte-identiek naar een (Shared) Drive-map.
    Geen re-render. GCS blijft intact. Veilige schrijfregels (geen stille overwrite)."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    obj = b.get("gcs_object")
    if not obj and b.get("gcs_url"):
        obj = b["gcs_url"].split("/%s/" % BUCKET_NAME, 1)[-1]
    folder_id = b.get("drive_folder_id")
    name = b.get("output_filename")
    if not (obj and folder_id and name):
        return jsonify(error="gcs_object/gcs_url + drive_folder_id + output_filename vereist"), 400
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    try:
        _download_gcs(obj, tmp)
        res = _upload_to_drive(tmp, folder_id, name, mime="video/mp4",
                               allow_version=bool(b.get("allow_version", False)))
        return jsonify(version=APP_VERSION, gcs_object=obj, gcs_intact=True, **res)
    except Exception as e:
        return jsonify(error=str(e), gcs_object=obj, gcs_intact=True), 500
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _run_stderr(cmd):
    return subprocess.run(cmd, stderr=subprocess.PIPE).stderr.decode(errors="replace")


def _audio_stream_info(path):
    """codec_name, sample_rate, channels van de eerste audiostream."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                          "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate",
                          "-of", "default=nw=1", path], stdout=subprocess.PIPE).stdout.decode()
    d = {}
    for line in out.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1); d[k] = v
    return d


def _measure_audio(path):
    """Meet loudness (EBU R128) + sample peaks + clipping van een bestand.
    Retourneert dict: integrated, lra, true_peak, st_max, sample_peak_l/r, clipped."""
    res = {}
    txt = _run_stderr(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                       "-af", "ebur128=peak=true", "-f", "null", "-"])
    # ebur128 logt PER FRAME 'I:'/'LRA:'; de samenvatting staat als LAATSTE -> [-1] pakken.
    iis = re.findall(r"I:\s*(-?[0-9.]+|-?inf)\s*LUFS", txt);  res["integrated"] = iis[-1] if iis else None
    lras = re.findall(r"LRA:\s*(-?[0-9.]+)\s*LU", txt);        res["lra"] = lras[-1] if lras else None
    tps = re.findall(r"Peak:\s*(-?[0-9.]+|-?inf)\s*dBFS", txt)
    res["true_peak"] = tps[-1] if tps else None
    sts = [float(x) for x in re.findall(r"\bS:\s*(-?[0-9.]+)", txt) if x not in ("-inf",)]
    res["st_max"] = round(max(sts), 2) if sts else None
    # astats: per-kanaal sample peak + clipped samples
    txt2 = _run_stderr(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                        "-af", "astats=metadata=1:reset=0", "-f", "null", "-"])
    peaks = re.findall(r"Peak level dB:\s*(-?inf|-?[0-9.]+)", txt2)
    res["sample_peak_l"] = peaks[0] if len(peaks) >= 1 else None
    res["sample_peak_r"] = peaks[1] if len(peaks) >= 2 else None
    clip = re.findall(r"Number of clipped samples:\s*([0-9]+)", txt2)
    res["clipped"] = sum(int(c) for c in clip) if clip else 0
    return res


def _loudnorm_measure(path, I, TP, LRA):
    """loudnorm pass 1: meet input_i/input_tp/input_lra/input_thresh/target_offset (JSON)."""
    txt = _run_stderr(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                       "-af", "loudnorm=I=%.2f:TP=%.2f:LRA=%.2f:print_format=json" % (I, TP, LRA),
                       "-f", "null", "-"])
    m = re.search(r"\{[^{}]*input_i[\s\S]*?\}", txt)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _video_stream_md5(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0",
                          "-c", "copy", "-f", "md5", "-"], stdout=subprocess.PIPE).stdout.decode().strip()
    return out


@app.post("/audio_master")
def audio_master():
    """POST /audio_master { drive_file_id|video_url, target_tp?, gain_db?, bitrate?,
    save_to_drive?, drive_folder_id?, output_filename? }
    Transparante peak-safety master: VIDEO = stream copy (geen re-encode), audio krijgt
    alleen true-peak-aware limiting (oversampled) tot <= target_tp. Geen EQ/comp/widening/
    saturation. Sample rate blijft die van de bron. Meet in/out en retourneert alles."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    drive_file_id = b.get("drive_file_id")
    video_url = b.get("video_url") or b.get("url")
    if not drive_file_id and not video_url:
        return jsonify(error="geen drive_file_id of video_url"), 400
    target_i = float(b.get("target_i", -10.0))       # integrated LUFS-doel (~-10)
    target_tp = float(b.get("target_tp", -2.0))      # START interne ceiling (dBTP); adaptief verlaagd
    bitrate = str(b.get("bitrate", "320k"))
    vin = tempfile.NamedTemporaryFile(delete=False, suffix=".vin.mp4").name
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    tmps = [vin, out]
    try:
        if drive_file_id:
            _download_drive_api(drive_file_id, vin)
        else:
            download(video_url, vin)
        # video mag NIET re-encoded worden -> stream copy. Codec vooraf checken.
        vcodec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1",
                                 vin], stdout=subprocess.PIPE).stdout.decode().strip()
        if vcodec not in ("h264", "hevc", "h265", "mpeg4", "vp9", "av1"):
            return jsonify(error="video-codec '%s' niet veilig stream-copy-baar naar mp4; "
                                 "re-encode vereist -> gestopt (visual master is locked)" % vcodec,
                           video_codec=vcodec), 409
        ainfo = _audio_stream_info(vin)
        sr = int(ainfo.get("sample_rate") or 44100)
        before = _measure_audio(vin)
        # PEAK-ONLY master (macro-dynamica/LRA behouden; GEEN loudness-compressie):
        #  1) kleine statische lineaire gain richting target_i (alleen verlagen);
        #  2) true-peak-limiter via 8x oversampling, ceiling met marge;
        #  3) ADAPTIEF: na AAC-encode de echte true-peak meten; is die > -1.0 dan de
        #     ceiling verlagen en opnieuw (AAC voegt inter-sample-overs toe boven de
        #     interne ceiling). Zo is de eind-TP gegarandeerd <= -1.0.
        try:
            in_i = float(before.get("integrated"))
        except (TypeError, ValueError):
            in_i = target_i
        gain = round(target_i - in_i, 2)
        gain = max(-6.0, min(0.0, gain))        # alleen zachter, nooit luider; veiligheidscap
        os_sr = sr * 8
        ceiling = float(target_tp)              # interne alimiter-ceiling in dBTP (start met marge)
        tp_attempts = []
        after = {}
        for _att in range(4):
            lim = 10 ** (ceiling / 20.0)
            chain = ("volume=%.2fdB,aresample=%d,"
                     "alimiter=level_in=1:level_out=1:limit=%.5f:level=false:asc=1:attack=5:release=60,"
                     "aresample=%d" % (gain, os_sr, lim, sr))
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", vin,
                   "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                   "-af", chain, "-c:a", "aac", "-b:a", bitrate, "-ar", str(sr),
                   "-movflags", "+faststart", out]
            r = subprocess.run(cmd, stderr=subprocess.PIPE)
            if r.returncode != 0:
                return jsonify(error="ffmpeg: " + r.stderr.decode(errors="replace")[-800:]), 500
            after = _measure_audio(out)
            try:
                tp_meas = float(after.get("true_peak"))
            except (TypeError, ValueError):
                tp_meas = 0.0
            tp_attempts.append({"internal_ceiling_dbtp": round(ceiling, 2), "measured_tp": tp_meas})
            if tp_meas <= -1.0:
                break
            ceiling -= (tp_meas - (-1.0)) + 0.3   # zak onder wat de encode extra opduwde
        norm_type = "peak-limit-only"
        vid_in_md5 = _video_stream_md5(vin)
        vid_out_md5 = _video_stream_md5(out)
        aout = _audio_stream_info(out)
        obj = f"clips/{uuid.uuid4().hex}.mp4"
        url = _upload_gcs(out, obj)
        drive = {}
        if bool(b.get("save_to_drive")) and b.get("drive_folder_id") and b.get("output_filename"):
            try:
                drive = {"drive": _upload_to_drive(out, b["drive_folder_id"], b["output_filename"],
                                                   mime="video/mp4",
                                                   allow_version=bool(b.get("allow_version", False)))}
            except Exception as e:
                drive = {"drive": {"uploaded": False, "error": str(e)}}
        return jsonify(version=APP_VERSION, url=url, bucket=BUCKET_NAME, object=obj,
                       size_mb=round(os.path.getsize(out) / (1 << 20), 1),
                       duration=_ffprobe_duration(out),
                       video_stream_copied=True,
                       video_stream_md5_in=vid_in_md5, video_stream_md5_out=vid_out_md5,
                       video_stream_identical=(vid_in_md5 == vid_out_md5),
                       audio_codec=aout.get("codec_name"), sample_rate=aout.get("sample_rate"),
                       channels=aout.get("channels"), bitrate=aout.get("bit_rate"),
                       target_i=target_i, target_tp=target_tp,
                       normalization_type=norm_type, gain_applied_db=gain,
                       tp_attempts=tp_attempts,
                       audio_before=before, audio_after=after, **drive)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in tmps:
            try:
                os.unlink(p)
            except OSError:
                pass


UN_ASSET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unchained_chain_emblem.png")
_FONT_MAP = {"cinzel600": CINZEL_SEMIBOLD, "mont500": MONTSERRAT_MEDIUM, "mont400": MONTSERRAT_REGULAR}


@app.post("/brand_master")
def brand_master():
    """POST /brand_master { drive_file_id, expected_un_sha256, events[], fps?,
    crf?, preset?, save_to_drive?, drive_folder_id?, output_filename?, qc_frames? }
    Burn-in van EV-overlays (tekst-PNG's met tracking+shadow + UN-monogram) op de
    locked master. Video re-encode (libx264), audio -c:a copy. Gates: UN-sha256, fonts."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    drive_file_id = b.get("drive_file_id")
    video_url = b.get("video_url")
    if not drive_file_id and not video_url:
        return jsonify(error="geen drive_file_id/video_url"), 400
    events = b.get("events") or []
    fps = float(b.get("fps", 24.0))
    crf = str(b.get("crf", "14"))
    preset = str(b.get("preset", "slow"))
    # --- font gate ---
    for key, p in _FONT_MAP.items():
        if not os.path.exists(p):
            return jsonify(error="FONT_ASSET_GATE FAIL: ontbreekt %s (%s)" % (key, p),
                           font_asset_gate="FAIL"), 409
    # --- UN asset sha256 gate ---
    if not os.path.exists(UN_ASSET_PATH):
        return jsonify(error="UN_ASSET_GATE FAIL: monogram niet gevonden", un_asset_gate="FAIL"), 409
    un_sha = _sha256_file(UN_ASSET_PATH)
    exp = (b.get("expected_un_sha256") or "").lower().strip()
    if exp and un_sha != exp:
        return jsonify(error="UN_ASSET_GATE FAIL_HASH_MISMATCH", un_asset_gate="FAIL_HASH_MISMATCH",
                       un_asset_sha256=un_sha, expected=exp), 409
    vin = tempfile.NamedTemporaryFile(delete=False, suffix=".vin.mp4").name
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    tmps = [vin, out]
    try:
        if drive_file_id:
            _download_drive_api(drive_file_id, vin)
        else:
            download(video_url, vin)
        # source verificatie
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
                                "-of", "default=nw=1", vin], stdout=subprocess.PIPE).stdout.decode()
        acodec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                 "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1",
                                 vin], stdout=subprocess.PIPE).stdout.decode().strip()
        # prescale UN voor elke gevraagde image-breedte
        un_scaled = {}
        for ev in events:
            if ev.get("type") == "image":
                w = int(ev["width"])
                if w not in un_scaled:
                    un_scaled[w] = _scaled_image_png(UN_ASSET_PATH, w)
        # bouw filtergraph
        base_args = ["ffmpeg", "-v", "error", "-y", "-i", vin]
        fc = ["[0:v]setsar=1[v0]"]
        idx = 1
        prev = "v0"
        for ev in sorted(events, key=lambda e: (e.get("z", 0), e.get("start_f", 0))):
            t0 = ev["start_f"] / fps
            t1 = ev["end_f"] / fps
            durs = (ev["end_f"] - ev["start_f"]) / fps
            entry = ev.get("entry_f", 0) / fps
            exit_ = ev.get("exit_f", 0) / fps
            maxop = float(ev.get("max_opacity", 1.0))
            if ev.get("type") == "text":
                png, W, H = _render_text_png(ev["text"], _FONT_MAP[ev["font"]], int(ev["size"]),
                                             float(ev.get("tracking", 0)), ev["color"],
                                             shadow=bool(ev.get("shadow", True)))
                tmps.append(png)
            else:
                png, W, H = un_scaled[int(ev["width"])]
                tmps.append(png)
            base_args += ["-loop", "1", "-t", "%.3f" % max(0.05, durs), "-i", png]
            k = idx; idx += 1
            if ev.get("anchor", "center") == "center":
                X0 = int(round(ev["x"] - W / 2.0)); Y0 = int(round(ev["y"] - H / 2.0))
            else:
                X0 = int(ev["x"]); Y0 = int(ev["y"])
            rise = int(ev.get("rise_px", 0))
            fo_st = max(0.0, durs - exit_)
            seg = "[%d:v]fps=%g,format=yuva420p,colorchannelmixer=aa=%.4f" % (k, fps, maxop)
            if entry > 0:
                seg += ",fade=t=in:st=0:d=%.4f:alpha=1" % entry
            if exit_ > 0:
                seg += ",fade=t=out:st=%.4f:d=%.4f:alpha=1" % (fo_st, exit_)
            seg += ",setpts=PTS-STARTPTS+%.5f/TB[ov%d]" % (t0, k)
            fc.append(seg)
            if rise > 0 and entry > 0:
                yexpr = "%d+%d*pow(max(0\\,1-((t-%.5f)/%.5f))\\,2)" % (Y0, rise, t0, entry)
            else:
                yexpr = "%d" % Y0
            fc.append("[%s][ov%d]overlay=%d:%s:enable='gte(t\\,%.5f)*lt(t\\,%.5f)'[v%d]"
                      % (prev, k, X0, yexpr, t0, t1, k))
            prev = "v%d" % k
        filter_complex = ";".join(fc)
        cmd = base_args + ["-filter_complex", filter_complex, "-map", "[%s]" % prev, "-map", "0:a:0",
                           "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p",
                           "-r", "%g" % fps, "-vsync", "cfr",
                           "-colorspace", "bt709", "-color_primaries", "bt709",
                           "-color_trc", "bt709", "-color_range", "tv",
                           "-c:a", "copy", "-movflags", "+faststart", out]
        r = subprocess.run(cmd, stderr=subprocess.PIPE)
        if r.returncode != 0:
            return jsonify(error="ffmpeg: " + r.stderr.decode(errors="replace")[-1200:]), 500
        # metingen
        vid_a_in = _video_stream_md5(vin)  # niet gebruikt voor gelijkheid (video re-encode)
        aud_in = subprocess.run(["ffmpeg", "-v", "error", "-i", vin, "-map", "0:a:0", "-c", "copy",
                                 "-f", "md5", "-"], stdout=subprocess.PIPE).stdout.decode().strip()
        aud_out = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-map", "0:a:0", "-c", "copy",
                                  "-f", "md5", "-"], stdout=subprocess.PIPE).stdout.decode().strip()
        vprobe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                 "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,"
                                 "duration,pix_fmt,color_primaries,color_transfer,color_space,color_range",
                                 "-of", "default=nw=1", out], stdout=subprocess.PIPE).stdout.decode()
        aout = _audio_stream_info(out)
        after_loud = _measure_audio(out)
        # QC contact sheet op key-frames
        qc_url = None
        try:
            qframes = b.get("qc_frames") or [30, 60, 1000, 1055, 1500, 2930, 3480, 3950, 4400, 4850, 4950, 5006]
            from PIL import Image as _I
            thumbs = []
            for qf in qframes:
                fp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                tmps.append(fp)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % (qf / fps), "-i", out,
                                "-frames:v", "1", fp], check=False)
                if os.path.exists(fp) and os.path.getsize(fp) > 0:
                    thumbs.append((qf, fp))
            if thumbs:
                cols = 4
                rows = int(math.ceil(len(thumbs) / cols))
                tw, th = 270, 480
                sheet = _I.new("RGB", (cols * tw, rows * th), (12, 12, 12))
                from PIL import ImageDraw as _D
                dd = _D.Draw(sheet)
                for i, (qf, fp) in enumerate(thumbs):
                    im = _I.open(fp).convert("RGB").resize((tw, th), _I.LANCZOS)
                    sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
                    dd.text(((i % cols) * tw + 6, (i // cols) * th + 6), "f%d" % qf, fill=(255, 215, 0))
                qp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                tmps.append(qp)
                sheet.save(qp, quality=90)
                qc_url = _upload_gcs(qp, "clips/%s_brandqc.jpg" % uuid.uuid4().hex, "image/jpeg")
        except Exception as e:
            qc_url = "qc_error: %s" % e
        obj = f"clips/{uuid.uuid4().hex}.mp4"
        url = _upload_gcs(out, obj)
        out_sha = _sha256_file(out)
        drive = {}
        if bool(b.get("save_to_drive")) and b.get("drive_folder_id") and b.get("output_filename"):
            try:
                drive = {"drive": _upload_to_drive(out, b["drive_folder_id"], b["output_filename"],
                                                   mime="video/mp4",
                                                   allow_version=bool(b.get("allow_version", False)))}
            except Exception as e:
                drive = {"drive": {"uploaded": False, "error": str(e)}}
        n_text = sum(1 for e in events if e.get("type") == "text")
        n_img = sum(1 for e in events if e.get("type") == "image")
        return jsonify(version=APP_VERSION, url=url, qc_url=qc_url, bucket=BUCKET_NAME, object=obj,
                       size_mb=round(os.path.getsize(out) / (1 << 20), 1),
                       output_sha256=out_sha,
                       source_probe=probe.strip(), source_audio_codec=acodec,
                       output_probe=vprobe.strip(),
                       audio_codec=aout.get("codec_name"), sample_rate=aout.get("sample_rate"),
                       channels=aout.get("channels"),
                       audio_stream_copy=(aud_in == aud_out),
                       audio_md5_in=aud_in, audio_md5_out=aud_out,
                       audio_after=after_loud,
                       un_asset_gate="PASS", un_asset_sha256=un_sha,
                       font_asset_gate="PASS",
                       cinzel_fontfile=CINZEL_SEMIBOLD, montserrat_medium_fontfile=MONTSERRAT_MEDIUM,
                       montserrat_regular_fontfile=MONTSERRAT_REGULAR,
                       text_events=n_text, image_events=n_img, **drive)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in tmps:
            try:
                os.unlink(p)
            except OSError:
                pass


@app.post("/hits")
def hits():
    """POST /hits { audio_url|video_url|url, every? } -> kick/snare-aanslagen met
    onset-sterkte + (optioneel) downbeat-relatie. Analyse-only; wijzigt niets."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    drive_file_id = b.get("drive_file_id")
    url = b.get("audio_url") or b.get("video_url") or b.get("url")
    if not drive_file_id and not url:
        return jsonify(error="geen drive_file_id of url"), 400
    src = tempfile.NamedTemporaryFile(delete=False, suffix=".in").name
    try:
        if drive_file_id:
            _download_drive_api(drive_file_id, src)   # Drive-native (voorkeur, geen publieke link)
        else:
            download(url, src)                        # fallback: publieke/Drive-URL
        detailed = FX.detect_hits_detailed(src)
        try:
            _dur, tempo, bt = detect_beats(src)
            every = int(b.get("every", 4))
            downbeats = bt[::max(1, every)].tolist()
        except Exception:
            tempo, downbeats = None, []

        def annotate(lst):
            out = []
            for h in lst:
                nb = round(min(downbeats, key=lambda d: abs(d - h["t"])) - h["t"], 3) if downbeats else None
                out.append({**h, "nearest_downbeat_offset": nb})
            return out

        return jsonify(version=APP_VERSION,
                       duration=detailed["duration"],
                       bpm=(round(tempo, 1) if tempo else None),
                       downbeats=[round(float(x), 3) for x in downbeats],
                       counts={"kick": len(detailed["kick"]), "snare": len(detailed["snare"])},
                       kick=annotate(detailed["kick"]),
                       snare=annotate(detailed["snare"]))
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass


@app.post("/beats")
def beats():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    every = int(request.args.get("every") or body.get("every") or 4)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        if "file" in request.files:
            request.files["file"].save(tmp.name)
        else:
            url = body.get("audio_url") or request.form.get("audio_url")
            if not url:
                return jsonify(error="geen audio_url of file"), 400
            download(url, tmp.name)
        dur, tempo, bt = detect_beats(tmp.name)
        downbeats = bt[::max(1, every)].tolist()
        return jsonify(duration=round(dur, 1), bpm=round(float(tempo), 1),
                       num_beats=len(bt), beats=bt.tolist(),
                       downbeats=downbeats, every=every)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@app.post("/prep")
def prep():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    video_url = body.get("video_url")
    audio_url = body.get("audio_url")
    if not video_url:
        return jsonify(error="geen video_url"), 400
    vid = tempfile.NamedTemporaryFile(delete=False, suffix=".vin").name
    aud = tempfile.NamedTemporaryFile(delete=False, suffix=".ain").name if audio_url else None
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    tmps = [vid, out] + ([aud] if aud else [])
    try:
        download(video_url, vid)
        if audio_url:
            download(audio_url, aud)
        prep_media(vid, aud, out)
        obj = f"prepped/{uuid.uuid4().hex}.mp4"
        url = _upload_gcs(out, obj)
        size_mb = round(os.path.getsize(out) / (1 << 20), 1)
        return jsonify(url=url, bucket=BUCKET_NAME, object=obj,
                       size_mb=size_mb, duration=_ffprobe_duration(out))
    except subprocess.CalledProcessError as e:
        return jsonify(error=f"ffmpeg-fout: {e}"), 500
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in tmps:
            try:
                os.unlink(p)
            except OSError:
                pass


# ============================================================================
#  /visualizer  — audio-visualizer voor bestaande nummers (4 stijlen + rotatie)
#  POST { photo_url, audio_url, title, style?, start?, duration?, subtitle? }
#    style: "A"|"B"|"C"|"D" of "auto" (+ index) of laat weg -> gebruik `index`
#    -> { url, bucket, object, style, size_mb, duration }
#  Titel-hoogte staat in de veilige TikTok-zone (vrij van caption/knoppen).
# ============================================================================

def rotate_style(index):
    return STYLE_ORDER[int(index) % len(STYLE_ORDER)]


def _textfile(text):
    f = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8")
    f.write(text or "")
    f.close()
    return f.name


def _detect_black_tail(video, start, dur, pix_th=0.10, min_black=0.30):
    """Detecteer een aaneengesloten ZWARTE staart aan het eind van [start, start+dur].
    Retourneert de nieuwe duur (= begin van de trailing black) of de originele dur als
    er geen zwarte staart is. Puur meten (blackdetect), verandert niets."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start > 0.0:
        cmd += ["-ss", "%.3f" % start]
    cmd += ["-t", "%.3f" % dur, "-i", video,
            "-vf", "blackdetect=d=%.2f:pix_th=%.2f" % (min_black, pix_th),
            "-an", "-f", "null", "-"]
    r = subprocess.run(cmd, stderr=subprocess.PIPE)
    txt = r.stderr.decode(errors="replace")
    last = None
    for m in re.finditer(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)", txt):
        last = (float(m.group(1)), float(m.group(2)))
    if last and (dur - last[1] < 0.5):   # trailing black loopt tot (bijna) het einde
        return max(0.0, round(last[0], 3))
    return dur


def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _sha256_file(path):
    import hashlib
    hsh = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hsh.update(chunk)
    return hsh.hexdigest()


def _render_text_png(text, font_path, size_px, tracking_millieme, color_hex,
                     shadow=True, pad=48):
    """Rendert 1 regel tekst met echte letter-tracking + drop-shadow naar een
    transparante PNG (drawtext kan geen tracking). Retourneert (path, W, H)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    font = ImageFont.truetype(font_path, size_px)
    asc, desc = font.getmetrics()
    tpx = (tracking_millieme / 1000.0) * size_px
    chars = list(text)
    widths = [font.getlength(c) for c in chars]
    text_w = sum(widths) + tpx * max(0, len(chars) - 1)
    text_h = asc + desc
    W = int(math.ceil(text_w)) + 2 * pad
    H = int(math.ceil(text_h)) + 2 * pad
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def _draw(layer_color, x0, y0):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x = x0
        for c, w in zip(chars, widths):
            d.text((x, y0), c, font=font, fill=layer_color)
            x += w + tpx
        return lay

    if shadow:
        sh = _draw((0, 0, 0, 255), pad, pad + 3)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        # schaal alpha naar 60%
        a = sh.split()[3].point(lambda v: int(v * 0.60))
        sh.putalpha(a)
        img = Image.alpha_composite(img, sh)
    r, g, b = _hex_rgb(color_hex)
    main = _draw((r, g, b, 255), pad, pad)
    img = Image.alpha_composite(img, main)
    outp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(outp)
    return outp, W, H


def _scaled_image_png(src_png, target_w):
    """Schaal een asset-PNG naar target breedte (aspect behouden). Retourneert (path,W,H)."""
    from PIL import Image
    im = Image.open(src_png).convert("RGBA")
    w, h = im.size
    nh = max(1, int(round(h * (target_w / float(w)))))
    im = im.resize((int(target_w), nh), Image.LANCZOS)
    outp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    im.save(outp)
    return outp, int(target_w), nh


def build_clean_cues(video, out, cues, audio=None, fps=24, start=0.0, dur=None,
                     copy_audio_from=None, color_filters=None, trim_black_tail=False):
    """CLEAN MODE + cues[]-executor: geen branding/intro/outro/logo/titels — alleen
    de gefilmde clip (1080x1920, -14 LUFS) met de goedgekeurde cue-effecten
    (shake/vshake/zoom/zoomramp/pullout/flash). Aparte functie: raakt build_clip niet aan.

    copy_audio_from: pad naar een bestaande render (bv. V01/V02). Is dit gezet, dan wordt de
    audiostream daarvan BYTE-IDENTIEK gekopieerd (-c:a copy, geen loudnorm/fades).
    color_filters: optionele ffmpeg-filterketen (bv. curves+colorbalance) die na scale/crop
      wordt ingevoegd — een subtiele color-polish, GEEN nieuwe grade.
    trim_black_tail: knip een zwarte staart aan het eind weg (video + audio), gedocumenteerd.
    Retourneert een dict met trim/color-info voor de respons."""
    d = float(dur) if dur else (_ffprobe_duration(video) - float(start or 0.0))
    start = float(start or 0.0)
    # Bij byte-identieke audio-copy is de bron-render leidend voor de lengte.
    if copy_audio_from:
        d = _ffprobe_duration(copy_audio_from)
    old_end = round(d, 3)
    trim_info = {"trimmed": False, "old_end": old_end, "new_end": old_end, "removed": 0.0}
    if trim_black_tail:
        nd = _detect_black_tail(video, start, d)
        if nd < d - 0.05:
            trim_info = {"trimmed": True, "old_end": old_end, "new_end": round(nd, 3),
                         "removed": round(d - nd, 3)}
            d = nd
    base = ["ffmpeg", "-v", "error", "-y"]
    if start > 0.0:
        base += ["-ss", "%.3f" % start]
    base += ["-t", "%.3f" % d, "-i", video]
    idx = 1
    aud_ref = "[0:a]"
    if audio:
        base += ["-i", audio]; aud_ref = "[%d:a]" % idx; idx += 1
    copy_a_idx = None
    if copy_audio_from:
        base += ["-i", copy_audio_from]; copy_a_idx = idx; idx += 1
    color_seg = ("," + color_filters) if color_filters else ""
    fc = ("[0:v]fps=%d,scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1%s[fxin];" % (fps, color_seg))
    fxfilt, flashes = FX.fx_from_cues(cues or [], fps=fps, in_label="fxin", out_label="vfx")
    fc += fxfilt + ";"
    cur = "vfx"
    # Flash: per-frame witte overlays met exacte opacity. Elke opacity = precies 1 frame,
    # consecutief vanaf ft. Constante alpha via colorchannelmixer + harde 1-frame enable-gate
    # -> geen fade-in, geen naijlend/melkachtig wit, exact aantal frames.
    frame = 1.0 / fps
    for i, (ft, ops) in enumerate(flashes):
        for j, op in enumerate(ops):
            op = max(0.0, min(1.0, float(op)))
            if op <= 0.0:
                continue
            tt = ft + j * frame
            base += ["-f", "lavfi", "-i", "color=c=white:s=1080x1920:r=%d:d=%.3f" % (fps, d)]
            fi = idx; idx += 1
            fc += "[%d:v]format=yuva420p,colorchannelmixer=aa=%.3f[wf%d_%d];" % (fi, op, i, j)
            fc += ("[%s][wf%d_%d]overlay=0:0:enable='between(t\\,%.4f\\,%.4f)'[flo%d_%d];"
                   % (cur, i, j, tt, tt + frame - 0.001, i, j))
            cur = "flo%d_%d" % (i, j)
    fc += "[%s]null[vo];" % cur
    if copy_a_idx is not None:
        # audio byte-identiek uit de bronrender; geen filtergraph op audio.
        # Zonder tail-trim GEEN output -t (anders sneuvelt het laatste AAC-frame).
        # MET tail-trim wel output -t d: video + audio worden op de nieuwe (kortere) duur
        # afgekapt — het verwijderde stuk is de zwarte/stille staart (gedocumenteerd).
        fc = fc.rstrip(";")
        cmd = base + ["-filter_complex", fc, "-map", "[vo]", "-map", "%d:a:0" % copy_a_idx,
                      "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                      "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart"]
        if trim_info.get("trimmed"):
            cmd += ["-t", "%.3f" % d]
        cmd += [out]
    else:
        afo = max(0.0, d - 0.8)
        fc += ("%sloudnorm=I=%s:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.3,"
               "afade=t=out:st=%.2f:d=0.6[ao]" % (aud_ref, LUFS, afo))
        cmd = base + ["-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
                      "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                      "-movflags", "+faststart", "-t", "%.3f" % d, "-shortest", out]
    r = subprocess.run(cmd, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.decode(errors="replace")[-800:])
    trim_info["color_applied"] = bool(color_filters)
    trim_info["effective_duration"] = round(d, 3)
    return trim_info


def build_clip(video, out, audio=None, hook_text=None, brand_text=None, hook_y=None,
               intro_png=None, intro_dur=3.0,
               lyric_pngs=None, lyric_times=None,
               kicks=None, snares=None, fps=24,
               kick_zoom=0.038, snare_shake=0.010, fx=True, start=0.0, dur=None):
    """Render een gebrande, beat-synced social-clip uit een gefilmde opname.
    Video -> 1080x1920/fps -> beat-synced zoom-punch(kick)+shake(snare) -> ketting-logo
    -> hook-tekst (eerste ~2,8s) -> end-card (>=8s) -> lyrics-pills. Audio: losse
    studio-bed (of bron), loudnorm -14 LUFS + fades. Eén ffmpeg-pass.
    start/dur: nauwkeurig knippen op de input (timeline reset naar 0, sync blijft kloppen).
    """
    d = float(dur) if dur else (_ffprobe_duration(video) - float(start or 0.0))
    start = float(start or 0.0)
    base = ["ffmpeg", "-v", "error", "-y"]
    if start > 0.0:
        base += ["-ss", "%.3f" % start]
    base += ["-t", "%.3f" % d, "-i", video]
    idx = 1
    aud_ref = "[0:a]"
    if audio:
        base += ["-i", audio]; aud_ref = "[%d:a]" % idx; idx += 1
    base += ["-i", LOGO_PATH]; logo_i = idx; idx += 1
    use_outro = (d >= 8.0 and os.path.exists(OUTRO_PATH))
    if use_outro:
        base += ["-loop", "1", "-i", OUTRO_PATH]; outro_i = idx; idx += 1
    intro_i = None
    if intro_png:
        base += ["-loop", "1", "-i", intro_png]; intro_i = idx; idx += 1
    pill_base = idx
    for p in (lyric_pngs or []):
        base += ["-loop", "1", "-i", p]; idx += 1

    tmp_txt = []
    # --- videoketen ---
    fc = ("[0:v]fps=%d,scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1[fxin];" % fps)
    if fx:
        fc += FX.fx_beat_filter(kicks or [], snares or [], fps=fps,
                                kick_zoom=kick_zoom, snare_shake=snare_shake,
                                in_label="fxin", out_label="vfx") + ";"
    else:
        fc += "[fxin]null[vfx];"
    # ketting-logo linksboven
    fc += "[%d:v]scale=280:-1[lg];[vfx][lg]overlay=44:60[vlogo];" % logo_i
    cur = "vlogo"
    # hook-tekst bovenin, eerste 2,8s
    if hook_text:
        hf = _textfile(hook_text.upper()); tmp_txt.append(hf)
        hy = str(hook_y) if hook_y not in (None, "", "center") else "(h-text_h)/2"
        # bij een intro-titel: hook pas ná de intro tonen (geen overlap met de titelkaart)
        he = ("between(t,%.2f,%.2f)" % (intro_dur + 0.2, intro_dur + 3.0)) if intro_png else "lt(t,2.8)"
        fc += ("[%s]drawtext=fontfile=%s:textfile=%s:fontcolor=white:fontsize=56:"
               "x=(w-text_w)/2:y=%s:box=1:boxcolor=black@0.38:boxborderw=20:"
               "enable='%s'[vhook];" % (cur, FONT_BOLD, hf, hy, he))
        cur = "vhook"
    # merk-regel onderin de laatste 2s (alleen als er geen end-card is)
    if brand_text and not use_outro:
        bf = _textfile(brand_text.upper()); tmp_txt.append(bf)
        bst = max(0.0, d - 2.0)
        fc += ("[%s]drawtext=fontfile=%s:textfile=%s:fontcolor=%s:fontsize=46:"
               "x=(w-text_w)/2:y=1620:enable='gte(t\\,%.2f)'[vbrand];"
               % (cur, FONT_BOLD, bf, GOLD, bst))
        cur = "vbrand"
    # end-card in de laatste seconden
    if use_outro:
        ost = max(0.0, d - OUTRO_DUR)
        fc += ("[%d:v]scale=1080:1920,format=rgba,fade=t=in:st=%.2f:d=0.6:alpha=1[ov];"
               "[%s][ov]overlay=0:0:enable='gte(t\\,%.2f)'[vend];" % (outro_i, ost, cur, ost))
        cur = "vend"
    # lyrics-pills als laag
    if lyric_pngs and lyric_times:
        fc += L.overlay_filter(cur, "vbody", len(lyric_pngs), pill_base, lyric_times) + ";"
    else:
        fc += "[%s]null[vbody];" % cur
    # intro-titelkaart (transparante PNG) over het begin, met fade-out
    if intro_i is not None:
        fo = max(0.0, float(intro_dur) - 0.5)
        fc += ("[%d:v]scale=1000:-1,format=rgba,"
               "fade=t=out:st=%.2f:d=0.5:alpha=1[introv];"
               "[vbody][introv]overlay=(W-w)/2:(H-h)/2:enable='lt(t,%.2f)'[vo];"
               % (intro_i, fo, float(intro_dur)))
    else:
        fc += "[vbody]null[vo];"
    # --- audio ---
    afo = max(0.0, d - 0.8)
    fc += ("%sloudnorm=I=%s:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.3,"
           "afade=t=out:st=%.2f:d=0.6[ao]" % (aud_ref, LUFS, afo))
    if fc.endswith(";"):
        fc = fc[:-1]

    cmd = base + ["-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
                  "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                  "-movflags", "+faststart", "-t", "%.3f" % d, "-shortest", out]
    try:
        r = subprocess.run(cmd, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg: " + r.stderr.decode(errors="replace")[-800:])
    finally:
        for p in tmp_txt:
            try:
                os.unlink(p)
            except OSError:
                pass


@app.post("/clip")
def clip():
    """POST /clip { video_url, audio_url?, hook_text?, brand_text?, song?, lyrics_url?,
                    kick_zoom?, snare_shake?, fx? (bool), start?, duration? }
    -> gebrande, beat-synced social-clip (1080x1920) in GCS. """
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    b = request.get_json(silent=True) or {}
    video_url = b.get("video_url")
    drive_file_id = b.get("drive_file_id")
    if not video_url and not drive_file_id:
        return jsonify(error="geen video_url of drive_file_id"), 400
    audio_url = b.get("audio_url")
    audio_drive_id = b.get("audio_drive_id")
    intro_url = b.get("intro_url")
    vid = tempfile.NamedTemporaryFile(delete=False, suffix=".vin").name
    aud = tempfile.NamedTemporaryFile(delete=False, suffix=".ain").name if (audio_url or audio_drive_id) else None
    intro = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name if intro_url else None
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    # audio byte-identiek kopiëren uit een bestaande render (bv. V01)
    audio_copy_url = b.get("audio_copy_url")
    audio_copy_drive_id = b.get("audio_copy_drive_id")
    acopy = tempfile.NamedTemporaryFile(delete=False, suffix=".acp.mp4").name if (audio_copy_url or audio_copy_drive_id) else None
    pills = []
    tmps = [vid, out] + ([aud] if aud else []) + ([intro] if intro else []) + ([acopy] if acopy else [])
    # --- optionele Drive self-save (v11) -----------------------------------
    # save_to_drive: bool ; drive_folder_id ; output_filename ; allow_version?
    _save = bool(b.get("save_to_drive"))
    _folder = b.get("drive_folder_id")
    _outname = b.get("output_filename")
    def _do_drive_save():
        """Uploadt de zojuist gerenderde `out` naar Drive volgens veilige regels.
        Retourneert een dict om in de JSON-respons te mergen (altijd onder key 'drive')."""
        if not _save:
            return {}
        if not (_folder and _outname):
            return {"drive": {"uploaded": False,
                              "error": "save_to_drive vereist drive_folder_id + output_filename"}}
        try:
            r = _upload_to_drive(out, _folder, _outname, mime="video/mp4",
                                 allow_version=bool(b.get("allow_version", False)))
            return {"drive": r}
        except Exception as e:
            return {"drive": {"uploaded": False, "error": str(e)}}
    try:
        if drive_file_id:
            _download_drive_api(drive_file_id, vid)
        else:
            download(video_url, vid)
        if audio_drive_id:
            _download_drive_api(audio_drive_id, aud)
        elif audio_url:
            download(audio_url, aud)
        if intro_url:
            download(intro_url, intro)
        if audio_copy_drive_id:
            # zelfde bron als de video? hergebruik de reeds gedownloade file (geen dubbele download)
            if drive_file_id and audio_copy_drive_id == drive_file_id:
                acopy = vid
            else:
                _download_drive_api(audio_copy_drive_id, acopy)
        elif audio_copy_url:
            download(audio_copy_url, acopy)
        full_dur = _ffprobe_duration(vid)
        start = float(b.get("start") or 0.0)
        dur = float(b.get("duration") or (full_dur - start))
        # --- CLEAN MODE + cues[] executor (backwards-compatible; branded path unchanged) ---
        if bool(b.get("clean")) and b.get("cues"):
            _polish = build_clean_cues(vid, out, cues=b["cues"], audio=aud, start=start, dur=dur,
                                       copy_audio_from=acopy,
                                       color_filters=b.get("color_filters"),
                                       trim_black_tail=bool(b.get("trim_black_tail")))
            obj = f"clips/{uuid.uuid4().hex}.mp4"
            url = _upload_gcs(out, obj)
            preview_url = None
            try:
                prev = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                tmps.append(prev)
                _make_contact_sheet(out, prev)
                preview_url = _upload_gcs(prev, obj[:-4] + "_preview.jpg", "image/jpeg")
            except Exception:
                preview_url = None
            return jsonify(url=url, preview_url=preview_url, bucket=BUCKET_NAME, object=obj,
                           size_mb=round(os.path.getsize(out) / (1 << 20), 1),
                           duration=_ffprobe_duration(out), clean=True,
                           audio_copied=bool(acopy), polish=_polish,
                           cues=len(b["cues"]), version=APP_VERSION, **_do_drive_save())
        # beat-detectie op de (studio-)audio die onder de clip komt
        fxon = bool(b.get("fx", True))
        kicks = snares = []
        if fxon:
            hits = FX.detect_hits(aud or vid)
            kicks = FX.thin(FX.shift_and_window(hits["kick"], start, dur),
                            min_gap=float(b.get("kick_gap", 0.40)), max_count=40)
            snares = FX.thin(FX.shift_and_window(hits["snare"], start, dur),
                             min_gap=float(b.get("snare_gap", 0.32)), max_count=40)
        # lyrics (optioneel)
        lyric_pngs = lyric_times = None
        song = b.get("song"); lyrics_url = b.get("lyrics_url")
        if song or lyrics_url:
            lines, _ = _load_lyrics(lyrics_url=lyrics_url, song=song)
            if lines:
                lyric_pngs, lyric_times = _make_pill_pngs(lines, start, dur)
                pills = list(lyric_pngs)
        build_clip(vid, out, audio=aud,
                   hook_text=b.get("hook_text"), brand_text=b.get("brand_text"),
                   hook_y=b.get("hook_y"),
                   intro_png=intro, intro_dur=float(b.get("intro_dur", 3.0)),
                   lyric_pngs=lyric_pngs, lyric_times=lyric_times,
                   kicks=kicks, snares=snares,
                   kick_zoom=float(b.get("kick_zoom", 0.038)),
                   snare_shake=float(b.get("snare_shake", 0.010)),
                   fx=fxon, start=start, dur=dur)
        obj = f"clips/{uuid.uuid4().hex}.mp4"
        url = _upload_gcs(out, obj)
        preview_url = None
        try:
            prev = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
            tmps.append(prev)
            _make_contact_sheet(out, prev)
            preview_url = _upload_gcs(prev, obj[:-4] + "_preview.jpg", "image/jpeg")
        except Exception:
            preview_url = None
        return jsonify(url=url, preview_url=preview_url, bucket=BUCKET_NAME, object=obj,
                       size_mb=round(os.path.getsize(out) / (1 << 20), 1),
                       duration=_ffprobe_duration(out),
                       kicks=len(kicks), snares=len(snares),
                       intro=bool(intro), version=APP_VERSION, **_do_drive_save())
    except subprocess.CalledProcessError as e:
        return jsonify(error=f"ffmpeg-fout: {e}"), 500
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in tmps + pills:
            try:
                os.unlink(p)
            except OSError:
                pass


def _titlefile(text):
    """Schrijf songtitel naar tmp-bestand (textfile= voorkomt drawtext-escaping)."""
    f = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8")
    f.write((text or "").upper())
    f.close()
    return f.name


def _title_draw(subtitle_file, title_file):
    """Twee drawtext-regels onderin (veilige zone). Zelfde voor alle stijlen."""
    return (
        "drawtext=fontfile=%s:textfile=%s:fontcolor=%s:fontsize=42:"
        "x=(w-text_w)/2:y=1500,"
        "drawtext=fontfile=%s:textfile=%s:fontcolor=white:fontsize=92:"
        "x=(w-text_w)/2:y=1550"
        % (FONT_MED, subtitle_file, GOLD, FONT_BOLD, title_file)
    )


def build_visualizer(style, photo, audio, out, start, dur, title, subtitle,
                     lyric_pngs=None, lyric_times=None):
    """Bouw ffmpeg-commando voor de gekozen stijl (A/B/C/D). Recepten bewezen 10 jul.
    lyric_pngs/lyric_times (optioneel): getimede ondertitel-pills die als laatste stap
    over het beeld worden gelegd (stijl B). Leeg = exact ongewijzigd gedrag."""
    sub_f = _titlefile(subtitle or "NOW PLAYING")
    ttl_f = _titlefile(title or "")
    title_dt = _title_draw(sub_f, ttl_f)
    base = ["ffmpeg", "-v", "error", "-y",
            "-loop", "1", "-i", photo,
            "-ss", str(start), "-t", str(dur), "-i", audio,
            "-i", LOGO_PATH]

    if style == "A":  # golflijn
        fc = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[b0];"
            "[b0]drawbox=x=0:y=1120:w=1080:h=350:color=black@0.42:t=fill[bg];"
            "[1:a]showwaves=s=1080x300:mode=cline:colors=%s:draw=full,format=rgba,colorkey=0x000000:0.14:0.06[wv];"
            "[bg][wv]overlay=0:1140[c1];"
            "[2:v]scale=520:-1[lg];[c1][lg]overlay=(W-w)/2:110[c2];"
            "[c2]%s[vo]" % (GOLD, title_dt)
        )
    elif style == "D":  # spectrum (schone spiky golf i.p.v. troebele showfreqs)
        fc = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[b0];"
            "[b0]drawbox=x=0:y=1120:w=1080:h=350:color=black@0.42:t=fill[bg];"
            "[1:a]showwaves=s=1080x320:mode=p2p:colors=%s:draw=full,"
            "format=rgba,colorkey=0x000000:0.14:0.06[wv];"
            "[bg][wv]overlay=0:1130[c1];"
            "[2:v]scale=520:-1[lg];[c1][lg]overlay=(W-w)/2:110[c2];"
            "[c2]%s[vo]" % (GOLD, title_dt)
        )
    elif style == "B":  # foto in gouden kader + schone spiky equalizer
        fc = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
            "boxblur=28:2,eq=brightness=-0.10[bg];"
            "[0:v]scale=840:900:force_original_aspect_ratio=increase,crop=840:900,setsar=1,"
            "pad=856:916:8:8:color=%s[fr];"
            "[bg][fr]overlay=(W-w)/2:280[c0];"
            "[1:a]showwaves=s=856x300:mode=p2p:colors=%s:draw=full,"
            "format=rgba,colorkey=0x000000:0.14:0.06[wv];"
            "[c0][wv]overlay=(W-w)/2:1220[c1];"
            "[2:v]scale=500:-1[lg];[c1][lg]overlay=(W-w)/2:90[c2];"
            "[c2]%s[vo]" % (GOLD, GOLD, title_dt)
        )
    elif style == "C":  # radiaal (ronde foto + gouden ring + reactieve halo)
        # inputs 3 = rond masker, 4 = gouden ring (voorgerekend -> geen trage geq meer)
        base += ["-i", CIRCLE_MASK, "-i", RING_IMG]
        fc = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
            "boxblur=30:2,eq=brightness=-0.14[bg];"
            "[0:v]scale=720:720:force_original_aspect_ratio=increase,crop=720:720,setsar=1[phc];"
            "[phc][3:v]alphamerge[circ];"
            "[1:a]avectorscope=s=1040x1040:mode=polar:rc=210:gc=170:bc=45:draw=dot:zoom=1.15:scale=sqrt,"
            "format=rgba,colorchannelmixer=aa=0.85[sc];"
            "[bg][sc]overlay=(W-w)/2:440[c0];"
            "[c0][4:v]overlay=(W-w)/2:520[c0b];"
            "[c0b][circ]overlay=(W-w)/2:560[c1];"
            "[2:v]scale=440:-1[lg];[c1][lg]overlay=(W-w)/2:100[c2];"
            "[c2]%s[vo]" % title_dt
        )
    else:
        raise ValueError("onbekende style: %s (kies A/B/C/D)" % style)

    # --- fades: beeld hard erin + korte fade-out; audio 0.4s in / 0.8s uit ---
    d = max(0.6, float(dur))
    afo = max(0.0, d - 0.8)          # audio fade-out start
    vfo = max(0.0, d - 0.5)          # beeld fade-out start
    fc = fc.replace("[1:a]", "[aa]")  # visualizer-tak gebruikt de gesplitste audio
    # audio: loudness naar social-standaard (-14 LUFS) + fades
    apre = ("[1:a]asplit=2[aa][ab];"
            "[ab]loudnorm=I=%s:TP=-1.5:LRA=11,"
            "afade=t=in:st=0:d=0.4,afade=t=out:st=%.2f:d=0.8[ao];" % (LUFS, afo))
    if fc.endswith("[vo]"):
        fc = fc[:-4]
    # end-card met de socials in de laatste seconden (alleen bij clips >= 8s)
    if d >= 8.0 and os.path.exists(OUTRO_PATH):
        ost = max(0.0, d - OUTRO_DUR)
        base.extend(["-loop", "1", "-i", OUTRO_PATH])   # input 3
        fc = (apre
              + "[3:v]scale=1080:1920,format=rgba,"
                "fade=t=in:st=%.2f:d=0.6:alpha=1[ov];" % ost
              + fc + "[c9];"
              + "[c9][ov]overlay=0:0:enable='gte(t,%.2f)'[c10];" % ost
              + "[c10]fade=t=out:st=%.2f:d=0.5[vo]" % vfo)
    else:
        fc = apre + fc + (",fade=t=out:st=%.2f:d=0.5" % vfo) + "[vo]"

    # --- ondertitel-pills als laatste laag (getimede PNG-overlays, stijl B) ---
    if lyric_pngs and lyric_times and fc.endswith("[vo]"):
        idx0 = base.count("-i")                 # pill-inputs komen ná alle bestaande inputs
        for p in lyric_pngs:
            base.extend(["-loop", "1", "-i", p])
        fc = fc[:-4] + "[vbeforelyr];" + \
            L.overlay_filter("vbeforelyr", "vo", len(lyric_pngs), idx0, lyric_times)

    cmd = base + ["-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
                  "-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                  "-movflags", "+faststart", "-t", "%.3f" % d, "-shortest", out]
    try:
        subprocess.run(cmd, check=True)
    finally:
        for p in (sub_f, ttl_f):
            try:
                os.unlink(p)
            except OSError:
                pass


# --- lyrics-opslag (GCS) + laden voor /visualizer -------------------------------
def _lyrics_blob(song):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", song or "")[:100] or "x"
    from google.cloud import storage
    return storage.Client().bucket(BUCKET_NAME).blob(f"lyrics/{safe}.json")


def _load_lyrics(lyrics_url=None, song=None):
    """Laad lyrics-json (directe URL of GCS o.b.v. song). Retourneert
    (lines, status) met lines=[{start,end,text}] over het HELE nummer.
    Bij fout/afwezig: ([], None) -> /visualizer rendert gewoon zonder ondertitels."""
    data = None
    try:
        if lyrics_url:
            r = requests.get(lyrics_url, timeout=30)
            r.raise_for_status()
            data = r.json()
        elif song:
            b = _lyrics_blob(song)
            if b.exists():
                data = json.loads(b.download_as_text())
    except Exception:
        return [], None
    if not isinstance(data, dict):
        return [], None
    lines = []
    for ln in (data.get("lines") or []):
        try:
            s = float(ln["start"]); e = float(ln["end"])
        except (KeyError, TypeError, ValueError):
            continue
        txt = (ln.get("roman") or ln.get("text") or "").strip()
        if txt and e > s:
            lines.append({"start": s, "end": e, "text": txt})
    return lines, data.get("status")


LYRIC_LEAD_IN = float(os.environ.get("LYRIC_LEAD_IN") or 1.0)   # start ondertitels pas na N sec


def _make_pill_pngs(lines, start, dur):
    """Filter de regels op dit fragment, verschuif de tijden en render pill-PNG's.
    Retourneert (png_paths, times) — times in fragment-tijd (0..dur).
    Lead-in: eerste seconde geen ondertitel. Outro-guard: tijdens de end-card (laatste
    OUTRO_DUR sec, alleen bij clips >= 8s) geen ondertitel over de outro-tekst."""
    d = max(0.6, float(dur))
    tail_guard = OUTRO_DUR if (d >= 8.0 and os.path.exists(OUTRO_PATH)) else 0.0
    frag = L.lines_for_fragment(lines, start, dur, lead_in=LYRIC_LEAD_IN, tail_guard=tail_guard)
    paths, times = [], []
    for ln in frag:
        p = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        L.render_line_png(ln["text"], p, FONT_BOLD)
        paths.append(p)
        times.append((ln["start"], ln["end"]))
    return paths, times


@app.post("/visualizer")
def visualizer():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    photo_url = body.get("photo_url")
    audio_url = body.get("audio_url")
    if not photo_url or not audio_url:
        return jsonify(error="photo_url en audio_url vereist"), 400
    style = (body.get("style") or "").strip().upper()
    if style in ("", "AUTO"):
        style = rotate_style(body.get("index") or 0)
    if style not in STYLE_ORDER:
        return jsonify(error="style moet A/B/C/D of auto zijn"), 400
    start = float(body.get("start") or 0)
    dur = float(body.get("duration") or 15)
    title = body.get("title") or ""
    subtitle = body.get("subtitle") or "NOW PLAYING"
    # --- lyrics (optioneel): laad hele-song regels, alleen approved tenzij uitgezet ---
    lyrics_url = body.get("lyrics_url")
    song = body.get("song")
    require_approved = str(body.get("require_approved", "1")).lower() not in ("0", "false", "no")
    lyric_pngs, lyric_times = [], []
    if lyrics_url or song:
        lines, status = _load_lyrics(lyrics_url, song)
        if lines and (status == "approved" or not require_approved):
            lyric_pngs, lyric_times = _make_pill_pngs(lines, start, dur)
    ph = tempfile.NamedTemporaryFile(delete=False, suffix=".img").name
    au = tempfile.NamedTemporaryFile(delete=False, suffix=".aud").name
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    tmps = [ph, au, out] + lyric_pngs
    try:
        download(photo_url, ph)
        download(audio_url, au)
        build_visualizer(style, ph, au, out, start, dur, title, subtitle,
                         lyric_pngs=lyric_pngs or None, lyric_times=lyric_times or None)
        obj = f"visualizer/{uuid.uuid4().hex}.mp4"
        url = _upload_gcs(out, obj)
        size_mb = round(os.path.getsize(out) / (1 << 20), 1)
        return jsonify(url=url, bucket=BUCKET_NAME, object=obj, style=style,
                       size_mb=size_mb, duration=_ffprobe_duration(out),
                       lyric_lines=len(lyric_times))
    except subprocess.CalledProcessError as e:
        return jsonify(error=f"ffmpeg-fout: {e}"), 500
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in tmps:
            try:
                os.unlink(p)
            except OSError:
                pass


# ============================================================================
#  /transcribe — Whisper (segment-timings) + romaniseren -> lyrics/<song>.json
#  POST { song, audio_url }  ->  { song, status:"draft", n_lines, lines:[...] }
#  Model: gpt-4o-transcribe (language=hi, verbose_json, segment-timestamps).
#  Romaniseren: gpt-4o-mini (Devanagari -> leesbaar Hinglish), 1 call voor alle regels.
#  Slaat lyrics/<song>.json op (status draft) -> daarna review via /lyricsreview.
# ============================================================================

def _openai_transcribe(audio_path):
    """OpenAI transcriptie met segment-timestamps. Retourneert [{start,end,text}] (Devanagari)."""
    with open(audio_path, "rb") as fh:
        files = {"file": ("audio.mp3", fh, "application/octet-stream")}
        data = {"model": TRANSCRIBE_MODEL, "language": "hi",
                "response_format": "verbose_json", "timestamp_granularities[]": "segment"}
        r = requests.post("https://api.openai.com/v1/audio/transcriptions",
                          headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                          files=files, data=data, timeout=600)
    r.raise_for_status()
    return L.parse_whisper_segments(r.json())


def _openai_romanize(texts):
    """Zet een lijst Devanagari-regels om naar leesbaar Hinglish (Latijn). 1 chat-call.
    Retourneert een even lange lijst; bij twijfel valt hij terug op de invoer."""
    if not texts:
        return []
    sys_msg = ("Je romaniseert Hindi/Urdu songteksten naar leesbaar Hinglish (Latijns schrift). "
               "Behoud betekenis en klank, natuurlijke spelling zoals fans het schrijven. "
               "Vertaal NIET naar het Engels. Antwoord met UITSLUITEND een JSON-array van strings, "
               "even lang als de invoer, zelfde volgorde.")
    payload = {"model": ROMANIZE_MODEL, "temperature": 0,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": sys_msg},
                            {"role": "user", "content": json.dumps({"lines": texts}, ensure_ascii=False)}]}
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer {OPENAI_KEY}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=120)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        obj = json.loads(content)
        out = obj.get("lines") if isinstance(obj, dict) else obj
        if isinstance(out, list) and len(out) == len(texts):
            return [str(x).strip() or texts[i] for i, x in enumerate(out)]
    except Exception:
        pass
    return list(texts)  # fail-safe: originele tekst (review vangt het op)


@app.post("/transcribe")
def transcribe():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    if not OPENAI_KEY:
        return jsonify(error="OPENAI_API_KEY niet gezet"), 500
    body = request.get_json(silent=True) or {}
    song = body.get("song") or ""
    audio_url = body.get("audio_url")
    if not song or not audio_url:
        return jsonify(error="song en audio_url vereist"), 400
    au = tempfile.NamedTemporaryFile(delete=False, suffix=".aud").name
    try:
        download(audio_url, au)
        segs = _openai_transcribe(au)                 # Devanagari + tijden
        lines = L.regroup_lines(segs)                 # nette regels (<=~42 tekens)
        roman = _openai_romanize([ln["text"] for ln in lines])
        out_lines = [{"start": ln["start"], "end": ln["end"],
                      "roman": roman[i], "dev": ln["text"]}
                     for i, ln in enumerate(lines)]
        data = {"song": song, "status": "draft", "lang": "hi", "lines": out_lines}
        _lyrics_blob(song).upload_from_string(
            json.dumps(data, ensure_ascii=False), content_type="application/json")
        return jsonify(song=song, status="draft", n_lines=len(out_lines), lines=out_lines)
    except requests.HTTPError as e:
        return jsonify(error=f"OpenAI-fout: {e}"), 502
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try:
            os.unlink(au)
        except OSError:
            pass


# ============================================================================
#  /wordtimings — karaoke woord-timings uit OpusClip (voor N0-C2)
# ============================================================================
_WT_SKIP = ("__silence", "__missing", "__visual", "")


def _wt_flatten(clip):
    tr = (clip.get("timeRanges") or [[0, 0]])[0]
    clip_start = (tr[0] or 0) / 1000.0
    out = []
    sp = clip.get("screenplay") or {}
    chapters = sp.get("chapters") or ([sp] if sp.get("lines") else [])
    for ch in chapters:
        for line in (ch.get("lines") or []):
            for w in (line.get("words") or []):
                t = (w.get("text") or "").strip()
                if t in _WT_SKIP or t.startswith("__"):
                    continue
                wr = w.get("tr") or [0, 0]
                s = round(max(0.0, wr[0] - clip_start), 3)
                e = round(max(s, wr[1] - clip_start), 3)
                out.append({"w": t, "s": s, "e": e})
    return out


def _wt_clip(c):
    tr = (c.get("timeRanges") or [[0, 0]])[0]
    words = _wt_flatten(c)
    return {
        "clip_id": c.get("id"),
        "start": round((tr[0] or 0) / 1000.0, 3),
        "end": round((tr[1] or 0) / 1000.0, 3),
        "words": words,
        "words_json": json.dumps(words, ensure_ascii=False, separators=(",", ":")),
    }


@app.post("/wordtimings")
def wordtimings():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    pid = body.get("project_id")
    key = body.get("opus_key")
    want = body.get("clip_id")
    if not pid or not key:
        return jsonify(error="project_id en opus_key vereist"), 400
    r = requests.get("https://api.opus.pro/api/exportable-clips",
                     params={"q": "findByProjectId", "projectId": pid},
                     headers={"Authorization": f"Bearer {key}"}, timeout=60)
    r.raise_for_status()
    data = r.json().get("data") or []
    if want:
        for c in data:
            if c.get("id") == want:
                return jsonify(_wt_clip(c))
        return jsonify(error="clip_id niet gevonden", clip_id=want), 404
    return jsonify(clips=[_wt_clip(c) for c in data])


# ============================================================================
#  /cutform + /cutsubmit — Pijplijn 2: knipmomenten van een heel nummer opgeven
#  Nitin dropt nummer+foto -> intake-mail met link naar /cutform?song=<id>&title=..
#  Hij plakt de fragmenten (begin - eind per regel) -> /cutsubmit parse't robuust
#  en POST't {song_id, cuts:[{start,end,duration}]} naar de Make-webhook
#  (env MAKE_CUT_WEBHOOK). Make itereert en roept per fragment /visualizer aan.
# ============================================================================

def _to_sec(t):
    t = (t or "").strip()
    if not t:
        return None
    if ":" in t:
        try:
            bits = [float(b) for b in t.split(":")]
        except ValueError:
            return None
        if len(bits) == 2:
            return bits[0] * 60 + bits[1]
        if len(bits) == 3:
            return bits[0] * 3600 + bits[1] * 60 + bits[2]
        return None
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return None


def parse_cuts(text):
    """Vrije tekst -> lijst fragmenten. Snapt mm:ss of seconden, - of – als scheider,
    regels of komma's/puntkomma's als rij-scheiders. Ongeldige rijen worden genegeerd."""
    text = (text or "").replace("–", "-").replace("—", "-")
    cuts = []
    for part in re.split(r"[\n,;]+", text):
        part = part.strip()
        if not part:
            continue
        halves = re.split(r"\s*-\s*", part)
        if len(halves) != 2:
            continue
        s, e = _to_sec(halves[0]), _to_sec(halves[1])
        if s is None or e is None or e <= s:
            continue
        cuts.append({"idx": len(cuts), "start": round(s, 2), "end": round(e, 2),
                     "duration": round(e - s, 2)})
    return cuts


_CUTFORM_HTML = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Knipmomenten — Unchained Nitin</title>
<style>
 body{{margin:0;background:#0e1116;color:#f4f1e8;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
   display:flex;justify-content:center;padding:28px}}
 .card{{width:100%;max-width:520px}}
 h1{{color:#d4af37;font-size:22px;margin:0 0 4px}} .sub{{color:#aab4bf;font-size:14px;margin:0 0 18px}}
 .song{{color:#f4f1e8;font-weight:700}}
 textarea{{width:100%;box-sizing:border-box;min-height:170px;background:#1a2330;border:1px solid #3c4a59;
   border-radius:12px;color:#f4f1e8;font-size:16px;padding:14px;font-family:ui-monospace,Menlo,monospace}}
 .hint{{color:#8d99a6;font-size:13px;margin:8px 2px 18px;line-height:1.5}}
 button{{width:100%;background:#d4af37;color:#0e1116;font-size:17px;font-weight:700;border:0;
   border-radius:12px;padding:15px;cursor:pointer}}
 #msg{{margin-top:16px;font-size:15px;text-align:center}} .ok{{color:#7bd88f}} .err{{color:#e77}}
</style></head><body><div class="card">
 <h1>Knipmomenten invullen</h1>
 <p class="sub">Nummer: <span class="song">{title}</span></p>
 <textarea id="cuts" placeholder="0:15 - 0:35&#10;1:10 - 1:32&#10;2:05 - 2:24"></textarea>
 <p class="hint">Eén fragment per regel: <b>begin - eind</b>. Mag als <b>mm:ss</b> (1:10 - 1:32)
   of in seconden (15 - 35). De stijl wisselt automatisch per fragment.</p>
 <button onclick="send()">Versturen</button>
 <div id="msg"></div>
</div><script>
 async function send(){{
   var m=document.getElementById('msg'); m.textContent='Versturen...'; m.className='';
   try{{
     var r=await fetch('/cutsubmit',{{method:'POST',headers:{{'Content-Type':'application/json'}},
       body:JSON.stringify({{song:{song!r},cuts:document.getElementById('cuts').value}})}});
     var j=await r.json();
     if(r.ok){{m.textContent='✓ Ontvangen — '+j.num+' fragment(en). Je krijgt de visualizers zo ter review.';m.className='ok';}}
     else{{m.textContent='Er ging iets mis: '+(j.error||'onbekend');m.className='err';}}
   }}catch(e){{m.textContent='Netwerkfout, probeer opnieuw.';m.className='err';}}
 }}
</script></body></html>"""


@app.get("/cutform")
def cutform():
    song = request.args.get("song", "")
    title = request.args.get("title", "je nummer")
    html = _CUTFORM_HTML.format(title=title, song=song)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.post("/cutsubmit")
def cutsubmit():
    body = request.get_json(silent=True) or request.form
    song = body.get("song") or ""
    cuts = parse_cuts(body.get("cuts") or "")
    if not cuts:
        return jsonify(error="geen geldige knipmomenten gevonden"), 400
    hook = os.environ.get("MAKE_CUT_WEBHOOK")
    if hook:
        try:
            requests.post(hook, json={"song_id": song, "num": len(cuts), "cuts": cuts},
                          timeout=30)
        except Exception as e:
            return jsonify(error=f"kon niet doorsturen: {e}"), 502
    return jsonify(ok=True, num=len(cuts), cuts=cuts)


# ============================================================================
#  /review + /reviewsubmit — Pijplijn 2: caption + hashtags nakijken/aanpassen
#  V2 mailt een link naar /review?song=..&title=..&caption=<urlenc>&tags=<urlenc>
#  (caption/hashtags door AI gegenereerd). Nitin past evt. aan en klikt Goedkeuren
#  -> /reviewsubmit POST't {song, caption, hashtags} naar env MAKE_APPROVE_WEBHOOK
#  -> V3 plant de clips in met precies deze tekst.
# ============================================================================

_REVIEW_HTML = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review — Unchained Nitin</title>
<style>
 body{{margin:0;background:#0e1116;color:#f4f1e8;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
   display:flex;justify-content:center;padding:28px}}
 .card{{width:100%;max-width:560px}}
 h1{{color:#d4af37;font-size:22px;margin:0 0 4px}} .sub{{color:#aab4bf;font-size:14px;margin:0 0 18px}}
 .song{{color:#f4f1e8;font-weight:700}}
 .clip{{background:#141b25;border:1px solid #26303b;border-radius:14px;padding:14px;margin:14px 0}}
 .clip h3{{margin:0 0 8px;font-size:14px;color:#d4af37}} .clip a{{color:#7db8ff;font-size:13px;text-decoration:none}}
 label{{display:block;font-size:13px;color:#aab4bf;margin:16px 2px 6px}}
 textarea,input{{width:100%;box-sizing:border-box;background:#1a2330;border:1px solid #3c4a59;
   border-radius:12px;color:#f4f1e8;font-size:16px;padding:13px;font-family:inherit}}
 textarea{{min-height:82px}}
 .hint{{color:#8d99a6;font-size:13px;margin:6px 2px 4px;line-height:1.5}}
 button{{width:100%;margin-top:22px;background:#04b34f;color:#fff;font-size:17px;font-weight:700;border:0;
   border-radius:12px;padding:16px;cursor:pointer}}
 #msg{{margin-top:16px;font-size:15px;text-align:center}} .ok{{color:#7bd88f}} .err{{color:#e77}}
</style></head><body><div class="card">
 <h1>Clips nakijken &amp; goedkeuren</h1>
 <p class="sub">Nummer: <span class="song">{title}</span> — elke clip heeft een eigen AI-caption. Pas gerust aan.</p>
 <div id="clips"></div>
 <label>Hashtags (voor alle clips)</label>
 <input id="tags" value="{tags}">
 <p class="hint">Goedkeuren plant de visualizers in — één per dag om 18:00 op al je kanalen.
   Niks doen? Dan wordt er niets gepubliceerd.</p>
 <button onclick="send()">✅ Goedkeuren &amp; inplannen</button>
 <div id="msg"></div>
</div><script>
 var CAPS={captions_json}, URLS={urls_json};
 var box=document.getElementById('clips');
 CAPS.forEach(function(c,i){{
   var d=document.createElement('div'); d.className='clip';
   var link=URLS[i]?('<a href="'+URLS[i]+'" target="_blank">▶ bekijk clip '+(i+1)+'</a>'):'';
   d.innerHTML='<h3>Clip '+(i+1)+'</h3>'+link;
   var t=document.createElement('textarea'); t.value=c; t.id='cap'+i; d.appendChild(t); box.appendChild(d);
 }});
 async function send(){{
   var m=document.getElementById('msg'); m.textContent='Versturen...'; m.className='';
   var caps=CAPS.map(function(_,i){{return document.getElementById('cap'+i).value;}});
   try{{
     var r=await fetch('/reviewsubmit',{{method:'POST',headers:{{'Content-Type':'application/json'}},
       body:JSON.stringify({{song:{song!r},captions:caps,hashtags:document.getElementById('tags').value}})}});
     var j=await r.json();
     if(r.ok){{m.textContent='✓ Goedgekeurd — de clips staan ingepland.';m.className='ok';document.querySelector('button').disabled=true;}}
     else{{m.textContent='Er ging iets mis: '+(j.error||'onbekend');m.className='err';}}
   }}catch(e){{m.textContent='Netwerkfout, probeer opnieuw.';m.className='err';}}
 }}
</script></body></html>"""


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _review_blob(song):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", song or "")[:100] or "x"
    from google.cloud import storage
    return storage.Client().bucket(BUCKET_NAME).blob(f"reviewdata/{safe}.json")


@app.post("/reviewdata")
def reviewdata():
    """V2 zet hier de AI-captions/hashtags/urls neer (GCS), zodat de review-mail
    een KORTE link kan hebben i.p.v. alles in de URL (Outlook mangelt lange URLs)."""
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or request.form
    song = body.get("song") or ""
    if not song:
        return jsonify(error="song vereist"), 400
    caps = [c for c in (body.get("captions") or "").split("|~|") if c.strip()]
    urls = [u for u in (body.get("urls") or "").split(",") if u.strip()]
    data = {"title": body.get("title") or "", "hashtags": body.get("hashtags") or "",
            "captions": caps, "urls": urls}
    try:
        _review_blob(song).upload_from_string(
            json.dumps(data, ensure_ascii=False), content_type="application/json")
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(ok=True, n=len(caps))


@app.get("/review")
def review():
    song = request.args.get("song", "")
    title = request.args.get("title", "je nummer")
    caps, urls, tags = [], [], ""
    try:
        b = _review_blob(song)
        if b.exists():
            d = json.loads(b.download_as_text())
            caps = d.get("captions") or []
            urls = d.get("urls") or []
            tags = d.get("hashtags") or ""
            title = d.get("title") or title
    except Exception:
        pass
    if not caps:  # fallback: oude URL-parameters
        caps = [c for c in (request.args.get("captions", "").split("|~|")) if c.strip()] \
            or [request.args.get("caption", "")]
    if not urls:
        urls = [u for u in (request.args.get("urls", "").split(",")) if u.strip()]
    if not tags:
        tags = request.args.get("tags", "")
    html = _REVIEW_HTML.format(title=_esc(title), song=song, tags=_esc(tags),
                              captions_json=json.dumps(caps, ensure_ascii=False),
                              urls_json=json.dumps(urls, ensure_ascii=False))
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.post("/reviewsubmit")
def reviewsubmit():
    body = request.get_json(silent=True) or request.form
    song = body.get("song") or ""
    captions = body.get("captions")
    if captions is None:
        captions = [body.get("caption") or ""]
    captions = [(c or "").strip() for c in captions]
    hashtags = (body.get("hashtags") or "").strip()
    hook = os.environ.get("MAKE_APPROVE_WEBHOOK")
    if hook:
        try:
            requests.post(hook, json={"song": song, "captions": captions,
                                      "caption": captions[0] if captions else "",
                                      "hashtags": hashtags}, timeout=30)
        except Exception as e:
            return jsonify(error=f"kon niet doorsturen: {e}"), 502
    return jsonify(ok=True)


# ============================================================================
#  /lyricsreview + /lyricssubmit — Pijplijn 2: geromaniseerde lyrics nakijken
#  V1b mailt een link naar /lyricsreview?song=..&title=.. (data uit lyrics/<song>.json).
#  Nitin corrigeert regels + evt. tijden -> Goedkeuren -> /lyricssubmit zet
#  status:"approved" en overschrijft de json. Pas dan rendert V2 met ondertitels.
# ============================================================================

_LYRICS_HTML = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lyrics — Unchained Nitin</title>
<style>
 body{{margin:0;background:#0e1116;color:#f4f1e8;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
   display:flex;justify-content:center;padding:24px}}
 .card{{width:100%;max-width:600px}}
 h1{{color:#d4af37;font-size:22px;margin:0 0 4px}} .sub{{color:#aab4bf;font-size:14px;margin:0 0 16px}}
 .song{{color:#f4f1e8;font-weight:700}}
 .row{{display:flex;gap:8px;align-items:flex-start;background:#141b25;border:1px solid #26303b;
   border-radius:12px;padding:10px;margin:9px 0}}
 .n{{color:#8d99a6;font-size:12px;min-width:20px;padding-top:12px}}
 .tt{{display:flex;flex-direction:column;gap:6px;min-width:76px}}
 .tt input{{width:76px}}
 .row textarea{{flex:1;min-height:46px;background:#1a2330;border:1px solid #3c4a59;border-radius:10px;
   color:#f4f1e8;font-size:16px;padding:10px;font-family:inherit;resize:vertical}}
 input{{box-sizing:border-box;background:#1a2330;border:1px solid #3c4a59;border-radius:8px;
   color:#f4f1e8;font-size:13px;padding:8px;font-family:ui-monospace,Menlo,monospace}}
 .lbl{{color:#8d99a6;font-size:11px;margin:1px 2px}}
 .bar{{position:sticky;bottom:0;background:linear-gradient(180deg,transparent,#0e1116 30%);padding-top:14px}}
 button{{width:100%;background:#04b34f;color:#fff;font-size:17px;font-weight:700;border:0;
   border-radius:12px;padding:16px;cursor:pointer}}
 .hint{{color:#8d99a6;font-size:13px;margin:6px 2px 2px;line-height:1.5}}
 #msg{{margin-top:14px;font-size:15px;text-align:center}} .ok{{color:#7bd88f}} .err{{color:#e77}}
 .add{{background:#26303b;color:#f4f1e8;font-size:14px;padding:10px;border-radius:10px;margin:6px 0}}
</style></head><body><div class="card">
 <h1>Lyrics nakijken &amp; goedkeuren</h1>
 <p class="sub">Nummer: <span class="song">{title}</span> — corrigeer de geromaniseerde regels en (indien nodig) de tijden. Tijden zijn in seconden vanaf het begin van het nummer.</p>
 <div id="rows"></div>
 <div class="add" onclick="addRow()">+ regel toevoegen</div>
 <div class="bar">
   <p class="hint">Goedkeuren zet de ondertitels vast. Daarna renderen de clips mét lyrics. Niks doen? Dan blijft het concept en verschijnen er (nog) geen ondertitels.</p>
   <button onclick="send()">✅ Goedkeuren</button>
   <div id="msg"></div>
 </div>
</div><script>
 var LINES={lines_json};
 var box=document.getElementById('rows');
 function mkRow(ln,i){{
   var d=document.createElement('div'); d.className='row';
   d.innerHTML='<div class="n">'+(i+1)+'</div>'+
     '<div class="tt"><div class="lbl">start</div><input class="s" value="'+(ln.start!=null?ln.start:'')+'">'+
     '<div class="lbl">eind</div><input class="e" value="'+(ln.end!=null?ln.end:'')+'"></div>';
   var t=document.createElement('textarea'); t.className='r'; t.value=ln.roman||ln.text||'';
   d.appendChild(t); return d;
 }}
 function render(){{ box.innerHTML=''; LINES.forEach(function(ln,i){{ box.appendChild(mkRow(ln,i)); }}); }}
 function addRow(){{ LINES.push({{start:'',end:'',roman:''}}); render(); }}
 render();
 async function send(){{
   var m=document.getElementById('msg'); m.textContent='Versturen...'; m.className='';
   var rows=box.querySelectorAll('.row'); var out=[];
   rows.forEach(function(r){{
     var s=parseFloat(r.querySelector('.s').value), e=parseFloat(r.querySelector('.e').value);
     var tx=r.querySelector('.r').value.trim();
     if(tx && !isNaN(s) && !isNaN(e) && e>s) out.push({{start:s,end:e,roman:tx}});
   }});
   if(!out.length){{m.textContent='Geen geldige regels (elke regel heeft tekst + start<eind).';m.className='err';return;}}
   try{{
     var r=await fetch('/lyricssubmit',{{method:'POST',headers:{{'Content-Type':'application/json'}},
       body:JSON.stringify({{song:{song!r},lines:out}})}});
     var j=await r.json();
     if(r.ok){{m.textContent='✓ Goedgekeurd — '+j.n_lines+' regels vastgezet.';m.className='ok';document.querySelector('button').disabled=true;}}
     else{{m.textContent='Er ging iets mis: '+(j.error||'onbekend');m.className='err';}}
   }}catch(e){{m.textContent='Netwerkfout, probeer opnieuw.';m.className='err';}}
 }}
</script></body></html>"""


@app.get("/lyricsreview")
def lyricsreview():
    song = request.args.get("song", "")
    title = request.args.get("title", "je nummer")
    lines = []
    try:
        b = _lyrics_blob(song)
        if b.exists():
            d = json.loads(b.download_as_text())
            lines = d.get("lines") or []
            title = d.get("title") or title
    except Exception:
        pass
    html = _LYRICS_HTML.format(title=_esc(title), song=song,
                               lines_json=json.dumps(lines, ensure_ascii=False))
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.post("/lyricssubmit")
def lyricssubmit():
    body = request.get_json(silent=True) or request.form
    song = body.get("song") or ""
    if not song:
        return jsonify(error="song vereist"), 400
    raw = body.get("lines") or []
    lines = []
    for ln in raw:
        try:
            s = float(ln["start"]); e = float(ln["end"])
        except (KeyError, TypeError, ValueError):
            continue
        txt = (ln.get("roman") or ln.get("text") or "").strip()
        if txt and e > s:
            lines.append({"start": round(s, 3), "end": round(e, 3), "roman": txt})
    if not lines:
        return jsonify(error="geen geldige regels"), 400
    # bestaande json ophalen (voor title/dev), status op approved zetten
    data = {"song": song, "lang": "hi"}
    try:
        b = _lyrics_blob(song)
        if b.exists():
            data.update(json.loads(b.download_as_text()))
    except Exception:
        b = _lyrics_blob(song)
    data["status"] = "approved"
    data["lines"] = lines
    try:
        b.upload_from_string(json.dumps(data, ensure_ascii=False),
                             content_type="application/json")
    except Exception as e:
        return jsonify(error=str(e)), 500
    hook = os.environ.get("MAKE_LYRICS_APPROVE_WEBHOOK")
    if hook:
        try:
            requests.post(hook, json={"song": song, "n_lines": len(lines)}, timeout=30)
        except Exception:
            pass
    return jsonify(ok=True, song=song, status="approved", n_lines=len(lines))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
