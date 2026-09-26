"""
clip_fx.py — beat-synced camera-FX voor gefilmde clips (Unchained Nitin).

Twee dingen:
1) detect_hits(path): splitst de audio in een LAAG (kick) en MID/HOOG (snare) band
   en geeft per band de aanslag-tijden terug -> ({kick:[...], snare:[...]}).
2) fx_crop_filter(...): bouwt een ffmpeg crop-expressie (eval=frame) die op elke
   kick een subtiele ZOOM-PUNCH doet en op elke snare een korte SHAKE.

Pure logica (geen Flask/GCS), zodat het los te testen is: `python clip_fx.py`.
"""
import subprocess
import numpy as np

SR = 22050
NFFT = 1024
HOP = 256  # ~11.6 ms tijdresolutie

KICK_BAND = (30.0, 140.0)     # Hz
SNARE_BAND = (1600.0, 6500.0)  # Hz


def _read_mono(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        stdout=subprocess.PIPE, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _band_onsets(S, freqs, band, min_gap_s, thresh_k=1.6):
    lo, hi = band
    sel = (freqs >= lo) & (freqs <= hi)
    if not sel.any():
        return []
    band_mag = np.log1p(S[sel, :]).sum(axis=0)              # energie in band per frame
    flux = np.maximum(0.0, np.diff(band_mag, prepend=band_mag[:1]))
    if flux.max() > 0:
        flux = flux / flux.max()
    fps = SR / HOP
    # adaptieve drempel: lokaal gemiddelde + k*std
    win = max(3, int(0.4 * fps))
    kernel = np.ones(win) / win
    local_mean = np.convolve(flux, kernel, mode="same")
    local_std = np.sqrt(np.maximum(0.0, np.convolve(flux ** 2, kernel, mode="same") - local_mean ** 2))
    thr = local_mean + thresh_k * local_std
    min_gap = int(min_gap_s * fps)
    times, last = [], -min_gap
    for i in range(1, len(flux) - 1):
        if flux[i] >= thr[i] and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            if i - last >= min_gap:
                times.append(round(i / fps, 3))
                last = i
    return times


def detect_hits(path):
    """Retourneer {'kick':[t...], 'snare':[t...], 'duration':sec}."""
    y = _read_mono(path)
    dur = len(y) / SR
    win = np.hanning(NFFT).astype(np.float32)
    nframes = 1 + max(0, (len(y) - NFFT) // HOP)
    if nframes < 4:
        return {"kick": [], "snare": [], "duration": round(dur, 3)}
    S = np.empty((NFFT // 2 + 1, nframes), dtype=np.float32)
    for i in range(nframes):
        S[:, i] = np.abs(np.fft.rfft(y[i * HOP:i * HOP + NFFT] * win))
    freqs = np.fft.rfftfreq(NFFT, 1.0 / SR)
    kicks = _band_onsets(S, freqs, KICK_BAND, min_gap_s=0.14, thresh_k=1.5)
    snares = _band_onsets(S, freqs, SNARE_BAND, min_gap_s=0.10, thresh_k=1.8)
    return {"kick": kicks, "snare": snares, "duration": round(dur, 3)}


def _band_onsets_detailed(S, freqs, band, min_gap_s, thresh_k):
    """Als _band_onsets, maar retourneert per aanslag ook de onset-sterkte.
    onset_strength = ruwe spectral-flux-waarde op de piek (relatieve energie-toename).
    strength_norm  = die flux genormaliseerd op de sterkste hit in de band (0..1).
    Dit is een echte detector-output; het is GEEN probabilistische confidence."""
    lo, hi = band
    sel = (freqs >= lo) & (freqs <= hi)
    if not sel.any():
        return []
    band_mag = np.log1p(S[sel, :]).sum(axis=0)
    flux_raw = np.maximum(0.0, np.diff(band_mag, prepend=band_mag[:1]))
    peak = flux_raw.max()
    flux = flux_raw / peak if peak > 0 else flux_raw
    fps = SR / HOP
    win = max(3, int(0.4 * fps))
    kernel = np.ones(win) / win
    local_mean = np.convolve(flux, kernel, mode="same")
    local_std = np.sqrt(np.maximum(0.0, np.convolve(flux ** 2, kernel, mode="same") - local_mean ** 2))
    thr = local_mean + thresh_k * local_std
    min_gap = int(min_gap_s * fps)
    hits, last = [], -min_gap
    FLOOR = 0.05  # negeer verwaarloosbare piekjes (bv. artefacten bij de start)
    for i in range(1, len(flux) - 1):
        if flux[i] >= thr[i] and flux[i] >= FLOOR and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            if i - last >= min_gap:
                hits.append({
                    "t": round(i / fps, 3),
                    "onset_strength": round(float(flux_raw[i]), 4),
                    "strength_norm": round(float(flux[i]), 4),
                })
                last = i
    return hits


def detect_hits_detailed(path):
    """Kick/snare-aanslagen mét onset-sterkte. Retourneert
    {'kick':[{t,onset_strength,strength_norm}], 'snare':[...], 'duration'}."""
    y = _read_mono(path)
    dur = len(y) / SR
    win = np.hanning(NFFT).astype(np.float32)
    nframes = 1 + max(0, (len(y) - NFFT) // HOP)
    if nframes < 4:
        return {"kick": [], "snare": [], "duration": round(dur, 3)}
    S = np.empty((NFFT // 2 + 1, nframes), dtype=np.float32)
    for i in range(nframes):
        S[:, i] = np.abs(np.fft.rfft(y[i * HOP:i * HOP + NFFT] * win))
    freqs = np.fft.rfftfreq(NFFT, 1.0 / SR)
    kicks = _band_onsets_detailed(S, freqs, KICK_BAND, min_gap_s=0.14, thresh_k=1.5)
    snares = _band_onsets_detailed(S, freqs, SNARE_BAND, min_gap_s=0.10, thresh_k=1.8)
    return {"kick": kicks, "snare": snares, "duration": round(dur, 3)}


def _pulse_sum_on(times, fps, decay, gate):
    """Som van korte exp-pulsen op elke tijd, uitgedrukt in het frame-nummer 'on'
    (zoompan kent geen 't', wel 'on'). Komma's zijn met \\, geëscaped."""
    if not times:
        return "0"
    gate_f = gate * fps
    terms = []
    for t in times:
        f = t * fps
        terms.append("exp(-((on-%.2f)/%.1f)/%.3f)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                     % (f, fps, decay, f, f + gate_f))
    return "(" + "+".join(terms) + ")"


def _shake_sum_on(times, fps, freq_per_frame, decay, gate):
    """Som van korte gedempte sinus-wobbles (voor de snare-shake), in 'on'."""
    if not times:
        return "0"
    gate_f = gate * fps
    terms = []
    for t in times:
        f = t * fps
        terms.append("sin((on-%.2f)*%.3f)*exp(-((on-%.2f)/%.1f)/%.3f)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                     % (f, freq_per_frame, f, fps, decay, f, f + gate_f))
    return "(" + "+".join(terms) + ")"


def fx_beat_filter(kicks, snares, W=1080, H=1920, fps=24,
                   kick_zoom=0.038, snare_shake=0.010,
                   in_label="fxin", out_label="fx"):
    """Beat-synced zoom-punch (kick) + horizontale shake (snare) via zoompan.
    - kick_zoom: max extra zoom op een kick (0.055 = +5,5%).
    - snare_shake: shake-amplitude als fractie van breedte (0.012 ≈ 13px bij 1080).
    Werkt in ffmpeg 4.4+ (geen crop 'eval' nodig). Verwacht een 1080x1920/fps input.
    """
    zpulse = _pulse_sum_on(kicks, fps, decay=0.06, gate=0.20)
    Z = "1+%.4f*%s" % (kick_zoom, zpulse)
    shake_px = snare_shake * W
    OX = "%.2f*%s" % (shake_px, _shake_sum_on(snares, fps, freq_per_frame=1.6, decay=0.045, gate=0.16))
    x = "iw/2-(iw/zoom/2)+(%s)" % OX
    y = "ih/2-(ih/zoom/2)"
    return ("[%s]zoompan=z='%s':x='%s':y='%s':d=1:s=%dx%d:fps=%d[%s]"
            % (in_label, Z, x, y, W, H, fps, out_label))


ZMAP = {"light": 0.03, "medium": 0.05, "strong": 0.075, "strongest": 0.09}
SPX = {"light": 6.0, "medium": 12.0, "strong": 18.0, "strongest": 22.0}


def fx_from_cues(cues, W=1080, H=1920, fps=24, in_label="fxin", out_label="fx"):
    """Bouw een zoompan-FX uit een goedgekeurde cues[]-lijst (i.p.v. auto-detectie).
    Ondersteunt: shake, vshake, zoom (punch <=0.5s of sustained), pullout, stable.
    Retourneert (filter_str, flashes) waarbij flashes=[(t,dur), ...] apart worden gerenderd.
    Cue = {t, type, strength?, duration?}."""
    z_terms, x_terms, y_terms, flashes = [], [], [], []
    for c in (cues or []):
        t = float(c.get("t", 0)); f = t * fps
        typ = (c.get("type") or "").lower()
        st = (c.get("strength") or "medium").lower()
        dur = float(c.get("duration", 0.25)); gate = dur * fps
        # numerieke overrides (exacte controle, bv. voor ~30% reductie): "px" / "amp"
        px = float(c["px"]) if c.get("px") is not None else SPX.get(st, 12.0)
        amp = float(c["amp"]) if c.get("amp") is not None else ZMAP.get(st, 0.05)
        if typ == "zoom":
            if dur <= 0.5:
                z_terms.append("%.4f*exp(-((on-%.2f)/%.1f)/0.06)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                               % (amp, f, fps, f, f + 0.20 * fps))
            else:
                z_terms.append("%.4f*gte(on\\,%.2f)*lt(on\\,%.2f)" % (amp, f, f + gate))
        elif typ in ("zoomramp", "smoothzoom"):
            # Vloeiende continue push-in: ease-in-out omhoog over [f,f1] met piek=amp op f1,
            # daarna zachte ease-out over een korte staart (geen abrupte reset).
            tail = float(c.get("tail", 1.5)); tail_f = tail * fps
            f1 = f + gate
            z_terms.append("%.4f*((1-cos(PI*min(max((on-%.2f)/%.2f\\,0)\\,1)))/2)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                           % (amp, f, max(1.0, gate), f, f1))
            z_terms.append("%.4f*((1+cos(PI*min(max((on-%.2f)/%.2f\\,0)\\,1)))/2)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                           % (amp, f1, max(1.0, tail_f), f1, f1 + tail_f))
        elif typ == "pullout":
            pamp = float(c["amp"]) if c.get("amp") is not None else 0.06
            z_terms.append("%.4f*(1-(on-%.2f)/%.2f)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                           % (pamp, f, max(1.0, gate), f, f + gate))
        elif typ == "shake":
            # gate = cue-duur (frame-accuraat); decay ~ dur/3 zodat de shake binnen het
            # venster gedempt terugkeert. px numeriek override mogelijk.
            gs = dur if dur else 0.16; dec = max(0.02, gs / 3.0)
            x_terms.append("%.2f*sin((on-%.2f)*1.6)*exp(-((on-%.2f)/%.1f)/%.3f)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                           % (px, f, f, fps, dec, f, f + gs * fps))
        elif typ == "vshake":
            gs = dur if dur else 0.16; dec = max(0.02, gs / 3.0)
            y_terms.append("%.2f*sin((on-%.2f)*1.6)*exp(-((on-%.2f)/%.1f)/%.3f)*gte(on\\,%.2f)*lt(on\\,%.2f)"
                           % (px, f, f, fps, dec, f, f + gs * fps))
        elif typ == "flash":
            # per-frame opacities: expliciete lijst, of 1 frame op 'opacity' (default 45%)
            ops = c.get("frame_opacities")
            if not ops:
                ops = [float(c.get("opacity", 0.45))]
            flashes.append((t, [float(o) for o in ops]))
        # "stable" -> niets
    Z = "1+(" + "+".join(z_terms) + ")" if z_terms else "1"
    X = "iw/2-(iw/zoom/2)" + ("+(" + "+".join(x_terms) + ")" if x_terms else "")
    Y = "ih/2-(ih/zoom/2)" + ("+(" + "+".join(y_terms) + ")" if y_terms else "")
    filt = ("[%s]zoompan=z='%s':x='%s':y='%s':d=1:s=%dx%d:fps=%d[%s]"
            % (in_label, Z, X, Y, W, H, fps, out_label))
    return filt, flashes


def shift_and_window(times, start, dur):
    """Filter tijden binnen [start, start+dur] en verschuif naar fragment-tijd 0..dur."""
    out = []
    for t in times:
        if start <= t <= start + dur:
            out.append(round(t - start, 3))
    return out


def thin(times, min_gap=0.40, max_count=40):
    """Dun aanslagen uit: houd minimaal min_gap sec ertussen en cap op max_count.
    Voorkomt een epileptisch effect bij dichte beats én een te lange ffmpeg-expressie."""
    out, last = [], -1e9
    for t in times:
        if t - last >= min_gap:
            out.append(t)
            last = t
    if len(out) > max_count:
        step = (len(out) - 1) / (max_count - 1)
        idx = sorted({round(i * step) for i in range(max_count)})
        out = [out[i] for i in idx]
    return out


if __name__ == "__main__":
    import tempfile, os, sys
    # --- synthetische test: 12s, kick elke 0.5s, snare op de tel ertussen ---
    sr = 44100
    dur = 12.0
    n = int(sr * dur)
    t = np.arange(n) / sr
    audio = np.zeros(n, dtype=np.float32)
    # kick: 60 Hz burst elke 0.5s
    for k in np.arange(0.5, dur, 0.5):
        i0 = int(k * sr)
        env = np.exp(-np.arange(0, int(0.12 * sr)) / (0.03 * sr))
        seg = (0.9 * np.sin(2 * np.pi * 60 * np.arange(len(env)) / sr) * env).astype(np.float32)
        audio[i0:i0 + len(seg)] += seg
    # snare: ruisburst op 0.75, 1.25, ... (tussen de kicks)
    rng = np.random.default_rng(0)
    for s in np.arange(0.75, dur, 0.5):
        i0 = int(s * sr)
        env = np.exp(-np.arange(0, int(0.10 * sr)) / (0.02 * sr))
        noise = rng.standard_normal(len(env)).astype(np.float32)
        # highpass-achtig: differentieer de ruis om laag eruit te halen
        noise = np.diff(noise, prepend=noise[:1])
        audio[i0:i0 + len(env)] += (0.6 * noise * env).astype(np.float32)
    audio = np.clip(audio, -1, 1)
    wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    raw = (audio * 32767).astype(np.int16).tobytes()
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(raw)

    hits = detect_hits(wav)
    print("duration:", hits["duration"])
    print("kicks (%d):" % len(hits["kick"]), hits["kick"])
    print("snares (%d):" % len(hits["snare"]), hits["snare"])

    # --- render een testclip met de FX om de filtergraph te valideren ---
    vid = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc2=size=1080x1920:rate=24:duration=%.1f" % dur,
                    "-i", wav, "-map", "0:v", "-map", "1:a", "-shortest",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", vid], check=True)
    k = shift_and_window(hits["kick"], 0.0, dur)
    s = shift_and_window(hits["snare"], 0.0, dur)
    fc = "[0:v]null[fxin];" + fx_beat_filter(k, s, out_label="vo")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", vid, "-filter_complex", fc,
           "-map", "[vo]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-t", "%.1f" % dur, out]
    print("render cmd len:", len(fc), "chars")
    r = subprocess.run(cmd, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print("FFMPEG FOUT:\n", r.stderr.decode()[-2000:]); sys.exit(1)
    dprobe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of", "csv=p=0", out],
                            stdout=subprocess.PIPE).stdout.decode().strip()
    print("OK — render gelukt, out-duur:", dprobe, "s, bestand:", os.path.getsize(out), "bytes")
    print("frame-grab test...")
    fr = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", out,
                    "-frames:v", "1", fr], check=True)
    print("frame op kick t=0.5:", fr, os.path.getsize(fr), "bytes")
