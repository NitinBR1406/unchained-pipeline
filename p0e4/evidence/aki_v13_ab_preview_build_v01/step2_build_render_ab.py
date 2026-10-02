"""AKI V13 A/B preview build V01 - step 2: build A/B timelines inside the isolated copy and render global [60,420).
Mutates only project UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01 (must already be open; never calls LoadProject)."""
import hashlib, json, re, sys, time
from pathlib import Path
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
import DaVinciResolveScript as d

OUT = Path(__file__).resolve().parent
COPY = "UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01"
V13_DRP = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair/"
               "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp")
V13_DRP_SHA = "f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec"
BASE_TIMELINE = "AAKHRI_FIRST_PUBLISH_PREVIEW_72_96_V01"
V1 = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
SRC_OFFSET = 2144                 # IMG_5739 source frame = timeline frame + 2144 (DRP In values)
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


def tools(text): return dict(re.findall(r"\n\t\t(\w+) = (\w+) \{\n", text))


def span(text, name):
    m = re.search(rf"\n\t\t{re.escape(name)} = \w+ \{{\n", text); assert m, f"missing tool {name}"
    end = re.compile(r"\n\t\t\},?\n").search(text, m.end() - 1)
    return m.start() + 1, end.end()


def source_op(block, name):
    m = re.search(rf"\b{name} = Input \{{\n\t+SourceOp = \"(\w+)\"", block)
    return m.group(1) if m else None


def rewire(text, tool_name, input_name, old, new):
    s, e = span(text, tool_name)
    patched, n = re.subn(rf"(\b{input_name} = Input \{{\n\t+SourceOp = \"){re.escape(old)}\"", rf'\g<1>{new}"', text[s:e])
    assert n == 1, (tool_name, input_name, old)
    return text[:s] + patched + text[e:]


def spline(name, keys):
    rows = "\n".join(f"\t\t\t\t[{f}] = {{ {round(v, 6)}, Flags = {{ Linear = true }} }}," for f, v in keys)
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


def styled_text(text, name):
    s, e = span(text, name)
    m = re.search(r'StyledText = Input \{ Value = "((?:[^"\\]|\\.)*)", \}', text[s:e]); assert m
    return m.group(1)


def text_merges(text):
    kinds = tools(text)
    for name, kind in kinds.items():
        if kind == "Merge":
            s, e = span(text, name)
            fg = source_op(text[s:e], "Foreground")
            if kinds.get(fg) == "TextPlus":
                yield name, fg, source_op(text[s:e], "Blend")


def patch_clip(text, key, v, idx):
    start, end = V1[idx]; length = end - start
    disabled = []
    for merge, fg, blend in list(text_merges(text)):
        if blend:
            s, e = span(text, blend)
            text = text[:s] + spline(blend, [(0, 0.0), (length - 1, 0.0)]) + text[e:]
        else:
            s, e = span(text, merge)
            text = text[:s] + text[s:e].replace("\t\t\tInputs = {\n", "\t\t\tInputs = {\n" + inp("Blend", value=0), 1) + text[e:]
        disabled.append({"merge": merge, "text_tool": fg})
    zs, xs, windows = [], [], []
    for local in range(length):
        z, dx = zoom(v, start + local - EXCERPT[0])
        windows.append(assert_safe(z, dx))
        zs.append((local, z)); xs.append((local, 0.5 - dx / R_SIZE))
    blocks = [
        tool("UN_AB_T1", "Transform", [inp("Input", "MediaIn1"), inp("Center", value=f"{{ 0.5, {round(1 - F[1], 9)} }}")]),
        spline("UN_AB_T2Size", zs), spline("UN_AB_T2CenterX", xs), spline("UN_AB_T2CenterY", [(0, 0.5), (length - 1, 0.5)]),
        xypath("UN_AB_T2Center", "UN_AB_T2CenterX", "UN_AB_T2CenterY"),
        tool("UN_AB_T2", "Transform", [inp("Input", "UN_AB_T1"), inp("Size", "UN_AB_T2Size", source="Value"),
                                       inp("Center", "UN_AB_T2Center", source="Value")]),
        tool("UN_AB_T3", "Transform", [inp("Input", "UN_AB_T2"), inp("Center", value=f"{{ 0.5, {round(F[1], 9)} }}")]),
    ]
    text = rewire(text, "UN_CONTINUOUS_RHYTHM_V03", "Input", "MediaIn1", "UN_AB_T3")
    captions = []
    if idx == TEXT_CLIP:
        hook = styled_text(text, "UN_BRAND_HOOK"); assert hook == HOOK_TEXT, hook
        lines = hook.split(r"\n"); assert len(lines) == 2
        s, e = span(text, "MediaOut1"); first = last = source_op(text[s:e], "Input")
        local = lambda ex: ex + EXCERPT[0] - start
        for name, part, y, opacity, rise in v["captions"]:
            words = hook if part == 0 else lines[part - 1]
            okeys = [(0, 0.0)] + [(local(ex), float(o)) for ex, o in opacity] + [(length - 1, 0.0)]
            ykeys = ([(0, y - RISE), (local(rise[0]), y - RISE), (local(rise[1]), y), (length - 1, y)]
                     if rise else [(0, y), (length - 1, y)])
            blocks += [spline(f"{name}CX", [(0, 0.5), (length - 1, 0.5)]), spline(f"{name}CY", ykeys),
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
            captions.append({"tool": name, "text": words, "font": "Montserrat", "style": v["style"], "size": TEXT_SIZE,
                             "opacity_local_keys": okeys, "center_y_local_keys": ykeys,
                             "opacity_excerpt_keys": opacity, "rise_excerpt": rise})
            last = f"{name}Merge"
        text = rewire(text, "MediaOut1", "Input", first, last)
    text, n = re.subn(r"\n\tTools = (?:ordered\(\) )?\{\n", lambda m: m.group(0) + "".join(blocks), text, count=1)
    assert n == 1
    return text, {"clip": idx, "zoom": [(f, round(z, 6)) for f, z in zs], "disabled_text_merges": disabled,
                  "captions": captions, "window_extremes": [min(w[0] for w in windows), max(w[1] for w in windows),
                                                            min(w[2] for w in windows), max(w[3] for w in windows)]}


def verify_readback(body, v, plan):
    kinds = tools(body)
    for t in ("UN_AB_T1", "UN_AB_T2", "UN_AB_T3", "UN_AB_T2Size", "UN_AB_T2Center"):
        assert t in kinds, t
    s, e = span(body, "UN_CONTINUOUS_RHYTHM_V03"); assert source_op(body[s:e], "Input") == "UN_AB_T3"
    s, e = span(body, "UN_AB_T2Size")
    got = [(int(f), float(x)) for f, x in re.findall(r"\[(\d+)\] = \{ (-?[\d.e-]+),", body[s:e])]
    assert len(got) == len(plan["zoom"]) and all(a == b and abs(x - y) < 1e-5 for (a, x), (b, y) in zip(got, plan["zoom"]))
    ours = {c["tool"] for c in plan["captions"]}
    for merge, fg, blend in text_merges(body):
        if fg in ours:
            continue
        assert blend, merge
        s, e = span(body, blend)
        assert all(float(x) == 0.0 for x in re.findall(r"\] = \{ (-?[\d.e-]+),", body[s:e])), merge
    for c in plan["captions"]:
        s, e = span(body, c["tool"]); block = body[s:e]
        for needle in (f'Font = Input {{ Value = "Montserrat", }}', f'Style = Input {{ Value = "{v["style"]}", }}',
                       f'StyledText = Input {{ Value = "{c["text"]}", }}'):
            assert needle in block, (c["tool"], needle)


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


def render(r, p, tl, key):
    assert p.SetCurrentTimeline(tl) and r.OpenPage("deliver")
    o = tl.GetStartFrame(); target = OUT / f"{key}_RENDER"; target.mkdir(exist_ok=False)
    name = f"AKI_V13_AB_{key}_PREVIEW_V01_HLG_PRORES"
    assert p.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
    p.SetCurrentRenderMode(1)
    assert p.SetRenderSettings({"SelectAllFrames": False, "MarkIn": o + EXCERPT[0], "MarkOut": o + EXCERPT[1] - 1,
                                "TargetDir": str(target), "CustomName": name, "ExportVideo": True, "ExportAudio": True,
                                "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
                                "AudioCodec": "lpcm", "AudioSampleRate": 48000, "AudioBitDepth": 24})
    assert p.GetCurrentRenderFormatAndCodec() == {"format": "mov", "codec": "ProRes422HQ"}
    job = p.AddRenderJob(); assert job
    job_readback = [j for j in p.GetRenderJobList() if j.get("JobId") == job]
    started = time.monotonic(); assert p.StartRendering([job], False)
    while p.IsRenderingInProgress() and time.monotonic() - started < 900:
        time.sleep(0.5)
    status = p.GetRenderJobStatus(job)
    path = target / f"{name}.mov"
    assert status.get("JobStatus") == "Complete" and path.is_file(), status
    p.DeleteRenderJob(job)
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size, "status": status,
            "job_readback": job_readback, "mark_in_out_inclusive": [EXCERPT[0], EXCERPT[1] - 1],
            "seconds": round(time.monotonic() - started, 3)}


assert sha(V13_DRP) == V13_DRP_SHA
step1 = json.loads((OUT / "readback" / "STEP1_IMPORT_READBACK.json").read_text())
assert step1["project"] == COPY
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
receipt = {"schema": "AKI_V13_AB_PREVIEW_BUILD_V01", "project": COPY, "base_timeline": BASE_TIMELINE,
           "excerpt_global_half_open": list(EXCERPT), "video_source_offset": SRC_OFFSET, "zoom_anchor_pre_rhythm": F,
           "max_relative_zoom": MAX_ZOOM, "variants": {}}
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
        assert it.ImportFusionComp(str(dst))
        new = [n for n in it.GetFusionCompNameList() if n != "Composition 1"]; assert len(new) == 1
        assert it.LoadFusionCompByName(new[0]) and it.DeleteFusionCompByName("Composition 1")
        assert it.GetFusionCompNameList() == new
        rb = OUT / "comps" / f"{key}_clip{idx}_readback.comp"; assert it.ExportFusionComp(str(rb), 1)
        verify_readback(rb.read_text(encoding="utf-8"), v, plan)
        clips.append({**plan, "source_sha256": sha(src), "patched_sha256": sha(dst), "readback_sha256": sha(rb)})
    peak = max(zoom(v, e)[0] for e in range(360))
    receipt["variants"][key] = {"timeline": v["timeline"], "shots": v["shots"], "punch": v["punch"],
                                "peak_relative_zoom": round(peak, 6), "peak_total_fusion_size": round(peak * R_SIZE, 6),
                                "clips": clips}
assert audio(base) == base_audio and base_comp_hashes(base, "after") == before, "base timeline changed"
for key, v in VARIANTS.items():
    tl = next(p.GetTimelineByIndex(i) for i in range(1, p.GetTimelineCount() + 1)
              if p.GetTimelineByIndex(i).GetName() == v["timeline"])
    receipt["variants"][key]["render"] = render(r, p, tl, key)
assert pm.SaveProject()
drp = OUT / f"{COPY}.drp"; assert not drp.exists() and pm.ExportProject(COPY, str(drp), False)
assert sha(V13_DRP) == V13_DRP_SHA and pm.GetCurrentProject().GetName() == COPY
receipt.update({"copy_drp": {"path": str(drp), "sha256": sha(drp)}, "v13_drp_sha256_after": sha(V13_DRP),
                "base_timeline_unchanged": True, "nitin_approval_of_result": False, "publication_authorized": False})
(OUT / "STEP2_BUILD_RENDER_RECEIPT.json").write_text(json.dumps(receipt, indent=1, default=str))
print("STEP2_OK")
