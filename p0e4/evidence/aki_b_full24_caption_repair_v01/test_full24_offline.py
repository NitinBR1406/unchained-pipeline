"""Offline tests for step2_build_render_full24.py. Never imports DaVinciResolveScript or touches Resolve."""
import copy, importlib.util, json, re, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("s2", HERE / "step2_build_render_full24.py")
s2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s2)
FIX = HERE / "fixtures"
REAL = {i: (FIX / f"v13_clip{i}_resolve_export.comp").read_text(encoding="utf-8") for i in range(6)}
HOOK_LINES = s2.string(s2.block_of(REAL[1], "UN_BRAND_HOOK"), "StyledText").split(r"\n")


def set_spline_value(text, name, frame, value):
    s, e = s2.span(text, name)
    block, n = re.subn(rf"\[{frame}\] = \{{ {s2.NUM}", f"[{frame}] = {{ {value}", text[s:e], count=1)
    assert n == 1
    return text[:s] + block + text[e:]


def replace_in_tool(text, name, old, new):
    s, e = s2.span(text, name)
    assert old in text[s:e], (name, old)
    return text[:s] + text[s:e].replace(old, new, 1) + text[e:]


class RealV13Clips(unittest.TestCase):
    def setUp(self):
        self.patched = {i: s2.patch_clip(REAL[i], i, HOOK_LINES) for i in range(6)}

    def test_existing_texts_exact(self):
        self.assertEqual(HOOK_LINES, ["SOME LOVE STORIES", "NEVER REALLY END."])
        texts = s2.patch_clip(REAL[1], 1, HOOK_LINES)[1]["existing_texts"]
        self.assertEqual(texts["UN_BRAND_TITLE"], s2.TITLE_TEXT); self.assertEqual(texts["UN_BRAND_ARTIST"], s2.ARTIST_TEXT)

    def test_all_clips_patch_and_verify(self):
        for i, (body, plan) in self.patched.items():
            with self.subTest(clip=i):
                s2.verify_readback(body, plan)

    def test_inventory_disables_all_v13_text(self):
        disabled = {i: sorted(x["text_tool"] for x in plan["disabled_text_merges"]) for i, (_, plan) in self.patched.items()}
        self.assertEqual(disabled[0], ["UN_BRAND_HOOK", "UN_BRAND_HOOK_SONG_ID"])
        self.assertEqual(disabled[1], ["UN_BRAND_ARTIST", "UN_BRAND_HOOK", "UN_BRAND_HOOK_SONG_ID", "UN_BRAND_TITLE"])
        self.assertEqual(disabled[2], ["UN_BRAND_ARTIST", "UN_BRAND_TITLE"])
        self.assertEqual(disabled[3] + disabled[4] + disabled[5], [])

    def test_lightning_lockup_detached_in_clip5(self):
        _, plan = self.patched[5]
        self.assertIn("UN_AUTH_FULL_LOCKUP", plan["detached_tools_present"])
        bad = replace_in_tool(REAL[5], "MediaOut1", '"UN_CONTINUOUS_RHYTHM_V03"', '"Merge1"')
        with self.assertRaises(AssertionError):
            s2.patch_clip(bad, 5, HOOK_LINES)
        body, plan = self.patched[5]
        with self.assertRaises(AssertionError):
            s2.verify_readback(replace_in_tool(body, "UN_B24_TITLEMerge", '"UN_CONTINUOUS_RHYTHM_V03"', '"Merge1"'), plan)

    def test_captions_planned(self):
        c1 = self.patched[1][1]["captions"]; c5 = self.patched[5][1]["captions"]
        self.assertEqual([c["text"] for c in c1], ["SOME LOVE STORIES", "NEVER REALLY END."])
        self.assertEqual([(c["text"], c["font"], c["style"]) for c in c5],
                         [("AAKHRI ISHQ", "Cinzel", "SemiBold"), ("UNCHAINED NITIN", "Montserrat", "SemiBold")])
        for i in (0, 2, 3, 4):
            self.assertEqual(self.patched[i][1]["captions"], [])

    def test_negatives(self):
        b1, p1 = self.patched[1]; b5, p5 = self.patched[5]
        cases = {
            "hook opacity key changed": (set_spline_value(b1, "UN_B24_HOOK_P1MergeBlend", 7, 0.5), p1),
            "hook position key changed": (set_spline_value(b1, "UN_B24_HOOK_P2CenterY", 0, 0.3), p1),
            "hook text changed": (replace_in_tool(b1, "UN_B24_HOOK_P1", '"SOME LOVE STORIES"', '"SOME LOVE STORY"'), p1),
            "title colour changed": (replace_in_tool(b5, "UN_B24_TITLE", "Red1 = Input { Value = 0.847058823529412, }",
                                                     "Red1 = Input { Value = 1.0, }"), p5),
            "title colour dropped (default white)": (replace_in_tool(b5, "UN_B24_TITLE", "\t\t\t\tRed1 = Input { Value = 0.847058823529412, },\n", ""), p5),
            "artist size dropped (default 0.08)": (replace_in_tool(b5, "UN_B24_ARTIST", "\t\t\t\tSize = Input { Value = 0.075, },\n", ""), p5),
            "title font changed": (replace_in_tool(b5, "UN_B24_TITLE", '"Cinzel"', '"Open Sans"'), p5),
            "output disconnected": (replace_in_tool(b5, "MediaOut1", '"UN_B24_ARTISTMerge"', '"UN_CONTINUOUS_RHYTHM_V03"'), p5),
            "v13 hook re-enabled": (set_spline_value(b1, "Merge1Blend", 114, 1), p1),
            "rhythm bypasses AB layer": (replace_in_tool(b1, "UN_CONTINUOUS_RHYTHM_V03", '"UN_AB_T3"', '"MediaIn1"'), p1),
            "zoom key changed": (set_spline_value(b1, "UN_AB_T2Size", 40, 1.2), p1),
        }
        for label, (body, plan) in cases.items():
            with self.subTest(label):
                with self.assertRaises(AssertionError):
                    s2.verify_readback(body, plan)

    def test_spline_names_follow_fusion_convention(self):
        for i, (_, plan) in self.patched.items():
            for (tool_name, input_name), op in plan["wiring"].items():
                if op in plan["splines"]:
                    self.assertEqual(op, tool_name + input_name)

    def test_overlay_budget(self):
        caps = [(i, dict(plan["splines"])[f'{c["tool"]}MergeBlend']) for i, (_, plan) in self.patched.items() for c in plan["captions"]]
        frames = s2.overlay_frames(caps, s2.V2_OVERLAYS)
        self.assertEqual(len(frames), 143)
        self.assertGreaterEqual(1 - len(frames) / 720, s2.TARGET_CLEAN_FRACTION)


class Schedule(unittest.TestCase):
    def test_shots_visible_and_safe(self):
        s2.validate_shots()
        peak = max(s2.zoom(g)[0] for g in range(720))
        self.assertAlmostEqual(peak, 1.15)
        for g in range(720):
            s2.assert_safe(*s2.zoom(g))

    def test_selected_r4_b_span_preserved(self):
        r4 = [(60, 120, 1.00, 0.0), (120, 180, 1.12, 0.0), (180, 240, 1.00, 0.03), (240, 300, 1.10, 0.0), (300, 360, 1.06, 0.0), (360, 420, 1.12, -0.02)]
        self.assertEqual([s for s in s2.SHOTS if 60 <= s[0] < 420], r4)

    def test_invisible_cut_rejected(self):
        saved = s2.SHOTS
        try:
            s2.SHOTS = [(0, 60, 1.00, 0.0), (60, 720, 1.02, 0.0)]
            with self.assertRaises(AssertionError):
                s2.validate_shots()
        finally:
            s2.SHOTS = saved


class FakeItem:
    def __init__(self, name, start, end, props=None):
        self.name, self.start, self.end = name, start, end
        self.props = props or {**s2.NEUTRAL, "Opacity": 100.0, "CompositeMode": 0}
    def GetMediaPoolItem(self): return FakeMPI(self.name)
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def GetSourceStartFrame(self): return 0
    def GetProperty(self, k=None): return self.props[k] if k else self.props


class FakeMPI:
    def __init__(self, name): self.name, self.ics = name, "Rec.709"
    def GetClipProperty(self, k): return {"File Name": self.name, "Input Color Space": self.ics}[k]
    def SetClipProperty(self, k, v): self.ics = v; return True


class FakeTimeline:
    def __init__(self, v2): self.v2, self.deleted = v2, []
    def GetStartFrame(self): return 108000
    def GetItemListInTrack(self, kind, n): return list(self.v2) if (kind, n) == ("video", 2) else []
    def DeleteClips(self, items, ripple): self.deleted += items; self.v2 = [i for i in self.v2 if i not in items]; return True


class FakePool:
    def __init__(self, tl): self.tl = tl
    def ImportMedia(self, paths): return [FakeMPI(Path(paths[0]).name)]
    def AppendToTimeline(self, specs):
        sp = specs[0]; it = FakeItem(sp["mediaPoolItem"].name, sp["recordFrame"], sp["recordFrame"] + sp["endFrame"])
        self.tl.v2.append(it); return [it]


class FakeProject:
    def __init__(self, tl): self.pool = FakePool(tl)
    def GetMediaPool(self): return self.pool


class ReplaceV2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.saved = s2.OUT; s2.OUT = self.tmp
        self.manifest = {"overlays": []}
        for name, a, b in s2.V2_OVERLAYS:
            (self.tmp / name).write_bytes(name.encode())
            self.manifest["overlays"].append({"file": name, "sha256": s2.sha(self.tmp / name), "frames": b - a})

    def tearDown(self): s2.OUT = self.saved

    def v13_tl(self): return FakeTimeline([FakeItem(n, 108000 + a, 108000 + b) for n, a, b in s2.V2_V13])

    def test_replaces_intro_and_outro(self):
        tl = self.v13_tl(); placed = s2.replace_v2(FakeProject(tl), tl, self.manifest)
        self.assertEqual([p["timeline_frames"] for p in placed], [[0, 30], [672, 720]])
        self.assertEqual({p["input_color_space"] for p in placed}, {"Project"})
        self.assertEqual(len(tl.deleted), 2)

    def test_unexpected_v2_refused(self):
        tl = FakeTimeline([FakeItem("something_else.mov", 108000, 108054)])
        with self.assertRaises(AssertionError):
            s2.replace_v2(FakeProject(tl), tl, self.manifest)
        self.assertEqual(tl.deleted, [])

    def test_overlay_hash_drift_refused(self):
        (self.tmp / s2.V2_OVERLAYS[0][0]).write_bytes(b"tampered")
        tl = self.v13_tl()
        with self.assertRaises(AssertionError):
            s2.replace_v2(FakeProject(tl), tl, self.manifest)


class RenderProject:
    def __init__(self, job_status="Complete", never_finishes=False, foreign_job=False):
        self.jobs, self.started, self.stopped, self.deleted, self.settings = [], False, 0, [], {}
        self.job_status, self.never_finishes, self.foreign_job = job_status, never_finishes, foreign_job
    def SetCurrentTimeline(self, tl): return True
    def SetCurrentRenderFormatAndCodec(self, f, c): self.fc = {"format": f, "codec": c}; return True
    def GetCurrentRenderFormatAndCodec(self): return self.fc
    def SetCurrentRenderMode(self, m): return True
    def SetRenderSettings(self, s): self.settings = s; return True
    def AddRenderJob(self):
        self.jobs.append({"JobId": "job-1"})
        if self.foreign_job:
            self.jobs.append({"JobId": "foreign"})
        return "job-1"
    def GetRenderJobList(self): return list(self.jobs)
    def StartRendering(self, jobs, interactive):
        self.started = True
        if not self.never_finishes and self.job_status == "Complete":
            (Path(self.settings["TargetDir"]) / (self.settings["CustomName"] + ".mov")).write_bytes(b"fake")
        return True
    def IsRenderingInProgress(self): return self.never_finishes and not self.stopped
    def StopRendering(self): self.stopped += 1
    def GetRenderJobStatus(self, job): return {"JobStatus": "Rendering" if self.never_finishes else self.job_status}
    def DeleteRenderJob(self, job): self.deleted.append(job); return True


class FakeResolve:
    def OpenPage(self, page): return True


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def sleep(self, dt): self.t += dt


class RenderControl(unittest.TestCase):
    def run_render(self, p):
        tmp = Path(tempfile.mkdtemp()); clock = Clock()
        try:
            return s2.render(FakeResolve(), p, FakeTimeline([]), out=tmp, timeout=5, poll=1, clock=clock, sleep=clock.sleep), None
        except s2.BuildHold:
            return None, json.loads((tmp / "STEP2_RENDER_HOLD.json").read_text())

    def test_full_range_marks(self):
        p = RenderProject(); result, hold = self.run_render(p)
        self.assertIsNone(hold); self.assertEqual((p.settings["MarkIn"], p.settings["MarkOut"]), (108000, 108719))
        self.assertEqual(p.deleted, ["job-1"])

    def test_timeout_hold(self):
        p = RenderProject(never_finishes=True); _, hold = self.run_render(p)
        self.assertEqual(hold["status"], "TIMEOUT_HOLD"); self.assertEqual(p.stopped, 1); self.assertTrue(hold["stopped_verified"])

    def test_foreign_job_refused(self):
        p = RenderProject(foreign_job=True)
        with self.assertRaises(AssertionError):
            self.run_render(p)
        self.assertFalse(p.started)

    def test_failed_render_hold(self):
        p = RenderProject(job_status="Failed"); _, hold = self.run_render(p)
        self.assertEqual(hold["status"], "RENDER_FAILED_HOLD"); self.assertEqual(p.deleted, [])


def good_step1():
    clip = lambda s, e: {"name": "IMG_5739.MOV", "start": 108000 + s, "end": 108000 + e, "source_start": s + 2144,
                         "file": "/x/IMG_5739.MOV", "media": {"FPS": 30.0}, "comp_names": ["Composition 1"], "props": dict(s2.NEUTRAL)}
    return {"project": s2.COPY, "source_drp_sha256": s2.V13_DRP_SHA,
            "settings": {"timelineFrameRate": 30.0, "timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920",
                         "colorSpaceOutput": "Rec.2100 HLG", "colorSpaceOutputGamma": ""},
            "timelines": [{"name": s2.BASE_TIMELINE, "start": 108000, "tracks": {
                "video1": [clip(s, e) for s, e in s2.V1],
                "video2": [{"file": "/x/" + n, "start": 108000 + a, "end": 108000 + b} for n, a, b in s2.V2_V13],
                "audio1": [{"name": s2.AUDIO_FILE, "start": 108000, "end": 108720, "source_start": 2160, "file": "/x/" + s2.AUDIO_FILE}]}}]}


class Step1Validation(unittest.TestCase):
    def test_good(self):
        s2.validate_step1(good_step1())

    def test_mismatches(self):
        def mutate(fn):
            s = good_step1(); fn(s); return s
        cases = {
            "wrong copy": lambda s: s.update(project="UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01"),
            "fps 29.97": lambda s: s["timelines"][0]["tracks"]["video1"][2]["media"].update(FPS="29.97"),
            "source offset": lambda s: s["timelines"][0]["tracks"]["video1"][1].update(source_start=2234),
            "not HLG": lambda s: s["settings"].update(colorSpaceOutput="Rec.709 Gamma 2.4"),
            "audio offset": lambda s: s["timelines"][0]["tracks"]["audio1"][0].update(source_start=2159),
            "unexpected V2": lambda s: s["timelines"][0]["tracks"]["video2"].pop(),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                with self.assertRaises(AssertionError):
                    s2.validate_step1(mutate(fn))


if __name__ == "__main__":
    unittest.main(verbosity=2)
