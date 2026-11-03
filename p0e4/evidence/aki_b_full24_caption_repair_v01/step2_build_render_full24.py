"""AKI B full24 caption repair V01 - step 2: build the rhythmic B treatment over the full V13 selection [0,720)
with repaired captions, chain-logo intro/end card, and render it.
Based on the executed R4 A/B step 2 (a3ab4952...): same AB zoom layer, Fusion in-place comp swap, Fusion spline
naming and omitted-default handling. Mutates only project UNCHAINED_AKI_B_FULL24_CAPTION_REPAIR_V01 (must already be
open; never calls LoadProject). Pure helpers are importable without Resolve; Resolve is only touched as __main__."""
import hashlib, json, re, sys, time
from pathlib import Path

OUT = Path(__file__).resolve().parent
COPY = "UNCHAINED_AKI_B_FULL24_CAPTION_REPAIR_V01"
V13_DRP = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair/"
               "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp")
V13_DRP_SHA = "f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec"
CHAIN_LOGO_SHA = "5e77eb7a6590d63fc33042cdfc62582f20a77d9bd6175868c77a3b8354a7b509"
BASE_TIMELINE = "AAKHRI_FIRST_PUBLISH_PREVIEW_72_96_V01"
NEW_TIMELINE = "AKI_B_FULL24_CAPTION_REPAIR_V01"
COMPS = OUT / "comps"
V1 = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
V2_V13 = [("unchained_chain_emblem_54f.mov", 0, 54), ("visualizer_outro_120f.mov", 600, 720)]
SRC_OFFSET = 2144                 # IMG_5739 source frame = timeline frame + 2144 (DRP In values, step-1 readback)
AUDIO_FILE, AUDIO_OFFSET = "AAKHRI ISHQ MASTER 2.wav", 2160   # WAV frame = timeline frame + 2160 (72.000 s)
RANGE = (0, 720)                  # half-open; Resolve MarkIn/MarkOut = origin+0 / origin+719 (inclusive)
BUILD_CLIPS = (0, 1, 2, 3, 4, 5)
HOOK_TEXT = r"SOME LOVE STORIES\nNEVER REALLY END."
TITLE_TEXT, ARTIST_TEXT = "AAKHRI ISHQ", "UNCHAINED NITIN"
GOLD = (0.847058823529412, 0.72156862745098, 0.313725490196078)   # V13 title gold
R_CY, R_SIZE = 0.72, 2.3          # V13 UN_CONTINUOUS_RHYTHM_V03 base framing
F = (0.5, 0.5 + (1.0 - R_CY) / R_SIZE)   # pre-rhythm point that V13 maps to output top-centre (zoom anchor)
MAX_ZOOM = 1.15                   # relative to V13 framing incl. additive punch (R4 limit, not exceeded)
NEUTRAL = {"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": 0.0, "RotationAngle": 0.0,
           "CropLeft": 0.0, "CropRight": 0.0, "CropTop": 0.0, "CropBottom": 0.0}
# B treatment over [0,720): (start, end, zoom, window_dx) in global frames; [60,420) identical to the selected R4 B.
SHOTS = [(0, 60, 1.06, 0.0), (60, 120, 1.00, 0.0), (120, 180, 1.12, 0.0), (180, 240, 1.00, 0.03),
         (240, 300, 1.10, 0.0), (300, 360, 1.06, 0.0), (360, 420, 1.12, -0.02), (420, 474, 1.00, 0.0),
         (474, 548, 1.10, 0.02), (548, 600, 1.04, 0.0), (600, 656, 1.12, 0.0), (656, 720, 1.00, 0.0)]
# New cuts outside the R4 span moved to builder-measured onsets (15.80 s, 18.25 s, 21.86 s); 2 s grid elsewhere.
# Cut 240 (onset 7.88 s, -3.6 f) kept to preserve the selected R4 B span exactly. Not independently validated.
PUNCH = (0.03, 2, 8)              # +3 percentage points above shot base; attack 2 f, linear decay 8 f; every cut > 0
# Captions: (tool, text, font, style, size, y (Fusion y-up), rgb or None (default white), opacity keys global,
#            rise window global or None). Clip-local frame = global - clip start.
RISE = 0.008
CAPTIONS = {
    1: [("UN_B24_HOOK_P1", "HOOK_LINE_1", "Montserrat", "SemiBold", 0.095, 0.152, None,
         [(90, 0), (96, 1), (150, 1), (156, 0)], (90, 96)),
        ("UN_B24_HOOK_P2", "HOOK_LINE_2", "Montserrat", "SemiBold", 0.095, 0.108, None,
         [(102, 0), (108, 1), (150, 1), (156, 0)], (102, 108))],
    5: [("UN_B24_TITLE", TITLE_TEXT, "Cinzel", "SemiBold", 0.12, 0.185, GOLD, [(672, 0), (678, 1), (714, 1), (719, 0)], None),
        ("UN_B24_ARTIST", ARTIST_TEXT, "Montserrat", "SemiBold", 0.075, 0.130, None, [(672, 0), (678, 1), (714, 1), (719, 0)], None)],
}
V2_OVERLAYS = [("AKI_B_FULL24_INTRO_LOGO_30F.mov", 0, 30), ("AKI_B_FULL24_ENDCARD_LOGO_48F.mov", 672, 720)]
TEXTPLUS_DEFAULTS = {"Softness1": 0.0, "Enabled2": 0.0, "Enabled3": 0.0}   # Fusion omits default-valued inputs on export
TEXTPLUS_DEFAULT_SIZE = 0.08      # R4 readback: Fusion omitted Size exactly when it was 0.08
TEXTPLUS_DEFAULT_RGB = (1.0, 1.0, 1.0)
MIN_CLEAN_FRACTION, TARGET_CLEAN_FRACTION = 0.75, 0.80
RENDER_TIMEOUT_S, STOP_TIMEOUT_S = 1200, 60
NUM = r"-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?"


class BuildHold(RuntimeError):
    """Fail-closed stop after persisting HOLD state."""


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def zoom(g):
    assert RANGE[0] <= g < RANGE[1], g
    for s, t, z, dx in SHOTS:
        if s <= g < t:
            if s > 0:
                pp, attack, decay = PUNCH; k = g - s
                if k < attack:
                    z += pp * (k + 1) / attack
                elif k < attack + decay:
                    z += pp * (1 - (k - attack + 1) / decay)
            return z, dx
    raise AssertionError(g)


def validate_shots():
    assert SHOTS[0][0] == RANGE[0] and SHOTS[-1][1] == RANGE[1]
    for (s0, t0, z0, d0), (s1, t1, z1, d1) in zip(SHOTS, SHOTS[1:]):
        assert t0 == s1, "gap/overlap"
        assert abs(z1 - z0) >= 0.04 - 1e-9 or abs(d1 - d0) >= 0.02 - 1e-9, f"cut at {s1} has no visible reframe"


def assert_safe(z, dx):
    """Output corners mapped back to normalized source (y up). Fails closed on any edge/ceiling risk."""
    assert 1.0 - 1e-9 <= z <= MAX_ZOOM + 1e-9, z
    pts = []
    for ox in (0.0, 1.0):
        for oy in (0.0, 1.0):
            sx, sy = 0.5 + (ox - 0.5) / R_SIZE, 0.5 + (oy - R_CY) / R_SIZE
            pts.append((F[0] + (sx - F[0] + dx / R_SIZE) / z, F[1] + (sy - F[1]) / z))
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    assert min(xs) >= 0.02 and max(xs) <= 0.98, pts
    assert min(ys) >= 0.14, pts
    assert max(ys) <= F[1] + 1e-9, pts
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


def source_ops(block): return re.findall(r"\b\w+ = Input \{\s*SourceOp = \"(\w+)\"", block)


def reachable(text, root="MediaOut1"):
    seen, todo = set(), [root]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo += source_ops(block_of(text, name))
    return seen


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


def loaders_reaching_output(text):
    kinds = tools(text)
    return sorted(n for n in reachable(text) if kinds.get(n) in ("Loader", "MediaIn"))


def resolve_text(spec, hook_lines):
    if spec == "HOOK_LINE_1":
        return hook_lines[0]
    if spec == "HOOK_LINE_2":
        return hook_lines[1]
    return spec


def patch_clip(text, idx, hook_lines=None):
    start, end = V1[idx]; length = end - start
    r6 = lambda keys: [(f, round(val, 6)) for f, val in keys]
    assert loaders_reaching_output(text) == ["MediaIn1"], loaders_reaching_output(text)   # e.g. lightning lockup stays detached
    rhythm = keyframes(text, "UN_CONTINUOUS_RHYTHM_V03Size")
    assert source_op(block_of(text, "UN_CONTINUOUS_RHYTHM_V03"), "Size") == "UN_CONTINUOUS_RHYTHM_V03Size"
    texts_seen = {fg: string(block_of(text, fg), "StyledText") for _, fg, _ in text_merges(text)}
    plan = {"clip": idx, "splines": {"UN_CONTINUOUS_RHYTHM_V03Size": rhythm}, "points": {}, "kinds": {},
            "wiring": {("UN_CONTINUOUS_RHYTHM_V03", "Size"): "UN_CONTINUOUS_RHYTHM_V03Size"},
            "disabled_text_merges": [], "captions": [], "existing_texts": texts_seen,
            "detached_tools_present": sorted(set(tools(text)) - reachable(text))}
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
        z, dx = zoom(start + local)
        windows.append(assert_safe(z, dx))
        zs.append((local, z)); xs.append((local, 0.5 - dx / R_SIZE))
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
    for name, spec, font, style, size, y, rgb, opacity, rise in CAPTIONS.get(idx, []):
        words = resolve_text(spec, hook_lines)
        local = lambda g: g - start
        assert all(start <= g < end for g, _ in opacity), (name, "caption window outside clip")
        okeys = [(0, 0.0)] + [(local(g), float(o)) for g, o in opacity] + ([(length - 1, 0.0)] if local(opacity[-1][0]) < length - 1 else [])
        ykeys = r6([(0, y - RISE), (local(rise[0]), y - RISE), (local(rise[1]), y), (length - 1, y)] if rise else [(0, y), (length - 1, y)])
        plan["splines"].update({f"{name}CenterX": [(0, 0.5), (length - 1, 0.5)], f"{name}CenterY": ykeys, f"{name}MergeBlend": okeys})
        plan["kinds"].update({name: "TextPlus", f"{name}Center": "XYPath", f"{name}Merge": "Merge"})
        plan["wiring"].update({(name, "Center"): f"{name}Center", (f"{name}Center", "X"): f"{name}CenterX",
                               (f"{name}Center", "Y"): f"{name}CenterY", (f"{name}Merge", "Blend"): f"{name}MergeBlend",
                               (f"{name}Merge", "Background"): last, (f"{name}Merge", "Foreground"): name})
        colour = [inp(k, value=v) for k, v in zip(("Red1", "Green1", "Blue1"), rgb)] if rgb else []
        blocks += [spline(f"{name}CenterX", plan["splines"][f"{name}CenterX"]), spline(f"{name}CenterY", ykeys),
                   xypath(f"{name}Center", f"{name}CenterX", f"{name}CenterY"),
                   tool(name, "TextPlus", [inp("Width", value=2160), inp("Height", value=3840),
                        inp("UseFrameFormatSettings", value=1), inp("Center", f"{name}Center", source="Value"),
                        inp("StyledText", value=f'"{words}"'), inp("Font", value=f'"{font}"'),
                        inp("Style", value=f'"{style}"'), inp("Size", value=size), *colour,
                        inp("Softness1", value=0), inp("Enabled2", value=0), inp("Enabled3", value=0),
                        inp("VerticalJustificationNew", value=3), inp("HorizontalJustificationNew", value=3)]),
                   spline(f"{name}MergeBlend", okeys),
                   tool(f"{name}Merge", "Merge", [inp("Blend", f"{name}MergeBlend", source="Value"), inp("Background", last),
                                                  inp("Foreground", name), inp("PerformDepthMerge", value=0)])]
        plan["captions"].append({"tool": name, "text": words, "font": font, "style": style, "size": size, "y": y,
                                 "rgb": list(rgb) if rgb else list(TEXTPLUS_DEFAULT_RGB), "opacity_global_keys": opacity,
                                 "rise_global": rise})
        last = f"{name}Merge"
    if last != first:
        text = rewire(text, "MediaOut1", "Input", first, last)
    plan["wiring"][("MediaOut1", "Input")] = last
    for (tool_name, input_name), op in plan["wiring"].items():
        if op in plan["splines"]:   # Fusion renames animation splines to <Tool><Input> on import
            assert op == tool_name + input_name, (tool_name, input_name, op)
    text, n = re.subn(r"\n\tTools = (?:ordered\(\) )?\{\n", lambda m: m.group(0) + "".join(blocks), text, count=1)
    assert n == 1
    plan["window_extremes"] = [min(w[0] for w in windows), max(w[1] for w in windows),
                               min(w[2] for w in windows), max(w[3] for w in windows)]
    plan["composed_peak_total_size"] = round(max(composed), 6)
    return text, plan


def verify_readback(body, plan):
    """Every planned spline, connection, static point, caption setting, disabled caption and output reachability must match."""
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
        assert abs(scalar(b, "Size", TEXTPLUS_DEFAULT_SIZE) - c["size"]) < 1e-9, c
        for k, default, want in zip(("Red1", "Green1", "Blue1"), TEXTPLUS_DEFAULT_RGB, c["rgb"]):
            assert abs(scalar(b, k, default) - want) < 1e-9, (c["tool"], k)
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
    assert loaders_reaching_output(body) == ["MediaIn1"], loaders_reaching_output(body)


def overlay_frames(caption_plans, v2_items):
    """Union of global frames with any overlay alpha > 0 possible: V2 overlay windows plus caption opacity > 0."""
    frames = set()
    for name, a, b in v2_items:
        frames.update(range(a, b))
    for idx, keys in caption_plans:
        start, end = V1[idx]
        frames.update(start + l for l in range(end - start) if interp(keys, l) > 0)
    return frames


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
    assert [(Path(i["file"]).name, i["start"] - o, i["end"] - o) for i in tl["tracks"]["video2"]] == V2_V13
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


def v2_state(tl):
    o = tl.GetStartFrame()
    return [(i.GetMediaPoolItem().GetClipProperty("File Name"), i.GetStart() - o, i.GetEnd() - o)
            for i in tl.GetItemListInTrack("video", 2) or []]


def audio(tl):
    o = tl.GetStartFrame()
    return [(n, i.GetName(), i.GetStart() - o, i.GetEnd() - o, i.GetSourceStartFrame(), i.GetSourceEndFrame())
            for n in range(1, tl.GetTrackCount("audio") + 1) for i in tl.GetItemListInTrack("audio", n) or []]


def swap_comp(it, dst):
    """Resolve 21.1 replaced 'Composition 1' in place in R4; accept that or the add-new behaviour; content proven by readback."""
    assert it.ImportFusionComp(str(dst))
    names = it.GetFusionCompNameList()
    if names == ["Composition 1"]:
        return "REPLACED_IN_PLACE"
    new = [n for n in names if n != "Composition 1"]
    assert len(new) == 1 and "Composition 1" in names, names
    assert it.LoadFusionCompByName(new[0]) and it.DeleteFusionCompByName("Composition 1")
    assert it.GetFusionCompNameList() == new
    return "ADDED_THEN_OLD_DELETED"


def replace_v2(p, tl, manifest):
    """Remove V13 intro emblem/outro card from the NEW timeline's V2 and place the derived chain-logo overlays."""
    assert v2_state(tl) == V2_V13, v2_state(tl)
    assert tl.DeleteClips(tl.GetItemListInTrack("video", 2), False)
    assert not tl.GetItemListInTrack("video", 2)
    files = {o["file"]: o for o in manifest["overlays"]}
    pool = p.GetMediaPool(); o = tl.GetStartFrame(); placed = []
    for name, a, b in V2_OVERLAYS:
        path = OUT / name
        assert sha(path) == files[name]["sha256"] and files[name]["frames"] == b - a, name
        media = pool.ImportMedia([str(path)]); assert media and len(media) == 1, name
        mpi = media[0]
        if mpi.GetClipProperty("Input Color Space") != "Project":   # same interpretation as the V13 emblem
            assert mpi.SetClipProperty("Input Color Space", "Project"), name
        assert mpi.GetClipProperty("Input Color Space") == "Project", name
        item = pool.AppendToTimeline([{"mediaPoolItem": mpi, "startFrame": 0, "endFrame": b - a, "mediaType": 1,
                                       "trackIndex": 2, "recordFrame": o + a}])
        assert item and len(item) == 1, name
        it = item[0]
        assert (it.GetStart() - o, it.GetEnd() - o) == (a, b), (name, it.GetStart() - o, it.GetEnd() - o)
        assert it.GetSourceStartFrame() == 0, (name, it.GetSourceStartFrame())
        assert all(abs(float(it.GetProperty(k)) - val) < 1e-9 for k, val in NEUTRAL.items()), it.GetProperty()
        assert float(it.GetProperty("Opacity")) == 100.0 and int(it.GetProperty("CompositeMode")) == 0, it.GetProperty()
        placed.append({"file": name, "sha256": files[name]["sha256"], "timeline_frames": [a, b],
                       "input_color_space": mpi.GetClipProperty("Input Color Space")})
    assert v2_state(tl) == [(n, a, b) for n, a, b in V2_OVERLAYS], v2_state(tl)
    return placed


def base_snapshot(base):
    out = {}
    for idx in BUILD_CLIPS:
        fp = COMPS / f"BASE_clip{idx}_snapshot_{len(list(COMPS.glob(f'BASE_clip{idx}_snapshot_*')))}.comp"
        assert base.GetItemListInTrack("video", 1)[idx].ExportFusionComp(str(fp), 1)
        out[idx] = sha(fp)
    return {"comps": out, "v2": v2_state(base), "audio": audio(base)}


def job_ids(p): return [j.get("JobId") for j in p.GetRenderJobList() or []]


def render(r, p, tl, out=OUT, timeout=RENDER_TIMEOUT_S, poll=0.5, clock=time.monotonic, sleep=time.sleep):
    assert p.SetCurrentTimeline(tl) and r.OpenPage("deliver")
    o = tl.GetStartFrame(); target = out / "RENDER"; target.mkdir(exist_ok=False)
    name = "AKI_B_FULL24_CAPTION_REPAIR_V01_HLG_PRORES"
    path = target / f"{name}.mov"
    assert p.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
    p.SetCurrentRenderMode(1)
    assert p.SetRenderSettings({"SelectAllFrames": False, "MarkIn": o + RANGE[0], "MarkOut": o + RANGE[1] - 1,
                                "TargetDir": str(target), "CustomName": name, "ExportVideo": True, "ExportAudio": True,
                                "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30,
                                "AudioCodec": "lpcm", "AudioSampleRate": 48000, "AudioBitDepth": 24})
    assert p.GetCurrentRenderFormatAndCodec() == {"format": "mov", "codec": "ProRes422HQ"}
    job = p.AddRenderJob(); assert job
    assert job_ids(p) == [job], "render queue not exclusively owned by this run - refusing to start"
    job_readback = p.GetRenderJobList()
    hold_file = out / "STEP2_RENDER_HOLD.json"

    def hold(state):
        state.update({"job_id": job, "job_readback": job_readback, "expected_output": str(path), "file_present": path.is_file()})
        hold_file.write_text(json.dumps(state, indent=1, default=str))
        raise BuildHold(f"{state['status']} job {job}")

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
            "job_readback": job_readback, "mark_in_out_inclusive": [RANGE[0], RANGE[1] - 1],
            "seconds": round(clock() - started, 3)}


def build(d, receipt):
    assert sha(V13_DRP) == V13_DRP_SHA
    validate_shots()
    step1_path = OUT / "readback" / "STEP1_IMPORT_READBACK.json"
    step1 = json.loads(step1_path.read_text())
    validate_step1(step1)
    receipt["step1_readback_sha256"] = sha(step1_path)
    manifest = json.loads((OUT / "OVERLAY_MANIFEST.json").read_text())
    assert manifest["source_logo_sha256"] == CHAIN_LOGO_SHA
    receipt["overlay_manifest_sha256"] = sha(OUT / "OVERLAY_MANIFEST.json")
    COMPS.mkdir(exist_ok=False)
    r = d.scriptapp("Resolve"); assert r
    pm = r.GetProjectManager(); p = pm.GetCurrentProject()
    assert p and p.GetName() == COPY, "open project is not the isolated copy - refusing"
    assert not p.IsRenderingInProgress() and not p.GetRenderJobList(), "render jobs present in copy"
    for k, val in step1["settings"].items():
        assert p.GetSetting(k) == val, k
    assert p.GetTimelineCount() == 1
    base = p.GetTimelineByIndex(1); assert base.GetName() == BASE_TIMELINE
    check_v1(base); before = base_snapshot(base)
    tl = base.DuplicateTimeline(NEW_TIMELINE); assert tl and tl.GetName() == NEW_TIMELINE
    assert p.SetCurrentTimeline(tl)
    items = check_v1(tl); assert audio(tl) == before["audio"]
    clips, caption_plans, hook_lines = [], [], None
    for idx in BUILD_CLIPS:
        it = items[idx]; assert it.GetFusionCompNameList() == ["Composition 1"], it.GetFusionCompNameList()
        src = COMPS / f"clip{idx}_source.comp"; assert it.ExportFusionComp(str(src), 1)
        source_text = src.read_text(encoding="utf-8")
        if idx == 1:   # exact existing texts are read back, never invented
            hook = string(block_of(source_text, "UN_BRAND_HOOK"), "StyledText"); assert hook == HOOK_TEXT, hook
            hook_lines = hook.split(r"\n"); assert len(hook_lines) == 2
            assert string(block_of(source_text, "UN_BRAND_TITLE"), "StyledText") == TITLE_TEXT
            assert string(block_of(source_text, "UN_BRAND_ARTIST"), "StyledText") == ARTIST_TEXT
        patched, plan = patch_clip(source_text, idx, hook_lines)
        dst = COMPS / f"clip{idx}_patched.comp"; dst.write_text(patched, encoding="utf-8")
        verify_readback(patched, plan)
        swap_mode = swap_comp(it, dst)
        rb = COMPS / f"clip{idx}_readback.comp"; assert it.ExportFusionComp(str(rb), 1)
        verify_readback(rb.read_text(encoding="utf-8"), plan)
        caption_plans += [(idx, keyframes(rb.read_text(encoding="utf-8"), f'{c["tool"]}MergeBlend')) for c in plan["captions"]]
        clips.append({"clip": idx, "comp_swap": swap_mode, "window_extremes": plan["window_extremes"],
                      "composed_peak_total_size": plan["composed_peak_total_size"],
                      "disabled_text_merges": plan["disabled_text_merges"], "detached_tools_present": plan["detached_tools_present"],
                      "captions": plan["captions"], "source_sha256": sha(src), "patched_sha256": sha(dst), "readback_sha256": sha(rb)})
    placed = replace_v2(p, tl, manifest)
    after = base_snapshot(base)
    assert after == before, "base timeline changed"
    union = overlay_frames(caption_plans, V2_OVERLAYS)
    clean = 1 - len(union) / (RANGE[1] - RANGE[0])
    assert clean >= MIN_CLEAN_FRACTION, clean
    receipt.update({"timeline": NEW_TIMELINE, "shots": SHOTS, "punch": PUNCH,
                    "peak_relative_zoom": round(max(zoom(g)[0] for g in range(*RANGE)), 6),
                    "composed_peak_total_size": max(c["composed_peak_total_size"] for c in clips),
                    "clips": clips, "v2_overlays": placed,
                    "overlay_budget": {"overlay_frames": len(union), "clean_fraction": round(clean, 4),
                                       "meets_75_min": clean >= MIN_CLEAN_FRACTION, "meets_80_target": clean >= TARGET_CLEAN_FRACTION - 1e-9,
                                       "basis": "V2 overlay windows + caption MergeBlend > 0 from Resolve readback"}})
    receipt["render"] = render(r, p, tl)
    assert pm.SaveProject()
    drp = OUT / f"{COPY}.drp"; assert not drp.exists() and pm.ExportProject(COPY, str(drp), False)
    assert sha(V13_DRP) == V13_DRP_SHA and pm.GetCurrentProject().GetName() == COPY
    receipt.update({"status": "STEP2_COMPLETE_RENDER_ONLY", "copy_drp": {"path": str(drp), "sha256": sha(drp)},
                    "v13_drp_sha256_after": sha(V13_DRP), "base_timeline_unchanged": True,
                    "review_mp4_and_media_qc": "NOT_DONE_IN_STEP2"})


def main():
    sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
    import DaVinciResolveScript as d
    receipt = {"schema": "AKI_B_FULL24_CAPTION_REPAIR_BUILD_V01", "script_sha256": sha(__file__), "project": COPY,
               "base_timeline": BASE_TIMELINE, "range_global_half_open": list(RANGE), "video_source_offset": SRC_OFFSET,
               "audio_source_offset": AUDIO_OFFSET, "zoom_anchor_pre_rhythm": F, "max_relative_zoom": MAX_ZOOM,
               "nitin_final_approval": False, "publication_authorized": False}
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
