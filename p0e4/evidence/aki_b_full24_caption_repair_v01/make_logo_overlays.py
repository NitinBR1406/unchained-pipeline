"""AKI B full24 caption repair V01 - derive the two gold chain-logo overlay clips (1080x1920 ProRes 4444 + alpha).
No Resolve. Source must be the approved chain logo (5e77eb7a...); the lightning logo (9ec01839...) is refused.
Writes overlays + OVERLAY_MANIFEST.json next to this script; refuses to overwrite."""
import hashlib, json, shutil, subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
LOGO = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair/"
            "unchained_chain_emblem.png")
CHAIN_LOGO_SHA = "5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509"
LIGHTNING_LOGO_SHA = "9ec0183958eebed15e262202918db201bcd669e0d4975c7385ec88ecbc20805d"
FFMPEG = shutil.which("ffmpeg") or str(Path.home() / "ffbin/ffmpeg")
FFPROBE = shutil.which("ffprobe") or str(Path.home() / "ffbin/ffprobe")
W, H, FPS = 1080, 1920, 30
# name: (frames, logo width px, logo centre (x, y from top) px, fade-in frames, fade-out frames)
OVERLAYS = {
    "AKI_B_FULL24_INTRO_LOGO_30F.mov": (30, 390, (540, 1498), 5, 6),     # global [0,30), chest (as V13 intro)
    "AKI_B_FULL24_ENDCARD_LOGO_48F.mov": (48, 430, (540, 1400), 6, 6),   # global [672,720), above end-card text
}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(name, frames, width, centre, fade_in, fade_out):
    dst = OUT / name
    assert not dst.exists(), f"refusing to overwrite {dst}"
    graph = (f"color=c=black@0.0:s={W}x{H}:r={FPS},format=rgba[bg];"
             f"[0:v]scale={width}:-1:flags=lanczos,format=rgba[lg];"
             f"[bg][lg]overlay=x={centre[0]}-w/2:y={centre[1]}-h/2:format=auto:shortest=0,"
             f"fade=t=in:st=0:d={fade_in / FPS}:alpha=1,fade=t=out:st={(frames - fade_out) / FPS}:d={fade_out / FPS}:alpha=1,"
             f"format=yuva444p10le[out]")
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(LOGO), "-filter_complex", graph,
                    "-map", "[out]", "-frames:v", str(frames), "-r", str(FPS), "-c:v", "prores_ks", "-profile:v", "4",
                    "-pix_fmt", "yuva444p10le", "-an", "-fflags", "+bitexact", "-flags", "+bitexact", str(dst)], check=True)
    probe = json.loads(subprocess.run([FFPROBE, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height,pix_fmt,nb_read_frames,r_frame_rate,codec_name", "-of", "json", str(dst)],
                                      capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert (probe["width"], probe["height"], probe["pix_fmt"], int(probe["nb_read_frames"]), probe["r_frame_rate"]) == \
        (W, H, "yuva444p12le", frames, f"{FPS}/1"), probe   # ProRes 4444 decodes as 12-bit (V13 emblem: 12-bit)
    # alpha bounding box at mid-clip must match the planned logo placement (+/-3 px)
    alpha = subprocess.run([FFMPEG, "-v", "error", "-i", str(dst), "-vf", f"select=eq(n\\,{frames // 2}),alphaextract,format=gray",
                            "-fps_mode", "vfr", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    assert len(alpha) == W * H
    rows = [r for r in range(H) if max(alpha[r * W:(r + 1) * W]) > 8]
    cols = [c for c in range(W) if max(alpha[c::W]) > 8]
    x, y, w, h = cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1
    assert max(alpha[:W * 50]) == 0, "background alpha not transparent"
    assert abs(x + w / 2 - centre[0]) <= 3 and abs(y + h / 2 - centre[1]) <= 3 and abs(w - width) <= 4, (x, y, w, h)
    return {"file": name, "sha256": sha(dst), "bytes": dst.stat().st_size, "frames": frames, "logo_width_px": width,
            "logo_centre_px": list(centre), "fade_in_frames": fade_in, "fade_out_frames": fade_out,
            "alpha_bbox_mid_clip": [x, y, w, h], "probe": probe}


def main():
    logo_sha = sha(LOGO)
    assert logo_sha != LIGHTNING_LOGO_SHA, "lightning logo refused"
    assert logo_sha == CHAIN_LOGO_SHA, "chain-logo binding drift"
    manifest = OUT / "OVERLAY_MANIFEST.json"
    assert not manifest.exists(), "manifest exists - refusing to overwrite"
    result = {"schema": "AKI_B_FULL24_LOGO_OVERLAYS_V01", "source_logo": str(LOGO.name), "source_logo_sha256": logo_sha,
              "overlays": [build(n, *spec) for n, spec in OVERLAYS.items()]}
    manifest.write_text(json.dumps(result, indent=1) + "\n")
    print("OVERLAYS_OK")


if __name__ == "__main__":
    main()
