"""Offline tests for step2_build_render_ab.py (rev 2). Never imports DaVinciResolveScript or touches Resolve."""
import copy, importlib.util, json, re, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("step2", HERE / "step2_build_render_ab.py")
s2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s2)
V13_LOCAL = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair")

FIXTURE = """Composition {
\tCurrentTime = 0,
\tRenderRange = { 0, 114 },
\tTools = {
\t\tMediaOut1 = Saver {
\t\t\tInputs = {
\t\t\t\tIndex = Input { Value = "0", },
\t\t\t\tInput = Input {
\t\t\t\t\tSourceOp = "Merge2",
\t\t\t\t\tSource = "Output",
\t\t\t\t}
\t\t\t},
\t\t},
\t\tMediaIn1 = MediaIn {
\t\t\tInputs = {
\t\t\t\tGlobalIn = Input { Value = -2233, },
\t\t\t},
\t\t},
\t\tUN_CONTINUOUS_RHYTHM_V03Size = BezierSpline {
\t\t\tSplineColor = { Red = 225, Green = 0, Blue = 225 },
\t\t\tCtrlWZoom = false,
\t\t\tKeyFrames = {
\t\t\t\t[0] = { 2.3, RH = { 21.3, 2.3 }, Flags = { Linear = true } },
\t\t\t\t[64] = { 2.3, Flags = { Linear = true } },
\t\t\t\t[66] = { 2.3414, Flags = { Linear = true } },
\t\t\t\t[114] = { 2.3, Flags = { Linear = true } }
\t\t\t}
\t\t},
\t\tUN_CONTINUOUS_RHYTHM_V03 = Transform {
\t\t\tInputs = {
\t\t\t\tCenter = Input { Value = { 0.5, 0.72 }, },
\t\t\t\tSize = Input {
\t\t\t\t\tSourceOp = "UN_CONTINUOUS_RHYTHM_V03Size",
\t\t\t\t\tSource = "Value",
\t\t\t\t},
\t\t\t\tInput = Input {
\t\t\t\t\tSourceOp = "MediaIn1",
\t\t\t\t\tSource = "Output",
\t\t\t\t}
\t\t\t},
\t\t},
\t\tUN_BRAND_HOOK = TextPlus {
\t\t\tInputs = {
\t\t\t\tStyledText = Input { Value = "SOME LOVE STORIES\\nNEVER REALLY END.", },
\t\t\t\tFont = Input { Value = "Montserrat", },
\t\t\t\tSoftness1 = Input { Value = 1, },
\t\t\t},
\t\t},
\t\tMerge1Blend = BezierSpline {
\t\t\tSplineColor = { Red = 205, Green = 205, Blue = 205 },
\t\t\tCtrlWZoom = false,
\t\t\tKeyFrames = {
\t\t\t\t[0] = { 0, Flags = { Linear = true } },
\t\t\t\t[8] = { 1, Flags = { Linear = true } },
\t\t\t\t[114] = { 1, Flags = { Linear = true } },
\t\t\t}
\t\t},
\t\tMerge1 = Merge {
\t\t\tInputs = {
\t\t\t\tBlend = Input {
\t\t\t\t\tSourceOp = "Merge1Blend",
\t\t\t\t\tSource = "Value",
\t\t\t\t},
\t\t\t\tBackground = Input {
\t\t\t\t\tSourceOp = "UN_CONTINUOUS_RHYTHM_V03",
\t\t\t\t\tSource = "Output",
\t\t\t\t},
\t\t\t\tForeground = Input {
\t\t\t\t\tSourceOp = "UN_BRAND_HOOK",
\t\t\t\t\tSource = "Output",
\t\t\t\t},
\t\t\t},
\t\t},
\t\tUN_BRAND_TITLE = TextPlus {
\t\t\tInputs = {
\t\t\t\tStyledText = Input { Value = "AAKHRI ISHQ", },
\t\t\t},
\t\t},
\t\tMerge2 = Merge {
\t\t\tInputs = {
\t\t\t\tBlend = Input { Value = 1, },
\t\t\t\tBackground = Input {
\t\t\t\t\tSourceOp = "Merge1",
\t\t\t\t\tSource = "Output",
\t\t\t\t},
\t\t\t\tForeground = Input {
\t\t\t\t\tSourceOp = "UN_BRAND_TITLE",
\t\t\t\t\tSource = "Output",
\t\t\t\t},
\t\t\t},
\t\t},
\t},
}
"""


def set_spline_value(text, name, frame, value):
    s, e = s2.span(text, name)
    block, n = re.subn(rf"\[{frame}\] = \{{ {s2.NUM}", f"[{frame}] = {{ {value}", text[s:e], count=1)
    assert n == 1
    return text[:s] + block + text[e:]


def replace_in_tool(text, name, old, new):
    s, e = s2.span(text, name)
    assert old in text[s:e], (name, old)
    return text[:s] + text[s:e].replace(old, new, 1) + text[e:]


class PatchAndReadback(unittest.TestCase):
    def setUp(self):
        self.patched = {k: s2.patch_clip(FIXTURE, k, v, s2.TEXT_CLIP) for k, v in s2.VARIANTS.items()}

    def assertRejects(self, body, plan):
        with self.assertRaises(AssertionError):
            s2.verify_readback(body, plan)

    def test_positive_both_variants(self):
        for key, (body, plan) in self.patched.items():
            s2.verify_readback(body, plan)
            self.assertEqual(len(plan["disabled_text_merges"]), 2)
            self.assertEqual(len(re.findall(r"\bBlend = Input", s2.block_of(body, "Merge2"))), 1)

    def test_default_valued_inputs_may_be_omitted_by_fusion(self):
        body, plan = self.patched["A"]
        body = replace_in_tool(body, "UN_AB_HOOK", "\t\t\t\tEnabled2 = Input { Value = 0, },\n", "")
        s2.verify_readback(body, plan)

    def test_negatives(self):
        a, pa = self.patched["A"]; b, pb = self.patched["B"]
        cases = {
            "caption opacity curve emptied": (re.sub(r"(UN_AB_HOOKBlend = BezierSpline \{.*?KeyFrames = \{)(.*?)(\n\t\t\t\})",
                                                     r"\1\3", a, count=1, flags=re.S), pa),
            "caption position key changed": (set_spline_value(b, "UN_AB_HOOK_P2CY", 0, 0.5), pb),
            "caption opacity key changed": (set_spline_value(a, "UN_AB_HOOKBlend", 9, 0.5), pa),
            "caption tool removed": (a[:s2.span(a, "UN_AB_HOOK")[0]] + a[s2.span(a, "UN_AB_HOOK")[1]:], pa),
            "output disconnected": (replace_in_tool(a, "MediaOut1", '"UN_AB_HOOKMerge"', '"Merge2"'), pa),
            "caption merge background rewired": (replace_in_tool(b, "UN_AB_HOOK_P2Merge", '"UN_AB_HOOK_P1Merge"', '"Merge2"'), pb),
            "pre-existing caption re-enabled (spline)": (set_spline_value(a, "Merge1Blend", 114, 1), pa),
            "pre-existing caption re-enabled (static)": (replace_in_tool(a, "Merge2", "Blend = Input { Value = 0, }",
                                                                         "Blend = Input { Value = 1, }"), pa),
            "T1 centre changed": (replace_in_tool(a, "UN_AB_T1", "0.37826087", "0.4"), pa),
            "T2 not fed by T1": (replace_in_tool(a, "UN_AB_T2", '"UN_AB_T1"', '"MediaIn1"'), pa),
            "rhythm bypasses AB layer": (replace_in_tool(a, "UN_CONTINUOUS_RHYTHM_V03", '"UN_AB_T3"', '"MediaIn1"'), pa),
            "inherited rhythm curve changed": (set_spline_value(a, "UN_CONTINUOUS_RHYTHM_V03Size", 66, 2.5), pa),
            "zoom key changed": (set_spline_value(b, "UN_AB_T2Size", 32, 1.2), pb),
            "B style changed": (replace_in_tool(b, "UN_AB_HOOK_P1", '"SemiBold"', '"Medium"'), pb),
            "halo softness enabled": (replace_in_tool(a, "UN_AB_HOOK", "Softness1 = Input { Value = 0, }",
                                                      "Softness1 = Input { Value = 1, }"), pa),
            "text size changed": (replace_in_tool(a, "UN_AB_HOOK", "Size = Input { Value = 0.08, }",
                                                  "Size = Input { Value = 0.1, }"), pa),
        }
        for label, (body, plan) in cases.items():
            with self.subTest(label):
                self.assertRejects(body, plan)

    def test_unknown_extra_text_merge_rejected(self):
        body, plan = self.patched["A"]
        plan = copy.deepcopy(plan); plan["disabled_text_merges"] = plan["disabled_text_merges"][:1]
        self.assertRejects(body, plan)

    def test_geometry_and_punch(self):
        b = s2.VARIANTS["B"]
        self.assertAlmostEqual(s2.zoom(b, 61)[0], 1.15)
        self.assertAlmostEqual(s2.zoom(b, 60)[0], 1.135)
        self.assertAlmostEqual(s2.zoom(b, 69)[0], 1.12)
        self.assertAlmostEqual(max(s2.zoom(b, e)[0] for e in range(360)), 1.15)
        self.assertAlmostEqual(max(s2.zoom(s2.VARIANTS["A"], e)[0] for e in range(360)), 1.13 - 0.03 / 120)
        with self.assertRaises(AssertionError):
            s2.assert_safe(1.21, 0.0)
        with self.assertRaises(AssertionError):
            s2.assert_safe(1.0, 0.7)   # window beyond source edge (0.3 still fits: source is 2.3x frame width)

    def test_composed_peak_includes_rhythm_pulse(self):
        _, plan = self.patched["B"]
        self.assertGreater(plan["composed_peak_total_size_in_excerpt"], 1.12 * 2.3)


@unittest.skipUnless((V13_LOCAL / "clip_01_v13.comp").is_file(), "local V13 comp exports not present")
class RealV13Comps(unittest.TestCase):
    FILES = {0: "clip_00_v13.comp", 1: "clip_01_v13.comp", 2: "clip_02_v13.comp", 3: "clip_03_readback_comp_01.comp"}

    def test_patch_and_verify_real_exports(self):
        for key, v in s2.VARIANTS.items():
            for idx, name in self.FILES.items():
                with self.subTest(key=key, clip=idx):
                    body, plan = s2.patch_clip((V13_LOCAL / name).read_text(encoding="utf-8"), key, v, idx)
                    s2.verify_readback(body, plan)
                    if idx == s2.TEXT_CLIP:
                        self.assertEqual({c["tool"] for c in plan["captions"]},
                                         {c[0] for c in v["captions"]})


class FakeProject:
    def __init__(self, job_status="Complete", never_finishes=False, foreign_job=False, foreign_mid_render=False):
        self.jobs, self.started, self.stopped, self.deleted = [], False, 0, []
        self.job_status, self.never_finishes = job_status, never_finishes
        self.foreign_job, self.foreign_mid_render = foreign_job, foreign_mid_render
        self.settings = {}

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
        if self.foreign_mid_render:
            self.jobs.append({"JobId": "foreign"})
        if not self.never_finishes and self.job_status == "Complete":
            out = Path(self.settings["TargetDir"]) / (self.settings["CustomName"] + ".mov")
            out.write_bytes(b"fake")
        return True

    def IsRenderingInProgress(self): return self.never_finishes and not self.stopped
    def StopRendering(self): self.stopped += 1
    def GetRenderJobStatus(self, job): return {"JobStatus": "Rendering" if self.never_finishes else self.job_status}
    def DeleteRenderJob(self, job): self.deleted.append(job); return True


class FakeResolve:
    def OpenPage(self, page): return True


class FakeTimeline:
    def GetStartFrame(self): return 108000


class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def sleep(self, dt): self.t += dt


class RenderControl(unittest.TestCase):
    def run_render(self, p):
        tmp = Path(tempfile.mkdtemp()); clock = FakeClock()
        try:
            result = s2.render(FakeResolve(), p, FakeTimeline(), "A", out=tmp, timeout=5, poll=1, clock=clock, sleep=clock.sleep)
        except s2.BuildHold:
            return None, json.loads((tmp / "STEP2_RENDER_HOLD_A.json").read_text())
        return result, None

    def test_success_deletes_only_own_job(self):
        p = FakeProject(); result, hold = self.run_render(p)
        self.assertIsNone(hold); self.assertEqual(p.deleted, ["job-1"])
        self.assertEqual((p.settings["MarkIn"], p.settings["MarkOut"]), (108060, 108419))

    def test_timeout_stops_owned_job_and_persists_hold(self):
        p = FakeProject(never_finishes=True); result, hold = self.run_render(p)
        self.assertEqual(hold["status"], "TIMEOUT_HOLD"); self.assertEqual(p.stopped, 1)
        self.assertTrue(hold["stopped_verified"]); self.assertEqual(hold["job_id"], "job-1"); self.assertEqual(p.deleted, [])

    def test_timeout_does_not_stop_when_queue_not_owned(self):
        p = FakeProject(never_finishes=True, foreign_mid_render=True); result, hold = self.run_render(p)
        self.assertEqual(p.stopped, 0); self.assertFalse(hold["sole_job_owned"]); self.assertFalse(hold["stopped_verified"])

    def test_refuses_to_start_with_foreign_job(self):
        p = FakeProject(foreign_job=True)
        with self.assertRaises(AssertionError):
            self.run_render(p)
        self.assertFalse(p.started)

    def test_failed_render_persists_hold_without_cleanup(self):
        p = FakeProject(job_status="Failed"); result, hold = self.run_render(p)
        self.assertEqual(hold["status"], "RENDER_FAILED_HOLD"); self.assertEqual(p.deleted, [])


def good_step1():
    clip = lambda s, e: {"name": "IMG_5739.MOV", "start": 108000 + s, "end": 108000 + e, "source_start": s + 2144,
                         "file": "/x/IMG_5739.MOV", "media": {"FPS": "30.000"}, "comp_names": ["Composition 1"],
                         "props": {k: v for k, v in s2.NEUTRAL.items()}}
    return {"project": s2.COPY, "source_drp_sha256": s2.V13_DRP_SHA,
            "settings": {"timelineFrameRate": "30", "timelineResolutionWidth": "1080", "timelineResolutionHeight": "1920",
                         "colorSpaceOutput": "Rec.2100 HLG", "colorSpaceOutputGamma": ""},
            "timelines": [{"name": s2.BASE_TIMELINE, "start": 108000, "tracks": {
                "video1": [clip(s, e) for s, e in s2.V1],
                "audio1": [{"name": s2.AUDIO_FILE, "start": 108000, "end": 108720, "source_start": 2160, "file": "/x/" + s2.AUDIO_FILE}]}}]}


class Step1Validation(unittest.TestCase):
    def test_good(self):
        s2.validate_step1(good_step1())

    def test_mismatches(self):
        def mutate(fn):
            s = good_step1(); fn(s); return s
        cases = {
            "fps 29.97": lambda s: s["timelines"][0]["tracks"]["video1"][2]["media"].update(FPS="29.97"),
            "source offset": lambda s: s["timelines"][0]["tracks"]["video1"][1].update(source_start=2234),
            "not HLG": lambda s: s["settings"].update(colorSpaceOutput="Rec.709 Gamma 2.4"),
            "audio offset": lambda s: s["timelines"][0]["tracks"]["audio1"][0].update(source_start=2159),
            "extra comp": lambda s: s["timelines"][0]["tracks"]["video1"][0].update(comp_names=["Composition 1", "X"]),
            "non-neutral clip transform": lambda s: s["timelines"][0]["tracks"]["video1"][3]["props"].update(ZoomX=1.1),
            "timeline fps": lambda s: s["settings"].update(timelineFrameRate="29.97"),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                with self.assertRaises(AssertionError):
                    s2.validate_step1(mutate(fn))


if __name__ == "__main__":
    unittest.main(verbosity=2)
