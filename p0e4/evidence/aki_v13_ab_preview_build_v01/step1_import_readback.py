"""AKI V13 A/B preview build V01 - step 1: import V13 DRP as isolated copy + full readback.
Never loads/edits the original V13 project. Refuses if the copy or readback dir already exists."""
import hashlib, json, sys
from pathlib import Path
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
import DaVinciResolveScript as d

BASE = Path("/Users/nitinramdaras/Downloads/unchained-pipeline-p0e4/.local/aakhri-integrated-preview-v13-chain-caption-repair")
DRP = BASE / "UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp"
OUT = Path(__file__).resolve().parent
COPY = "UNCHAINED_AKI_V13_AB_PREVIEW_BUILD_V01"
FONTS = [Path.home() / "Library/Fonts" / n for n in ("UNCHAINED-Montserrat-Medium.ttf", "UNCHAINED-Montserrat-VF.ttf",
                                                     "UNCHAINED-Cinzel-SemiBold.ttf")]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

assert sha(DRP) == "f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec", "V13 DRP drift"
(OUT / "readback").mkdir(exist_ok=False)
r = d.scriptapp("Resolve"); assert r, "Resolve scripting unavailable"
pm = r.GetProjectManager()
assert COPY not in pm.GetProjectListInCurrentFolder(), "copy already exists - refusing"
cur = pm.GetCurrentProject()
assert not (cur and cur.IsRenderingInProgress()), "render in progress"
assert pm.ImportProject(str(DRP), COPY)
p = pm.LoadProject(COPY); assert p and p.GetName() == COPY
res = {"project": COPY, "source_drp_sha256": sha(DRP), "fonts": {f.name: sha(f) for f in FONTS},
       "settings": {}, "timelines": []}
for k in ["colorScienceMode", "colorSpaceTimeline", "colorSpaceOutput", "colorSpaceInput", "colorSpaceInputGamma",
          "colorSpaceTimelineGamma", "colorSpaceOutputGamma", "separateColorSpaceAndGamma", "timelineWorkingLuminance",
          "timelineWorkingLuminanceMode", "inputDRT", "outputDRT", "hdrMasteringOn", "hdrMasteringLuminanceMax",
          "useCATransform", "timelineFrameRate", "timelinePlaybackFrameRate", "timelineResolutionWidth",
          "timelineResolutionHeight", "superScale", "imageResizeMode", "timelineOutputResizingMode", "videoDataLevels"]:
    res["settings"][k] = p.GetSetting(k)
for ti in range(1, p.GetTimelineCount() + 1):
    tl = p.GetTimelineByIndex(ti)
    t = {"name": tl.GetName(), "start": tl.GetStartFrame(), "end": tl.GetEndFrame(), "tracks": {}}
    for kind in ("video", "audio"):
        for n in range(1, tl.GetTrackCount(kind) + 1):
            items = []
            for it in tl.GetItemListInTrack(kind, n) or []:
                mpi = it.GetMediaPoolItem()
                e = {"name": it.GetName(), "start": it.GetStart(), "end": it.GetEnd(), "duration": it.GetDuration(),
                     "left_offset": it.GetLeftOffset(), "right_offset": it.GetRightOffset(),
                     "source_start": it.GetSourceStartFrame(), "source_end": it.GetSourceEndFrame(),
                     "file": mpi.GetClipProperty("File Path") if mpi else None,
                     "media": {k: mpi.GetClipProperty(k) for k in ("FPS", "Resolution", "Start TC", "Frames",
                               "Input Color Space", "Data Level", "Video Codec", "Bit Depth")} if mpi else None}
                if kind == "video":
                    e["props"] = it.GetProperty()
                    e["comp_names"] = it.GetFusionCompNameList()
                    e["comps"] = {}
                    for ci in range(1, it.GetFusionCompCount() + 1):
                        fp = OUT / "readback" / f"tl{ti}_V{n}_{len(items):02d}_comp{ci}.comp"
                        assert it.ExportFusionComp(str(fp), ci)
                        e["comps"][fp.name] = sha(fp)
                items.append(e)
            t["tracks"][f"{kind}{n}"] = items
    res["timelines"].append(t)
assert pm.SaveProject()
(OUT / "readback" / "STEP1_IMPORT_READBACK.json").write_text(json.dumps(res, indent=1, default=str))
print("STEP1_OK", COPY)
