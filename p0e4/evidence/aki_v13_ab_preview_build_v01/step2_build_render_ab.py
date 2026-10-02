"""AKI V13 A/B preview build V01 (rev 2) - step 2: build A/B timelines inside the isolated copy and render global [60,420).
Mutates only project UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01 (must already be open; never calls LoadProject).
Pure helpers are importable without Resolve (offline tests); Resolve is only touched when run as __main__."""
import hashlib, json, re, sys, time
from pathlib import Path

OUT = Path(__file__).resolve().parent
COPY = "UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01"
V13_DRP = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair/"
               "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp")
V13_DRP_SHA = "f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec"
BASE_TIMELINE = "AAKHRI_FIRST_PUBLISH_PREVIEW_72_96_V01"
V1 = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
SRC_OFFSET = 2144                 # IMG_5739 source frame = timeline frame + 2144 (DRP In values)
AUDIO_FILE, AUDIO_OFFSET = "AAKHRI ISHQ MASTER 2.wav", 2160   # WAV frame = timeline frame + 2160 (72.000 s)
EXCERPT = (60, 420)               # half-open; Resolve MarkIn/MarkOut = origin+60 / origin+419 (inclusive)
BUILD_CLIPS = (0, 1, 2, 3)        # V1 clips intersecting the excerpt
TEXT_CLIP = 1                     # hook window global [90,150) lies in clip 1 [89,204); local = excerpt - 29
HOOK_TEXT = r"SOME LOVE STORIES\nNEVER REALLY END."
R_CY, R_SIZE = 0.72, 2.3          # V13 UN_CONTINUOUS_RHYTHM_V03 base framing
F = (0.5, 0.5 + (1.0 - R_CY) / R_SIZE)   # pre-rhythm point that V13 maps to output top-centre (zoom anchor)
MAX_ZOOM = 1.15                   # relative to V13 framing; V13 already upscales the source 1.15x
NEUTRAL = {"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": 0.0, "RotationAngle": 0.0,
           "CropLeft": 0.0, "CropRight": 0.0, "CropTop": 0.0, "CropBottom": 0.0}
VARIANTS = {   # shots: (start, end, zoom_from, zoom_to, window_dx) in excerpt frames; punch: (pp, attack, decay)
    "A": {"timeline": "AKI_V13_AB_A_CINEMATIC_V01", "style": "Medium", "punch": None,
          "shots": [(0, 120, 1.00, 1.03, 0.0), (120, 240, 1.10, 1.13, 0.0), (240, 360, 1.00, 1.03, 0.02)],
          "captions": [("UN_AB_HOOK", 0, 0.205, [(30, 0), (38, 1), (82, 1), (90, 0)], None)]},
    "B": {"timeline": "AKI_V13_AB_B_RHYTHMIC_V01", "style": "SemiBold", "punch": (0.03, 2, 8),
          "shots": [(0, 60, 1.00, 1.00, 0.0), (60, 120, 1.12, 1.12, 0.0), (120, 180, 1.00, 1.00, 0.03),
                    (180, 240, 1.10, 1.10, 0.0), (240, 300, 1.06, 1.06, 0.0), (300, 360, 1.12, 1.12, -0.02)],
          "captions": [("UN_AB_HOOK_P1", 1, 0.223, [(30, 0), (36, 1), (84, 1), (90, 0)], (30, 36)),
                       ("UN_AB_HOOK_P2", 2, 0.187, [(48, 0), (54, 1), (84, 1), (90, 0)], (48, 54))]},
}
RISE, TEXT_SIZE = 0.008, 0.08
TEXTPLUS_DEFAULTS = {"Softness1": 0.0, "Enabled2": 0.0, "Enabled3": 0.0}   # Fusion may omit default-valued inputs on export
RENDER_TIMEOUT_S, STOP_TIMEOUT_S = 900, 60
NUM = r"-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?"


class BuildHold(RuntimeError):
    """Fail-closed stop after persisting HOLD state; no further variant may start."""


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def zoom(v, e):
    if not 0 <= e < 360:
        return 1.0, 0.0
    for s, t, z0, z1, dx in v["shots"]:
        if s <= e < t:
            z = z0 + (z1 - z0) * (e - s) / (t - s)
            if v["punch"] and s > 0:
                pp, attack, decay = v["punch"]; k = e - s
                if k < attack:
                    z += pp * (k + 1) / attack
                elif k < attack + decay:
                    z += pp * (1 - (k - attack + 1) / decay)
            return z, dx
    raise AssertionError(e)


def assert_safe(z, dx):
    """Output corners mapped back to normalized source (y up). Fails closed on any edge/ceiling risk."""
    assert 1.0 - 1e-9 <= z <= MAX_ZOOM + 1e-9, z
    pts = []
    for ox in (0.0, 1.0):
        for oy in (0.0, 1.0):
            sx, sy = 0.5 + (ox - 0.5) / R_SIZE, 0.5 + (oy - R_CY) / R_SIZE
            pts.append((F[0] + (sx - F[0] + dx / R_SIZE) / z, F[1] + (sy - F[1]) / z))
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    assert min(xs) >= 0.02 and max(xs) <= 0.98, pts      # inside source width
    assert min(ys) >= 0.14, pts                           # inside source height (incl. T1 shift)
    assert max(ys) <= F[1] + 1e-9, pts                    # never above V13 top edge (ceiling guard)
    return [min(xs), max(xs), min(ys), max(ys)]


def interp(keys, f):
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            return v0 + (v1 - v0) * (f - f0) / (f1 - f0)
    return keys[-1][1]


def tools(text): return dict(re.findall(r"\n\t\t(\w+) = (\w+) \{\n", text))


def span(text, name):
    m = re.search(rf"\n\t\t{re.escape(name)} = \w+ \{{\n", text); assert m, f"missing tool {name}"
    end = re.compile(r"\n\t\t\},?\n").search(text, m.end() - 1)
    return m.start() + 1, end.end()


def block_of(text, name):
    s, e = span(text, name)
    return text[s:e]


def source_op(block, name):
    m = re.search(rf"\b{name} = Input \{{\s*SourceOp = \"(\w+)\"", block)
    return m.group(1) if m else None


def keyframes(text, name):
    keys = [(int(f), float(v)) for f, v in re.findall(rf"\[(-?\d+)\] = \{{ ({NUM})", block_of(text, name))]
    assert keys, f"no keyframes in {name}"
    return keys


def scalar(block, name, default=None):
    m = re.search(rf"\b{name} = Input \{{\s*Value = (?:Number \{{\s*Value = )?({NUM})", block)
    if m:
        return float(m.group(1))
    assert default is not None, f"missing input {name}"
    return default


def point(block, name):
    m = (re.search(rf"\b{name} = Input \{{\s*Value = \{{\s*({NUM}),\s*({NUM})\s*\}}", block)
         or re.search(rf"\b{name} = Input \{{\s*Value = Point \{{\s*X = ({NUM}),\s*Y = ({NUM})", block))
    assert m, f"missing point {name}"
    return float(m.group(1)), float(m.group(2))


def string(block, name):
    m = re.search(rf'\b{name} = Input \{{\s*Value = "((?:[^"\\]|\\.)*)"', block)
    assert m, f"missing string {name}"
    return m.group(1)


def same_keys(got, want, label):
    assert want and len(got) == len(want), (label, len(got), len(want))
    for (gf, gv), (wf, wv) in zip(got, want):
        assert gf == wf and abs(gv - wv) < 1e-5, (label, gf, gv, wf, wv)


def rewire(text, tool_name, input_name, old, new):
    s, e = span(text, tool_name)
    patched, n = re.subn(rf"(\b{input_name} = Input \{{\s*SourceOp = \"){re.escape(old)}\"", rf'\g<1>{new}"', text[s:e])
    assert n == 1, (tool_name, input_name, old)
    return text[:s] + patched + text[e:]


def spline(name, keys):
    rows = "\n".join(f"\t\t\t\t[{f}] = {{ {v}, Flags = {{ Linear = true }} }}," for f, v in keys)
    return (f"\t\t{name} = BezierSpline {{\n\t\t\tSplineColor = {{ Red = 0, Green = 200, Blue = 255 }},\n"
            f"\t\t\tCtrlWZoom = false,\n\t\t\tKeyFrames = {{\n{rows}\n\t\t\t}}\n\t\t}},\n")


def inp(name, op=None, value=None, source="Output"):
    if op:
        return f'\t\t\t\t{name} = Input {{ SourceOp = "{op}", Source = "{source}", }},\n'
    return f"\t\t\t\t{name} = Input {{ Value = {value}, }},\n"


def tool(name, kind, inputs, extra=""):
    return f"\t\t{name} = {kind} {{\n{extra}\t\t\tInputs = {{\n{''.join(inputs)}\t\t\t}},\n\t\t}},\n"


def xypath(name, x, y):
    return tool(name, "XYPath", [inp("X", x, source="Value"), inp("Y", y, source="Value")],
                extra='\t\t\tShowKeyPoints = false,\n\t\t\tDrawMode = "ModifyOnly",\n')


def text_merges(text):
    kinds = tools(text)
    for name, kind in kinds.items():
        if kind == "Merge":
            block = block_of(text, name)
            fg = source_op(block, "Foreground")
            if kinds.get(fg) == "TextPlus":
                yield name, fg, source_op(block, "Blend")


def patch_clip(text, key, v, idx):
    start, end = V1[idx]; length = end - start
    r6 = lambda keys: [(f, round(val, 6)) for f, val in keys]
    rhythm = keyframes(text, "UN_CONTINUOUS_RHYTHM_V03Size")
    assert source_op(block_of(text, "UN_CONTINUOUS_RHYTHM_V03"), "Size") == "UN_CONTINUOUS_RHYTHM_V03Size"
    plan = {"clip": idx, "splines": {"UN_CONTINUOUS_RHYTHM_V03Size": rhythm}, "points": {}, "kinds": {},
            "wiring": {("UN_CONTINUOUS_RHYTHM_V03", "Size"): "UN_CONTINUOUS_RHYTHM_V03Size"},
            "disabled_text_merges": [], "captions": []}
    for merge, fg, blend in list(text_merges(text)):
        if blend:
            s, e = span(text, blend)
            text = text[:s] + spline(blend, [(0, 0.0), (length - 1, 0.0)]) + text[e:]
        else:
            s, e = span(text, merge)
            block = re.sub(r"\n\t+Blend = Input \{ Value = [^\n]*", "", text[s:e])
            block = block.replace("\t\t\tInputs = {\n", "\t\t\tInputs = {\n" + inp("Blend", value=0), 1)
            assert len(re.findall(r"\bBlend = Input", block)) == 1, merge
            text = text[:s] + block + text[e:]
        plan["disabled_text_merges"].append({"merge": merge, "text_tool": fg, "blend": blend})
    zs, xs, windows, composed = [], [], [], []
    for local in range(length):
        z, dx = zoom(v, start + local - EXCERPT[0])
        windows.append(assert_safe(z, dx))
        zs.append((local, z)); xs.append((local, 0.5 - dx / R_SIZE))
        if EXCERPT[0] <= start + local < EXCERPT[1]:
            composed.append(z * interp(rhythm, local))
    t1c, t3c = (0.5, round(1 - F[1], 9)), (0.5, round(F[1], 9))
    plan["splines"].update({"UN_AB_T2Size": r6(zs), "UN_AB_T2CenterX": r6(xs), "UN_AB_T2CenterY": [(0, 0.5), (length - 1, 0.5)]})
    plan["points"].update({("UN_AB_T1", "Center"): t1c, ("UN_AB_T3", "Center"): t3c})
    plan["kinds"].update({"UN_AB_T1": "Transform", "UN_AB_T2": "Transform", "UN_AB_T3": "Transform", "UN_AB_T2Center": "XYPath"})
    plan["wiring"].update({("UN_AB_T1", "Input"): "MediaIn1", ("UN_AB_T2", "Input"): "UN_AB_T1",
                           ("UN_AB_T2", "Size"): "UN_AB_T2Size", ("UN_AB_T2", "Center"): "UN_AB_T2Center",
                           ("UN_AB_T2Center", "X"): "UN_AB_T2CenterX", ("UN_AB_T2Center", "Y"): "UN_AB_T2CenterY",
                           ("UN_AB_T3", "Input"): "UN_AB_T2", ("UN_CONTINUOUS_RHYTHM_V03", "Input"): "UN_AB_T3"})
    blocks = [
        tool("UN_AB_T1", "Transform", [inp("Input", "MediaIn1"), inp("Center", value=f"{{ {t1c[0]}, {t1c[1]} }}")]),
        *(spline(n, plan["splines"][n]) for n in ("UN_AB_T2Size", "UN_AB_T2CenterX", "UN_AB_T2CenterY")),
        xypath("UN_AB_T2Center", "UN_AB_T2CenterX", "UN_AB_T2CenterY"),
        tool("UN_AB_T2", "Transform", [inp("Input", "UN_AB_T1"), inp("Size", "UN_AB_T2Size", source="Value"),
                                       inp("Center", "UN_AB_T2Center", source="Value")]),
        tool("UN_AB_T3", "Transform", [inp("Input", "UN_AB_T2"), inp("Center", value=f"{{ {t3c[0]}, {t3c[1]} }}")]),
    ]
    text = rewire(text, "UN_CONTINUOUS_RHYTHM_V03", "Input", "MediaIn1", "UN_AB_T3")
    first = last = source_op(block_of(text, "MediaOut1"), "Input"); assert first
    if idx == TEXT_CLIP:
        hook = string(block_of(text, "UN_BRAND_HOOK"), "StyledText"); assert hook == HOOK_TEXT, hook
        lines = hook.split(r"\n"); assert len(lines) == 2
        local = lambda ex: ex + EXCERPT[0] - start
        for name, part, y, opacity, rise in v["captions"]:
            words = hook if part == 0 else lines[part - 1]
            okeys = [(0, 0.0)] + [(local(ex), float(o)) for ex, o in opacity] + [(length - 1, 0.0)]
            ykeys = r6([(0, y - RISE), (local(rise[0]), y - RISE), (local(rise[1]), y), (length - 1, y)]
                       if rise else [(0, y), (length - 1, y)])
            plan["splines"].update({f"{name}CX": [(0, 0.5), (length - 1, 0.5)], f"{name}CY": ykeys, f"{name}Blend": okeys})
            plan["kinds"].update({name: "TextPlus", f"{name}Center": "XYPath", f"{name}Merge": "Merge"})
            plan["wiring"].update({(name, "Center"): f"{name}Center", (f"{name}Center", "X"): f"{name}CX",
                                   (f"{name}Center", "Y"): f"{name}CY", (f"{name}Merge", "Blend"): f"{name}Blend",
                                   (f"{name}Merge", "Background"): last, (f"{name}Merge", "Foreground"): name})
            blocks += [spline(f"{name}CX", plan["splines"][f"{name}CX"]), spline(f"{name}CY", ykeys),
                       xypath(f"{name}Center", f"{name}CX", f"{name}CY"),
                       tool(name, "TextPlus", [inp("Width", value=2160), inp("Height", value=3840),
                            inp("UseFrameFormatSettings", value=1), inp("Center", f"{name}Center", source="Value"),
                            inp("StyledText", value=f'"{words}"'), inp("Font", value='"Montserrat"'),
                            inp("Style", value=f'"{v["style"]}"'), inp("Size", value=TEXT_SIZE),
                            inp("Softness1", value=0), inp("Enabled2", value=0), inp("Enabled3", value=0),
                            inp("VerticalJustificationNew", value=3), inp("HorizontalJustificationNew", value=3)]),
                       spline(f"{name}Blend", okeys),
                       tool(f"{name}Merge", "Merge", [inp("Blend", f"{name}Blend", source="Value"), inp("Background", last),
                                                      inp("Foreground", name), inp("PerformDepthMerge", value=0)])]
            plan["captions"].append({"tool": name, "text": words, "font": "Montserrat", "style": v["style"], "size": TEXT_SIZE,
                                     "opacity_excerpt_keys": opacity, "rise_excerpt": rise})
            last = f"{name}Merge"
        text = rewire(text, "MediaOut1", "Input", first, last)
    plan["wiring"][("MediaOut1", "Input")] = last
    text, n = re.subn(r"\n\tTools = (?:ordered\(\) )?\{\n", lambda m: m.group(0) + "".join(blocks), text, count=1)
    assert n == 1
    plan["window_extremes"] = [min(w[0] for w in windows), max(w[1] for w in windows),
                               min(w[2] for w in windows), max(w[3] for w in windows)]
    plan["composed_peak_total_size_in_excerpt"] = round(max(composed), 6) if composed else None
    return text, plan


def verify_readback(body, plan):
    """Every planned spline, connection, static point, caption setting and disabled pre-existing caption must match."""
    kinds = tools(body)
    for name, kind in plan["kinds"].items():
        assert kinds.get(name) == kind, (name, kinds.get(name))
    for name, keys in plan["splines"].items():
        assert kinds.get(name) == "BezierSpline", name
        same_keys(keyframes(body, name), keys, name)
    for (tool_name, input_name), op in plan["wiring"].items():
        assert source_op(block_of(body, tool_name), input_name) == op, (tool_name, input_name, op)
    for (tool_name, input_name), xy in plan["points"].items():
        got = point(block_of(body, tool_name), input_name)
        assert abs(got[0] - xy[0]) < 1e-6 and abs(got[1] - xy[1]) < 1e-6, (tool_name, input_name, got)
    for c in plan["captions"]:
        b = block_of(body, c["tool"])
        assert string(b, "StyledText") == c["text"] and string(b, "Font") == c["font"] and string(b, "Style") == c["style"], c
        assert abs(scalar(b, "Size") - c["size"]) < 1e-9, c
        for k, default in TEXTPLUS_DEFAULTS.items():
            assert scalar(b, k, default) == 0.0, (c["tool"], k)
    ours = {c["tool"] for c in plan["captions"]}
    found = {(m, fg) for m, fg, _ in text_merges(body) if fg not in ours}
    assert found == {(x["merge"], x["text_tool"]) for x in plan["disabled_text_merges"]}, found
    for x in plan["disabled_text_merges"]:
        b = block_of(body, x["merge"]); blend = source_op(b, "Blend")
        assert blend == x["blend"], x
        if blend:
            assert all(val == 0.0 for _, val in keyframes(body, blend)), x
        else:
            assert scalar(b, "Blend") == 0.0, x


def validate_step1(s1):
    """Step-1 readback must match the expected V13 identity, not just be self-consistent."""
    assert s1["project"] == COPY and s1["source_drp_sha256"] == V13_DRP_SHA
    st = s1["settings"]
    assert float(st["timelineFrameRate"]) == 30.0, st["timelineFrameRate"]
    assert (int(st["timelineResolutionWidth"]), int(st["timelineResolutionHeight"])) == (1080, 1920)
    assert "hlg" in f'{st.get("colorSpaceOutput")} {st.get("colorSpaceOutputGamma")}'.lower(), st
    assert [t["name"] for t in s1["timelines"]] == [BASE_TIMELINE]
    tl = s1["timelines"][0]; o = tl["start"]; v1 = tl["tracks"]["video1"]
    assert [(i["start"] - o, i["end"] - o) for i in v1] == V1
    for i in v1:
        assert i["source_start"] == i["start"] - o + SRC_OFFSET, (i["name"], i["source_start"])
        assert Path(i["file"]).name == "IMG_5739.MOV" and float(i["media"]["FPS"]) == 30.0, i["media"]
        assert i["comp_names"] == ["Composition 1"], i["comp_names"]
        assert all(abs(float(i["props"][k]) - val) < 1e-9 for k, val in NEUTRAL.items()), i["props"]
    audio_items = [a for k, items in tl["tracks"].items() if k.startswith("audio") for a in items]
    assert len(audio_items) == 1, audio_items
    a = audio_items[0]
    assert Path(a["file"]).name == AUDIO_FILE and (a["start"] - o, a["end"] - o) == (0, 720), a
    assert a["source_start"] == AUDIO_OFFSET, a


def check_v1(tl):
    o = tl.GetStartFrame(); items = tl.GetItemListInTrack("video", 1)
    assert [(i.GetStart() - o, i.GetEnd() - o) for i in items] == V1
    for i in items:
        assert i.GetSourceStartFrame() == i.GetStart() - o + SRC_OFFSET, (i.GetName(), i.GetSourceStartFrame())
        assert i.GetMediaPoolItem().GetClipProperty("File Name") == "IMG_5739.MOV"
        assert all(abs(float(i.GetProperty(k)) - val) < 1e-9 for k, val in NEUTRAL.items()), i.GetProperty()
    return items


def audio(tl):
    o = tl.GetStartFrame()
    return [(n, i.GetName(), i.GetStart() - o, i.GetEnd() - o, i.GetSourceStartFrame(), i.GetSourceEndFrame())
            for n in range(1, tl.GetTrackCount("audio") + 1) for i in tl.GetItemListInTrack("audio", n) or []]


def base_comp_hashes(base, tag):
    out = {}
    for idx in BUILD_CLIPS:
        fp = OUT / "comps" / f"BASE_clip{idx}_{tag}.comp"
        assert base.GetItemListInTrack("video", 1)[idx].ExportFusionComp(str(fp), 1)
        out[idx] = sha(fp)
    return out


def job_ids(p): return [j.get("JobId") for j in p.GetRenderJobList() or []]


def render(r, p, tl, key, out=OUT, timeout=RENDER_TIMEOUT_S, poll=0.5, clock=time.monotonic, sleep=time.sleep):
    assert p.SetCurrentTimeline(tl) and r.OpenPage("deliver")
    o = tl.GetStartFrame(); target = out / f"{key}_RENDER"; target.mkdir(exist_ok=False)
    name = f"AKI_V13_AB_{key}_PREVIEW_V01_HLG_PRORES"
    path = target / f"{name}.mov"
    assert p.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
    p.SetCurrentRenderMode(1)
    assert p.SetRenderSettings({"SelectAllFrames": False, "MarkIn": o + EXCERPT[0], "MarkOut": o + EXCERPT[1] - 1,
                                "TargetDir": str(target), "CustomName": name, "ExportVideo": True, "ExportAudio": True,
                                "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
                                "AudioCodec": "lpcm", "AudioSampleRate": 48000, "AudioBitDepth": 24})
    assert p.GetCurrentRenderFormatAndCodec() == {"format": "mov", "codec": "ProRes422HQ"}
    job = p.AddRenderJob(); assert job
    assert job_ids(p) == [job], "render queue not exclusively owned by this run - refusing to start"
    job_readback = p.GetRenderJobList()
    hold_file = out / f"STEP2_RENDER_HOLD_{key}.json"

    def hold(state):
        state.update({"variant": key, "job_id": job, "job_readback": job_readback, "expected_output": str(path),
                      "file_present": path.is_file()})
        hold_file.write_text(json.dumps(state, indent=1, default=str))
        raise BuildHold(f"{state['status']} {key} job {job}")

    started = clock(); assert p.StartRendering([job], False)
    while p.IsRenderingInProgress() and clock() - started < timeout:
        sleep(poll)
    if p.IsRenderingInProgress():
        # Resolve exposes only project-level StopRendering(); use it only while this run's job is the sole queued job.
        owned = job_ids(p) == [job]
        stopped = False
        if owned:
            p.StopRendering()
            t0 = clock()
            while p.IsRenderingInProgress() and clock() - t0 < STOP_TIMEOUT_S:
                sleep(poll)
            stopped = not p.IsRenderingInProgress()
        hold({"status": "TIMEOUT_HOLD", "timeout_s": timeout, "sole_job_owned": owned, "stop_requested": owned,
              "stopped_verified": stopped, "job_status": p.GetRenderJobStatus(job)})
    status = p.GetRenderJobStatus(job)
    if status.get("JobStatus") != "Complete" or not path.is_file():
        hold({"status": "RENDER_FAILED_HOLD", "job_status": status})
    p.DeleteRenderJob(job)        # only the job this run created, only after verified completion
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size, "status": status,
            "job_readback": job_readback, "mark_in_out_inclusive": [EXCERPT[0], EXCERPT[1] - 1],
            "seconds": round(clock() - started, 3)}


def build(d, receipt):
    assert sha(V13_DRP) == V13_DRP_SHA
    step1_path = OUT / "readback" / "STEP1_IMPORT_READBACK.json"
    step1 = json.loads(step1_path.read_text())
    validate_step1(step1)
    receipt["step1_readback_sha256"] = sha(step1_path)
    (OUT / "comps").mkdir(exist_ok=False)
    r = d.scriptapp("Resolve"); assert r
    pm = r.GetProjectManager(); p = pm.GetCurrentProject()
    assert p and p.GetName() == COPY, "open project is not the isolated copy - refusing"
    assert not p.IsRenderingInProgress() and not p.GetRenderJobList(), "render jobs present in copy"
    for k, val in step1["settings"].items():
        assert p.GetSetting(k) == val, k
    assert p.GetTimelineCount() == 1
    base = p.GetTimelineByIndex(1); assert base.GetName() == BASE_TIMELINE
    check_v1(base); base_audio = audio(base); before = base_comp_hashes(base, "before")
    for key, v in VARIANTS.items():
        tl = base.DuplicateTimeline(v["timeline"]); assert tl and tl.GetName() == v["timeline"]
        assert p.SetCurrentTimeline(tl)
        items = check_v1(tl); assert audio(tl) == base_audio
        clips = []
        for idx in BUILD_CLIPS:
            it = items[idx]; assert it.GetFusionCompNameList() == ["Composition 1"], it.GetFusionCompNameList()
            src = OUT / "comps" / f"{key}_clip{idx}_source.comp"; assert it.ExportFusionComp(str(src), 1)
            patched, plan = patch_clip(src.read_text(encoding="utf-8"), key, v, idx)
            dst = OUT / "comps" / f"{key}_clip{idx}_patched.comp"; dst.write_text(patched, encoding="utf-8")
            verify_readback(patched, plan)
            assert it.ImportFusionComp(str(dst))
            new = [n for n in it.GetFusionCompNameList() if n != "Composition 1"]; assert len(new) == 1
            assert it.LoadFusionCompByName(new[0]) and it.DeleteFusionCompByName("Composition 1")
            assert it.GetFusionCompNameList() == new
            rb = OUT / "comps" / f"{key}_clip{idx}_readback.comp"; assert it.ExportFusionComp(str(rb), 1)
            verify_readback(rb.read_text(encoding="utf-8"), plan)
            clips.append({"clip": idx, "window_extremes": plan["window_extremes"],
                          "composed_peak_total_size_in_excerpt": plan["composed_peak_total_size_in_excerpt"],
                          "disabled_text_merges": plan["disabled_text_merges"], "captions": plan["captions"],
                          "source_sha256": sha(src), "patched_sha256": sha(dst), "readback_sha256": sha(rb)})
        peak = max(zoom(v, e)[0] for e in range(360))
        receipt["variants"][key] = {
            "timeline": v["timeline"], "shots": v["shots"], "punch": v["punch"], "peak_relative_zoom": round(peak, 6),
            "peak_base_size_excl_rhythm_pulse": round(peak * R_SIZE, 6),
            "composed_peak_total_size": max(c["composed_peak_total_size_in_excerpt"] for c in clips
                                            if c["composed_peak_total_size_in_excerpt"] is not None),
            "clips": clips}
    assert audio(base) == base_audio and base_comp_hashes(base, "after") == before, "base timeline changed"
    for key, v in VARIANTS.items():
        tl = next(p.GetTimelineByIndex(i) for i in range(1, p.GetTimelineCount() + 1)
                  if p.GetTimelineByIndex(i).GetName() == v["timeline"])
        receipt["variants"][key]["render"] = render(r, p, tl, key)
    assert pm.SaveProject()
    drp = OUT / f"{COPY}.drp"; assert not drp.exists() and pm.ExportProject(COPY, str(drp), False)
    assert sha(V13_DRP) == V13_DRP_SHA and pm.GetCurrentProject().GetName() == COPY
    receipt.update({"status": "STEP2_COMPLETE_RENDERS_ONLY", "copy_drp": {"path": str(drp), "sha256": sha(drp)},
                    "v13_drp_sha256_after": sha(V13_DRP), "base_timeline_unchanged": True,
                    "review_mp4_and_media_qc": "NOT_DONE_IN_STEP2"})


def main():
    sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
    import DaVinciResolveScript as d
    receipt = {"schema": "AKI_V13_AB_PREVIEW_BUILD_V01", "revision": 2, "project": COPY, "base_timeline": BASE_TIMELINE,
               "excerpt_global_half_open": list(EXCERPT), "video_source_offset": SRC_OFFSET, "audio_source_offset": AUDIO_OFFSET,
               "zoom_anchor_pre_rhythm": F, "max_relative_zoom": MAX_ZOOM, "variants": {},
               "nitin_approval_of_result": False, "publication_authorized": False}
    try:
        build(d, receipt)
    except BaseException as exc:
        receipt["status"] = "HOLD" if isinstance(exc, BuildHold) else "FAILED"
        receipt["error"] = f"{type(exc).__name__}: {exc}"[:2000]
        (OUT / "STEP2_FAILURE_RECEIPT.json").write_text(json.dumps(receipt, indent=1, default=str))
        raise
    (OUT / "STEP2_BUILD_RENDER_RECEIPT.json").write_text(json.dumps(receipt, indent=1, default=str))
    print("STEP2_OK")


if __name__ == "__main__":
    main()
