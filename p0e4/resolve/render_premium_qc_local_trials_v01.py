"""Render bounded premium colour and caption trials from immutable V13.

Creates isolated Resolve project clones only. It never changes or renders over
the V13 project/master and never performs deployment or publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import DaVinciResolveScript as d

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/premium-qc-research-v01"
OUT.mkdir(parents=True, exist_ok=True)
BASE_DRP = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair/UNCHAINED_AAKHRI_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR.drp"
BASE_MASTER = ROOT / ".local/aakhri-integrated-preview-v13-chain-caption-repair/AAKHRI_ISHQ_FIRST_PUBLISH_PREVIEW_V13_CHAIN_CAPTION_REPAIR_HLG_PRORES.mov"
REQUEST_ID = "UNCHAINED_PREMIUM_EXECUTION_20260929"
EXPECTED_BASE_DRP = "f1e720b658315418279dc27e913e695308d00bdd5b572dca05e1395170870bec"
EXPECTED_BASE_MASTER = "7266506b3d9e5262ded0c579d664c2d6444e6c35c173cf00c062290810ffe088"
EXPECTED_TIMELINE = [(0, 89), (89, 204), (204, 335), (335, 491), (491, 623), (623, 720)]
SAMPLE = (335, 694)  # initial identical 12 s trial; superseded by performance-only R2


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def tool(text: str, name: str, transform) -> str:
    marker = f"\n\t\t{name} = "
    start = text.index(marker) + 1
    match = re.search(r"\n\t\t[^\t]", text[start + len(marker):])
    if not match:
        raise RuntimeError("tool end: " + name)
    end = start + len(marker) + match.start()
    return text[:start] + transform(text[start:end]) + text[end:]


def set_value(block: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+|\{{[^}}]+\}})(, \}},)"
    out, n = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if n != 1:
        raise RuntimeError(f"input {key}")
    return out


def set_or_insert(block: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)} = Input \{{ Value = )([^,]+)(, \}},)"
    out, n = re.subn(pattern, rf"\g<1>{value}\g<3>", block, count=1)
    if n:
        return out
    needle = "\n\t\t\t\tStyledText = Input"
    if needle not in block:
        raise RuntimeError("insert " + key)
    return block.replace(needle, f"\n\t\t\t\t{key} = Input {{ Value = {value}, }}," + needle, 1)


def style(block: str, *, center, size, rgb, font, weight) -> str:
    for key, value in (("Center", f"{{ {center[0]}, {center[1]} }}"), ("Size", str(size)),
                       ("Font", f'"{font}"'), ("Style", f'"{weight}"')):
        block = set_value(block, key, value)
    for key, value in zip(("Red1", "Green1", "Blue1"), rgb):
        block = set_or_insert(block, key, str(value))
    for key, value in (("Enabled2", "0"), ("Enabled3", "0"), ("Softness1", "0"), ("Opacity1", "1")):
        block = set_or_insert(block, key, value)
    return block


def curve(block: str, points) -> str:
    begin = block.index("\n\t\t\tKeyFrames = {")
    end = block.index("\n\t\t\t}", begin) + len("\n\t\t\t}")
    lines = ["\n\t\t\tKeyFrames = {"]
    lines += [f"\t\t\t\t[{frame}] = {{ {value}, Flags = {{ Linear = true }} }}," for frame, value in points]
    lines.append("\t\t\t}")
    return block[:begin] + "\n".join(lines) + block[end:]


CAPTIONS = {
    "T1_LYRICAL_ELEGANCE": {"hook": (0.5, 0.20, 0.088), "title": (0.5, 0.135, 0.112), "artist": (0.5, 0.25, 0.060), "fade": 8},
    "T2_KINETIC_IMPACT": {"hook": (0.5, 0.20, 0.106), "title": (0.5, 0.13, 0.128), "artist": (0.5, 0.255, 0.072), "fade": 4},
    "T3_CINEMATIC_TITLE": {"hook": (0.5, 0.18, 0.078), "title": (0.5, 0.145, 0.118), "artist": (0.5, 0.265, 0.058), "fade": 12},
}

COLOURS = {
    "C0_CURRENT_REFERENCE": None,
    "C1_WARM_CINEMATIC": {"NodeIndex": 1, "Slope": "1.035 1.015 0.985", "Offset": "0.003 0.001 -0.002", "Power": "0.985 0.995 1.010", "Saturation": 1.055},
    "C2_DRAMATIC_STAGE": {"NodeIndex": 1, "Slope": "1.045 1.018 0.990", "Offset": "-0.006 -0.006 -0.004", "Power": "0.975 0.990 1.012", "Saturation": 1.070},
}


def clone(pm, name):
    if name in pm.GetProjectListInCurrentFolder():
        raise RuntimeError("NO_DUPLICATE_PROJECT:" + name)
    if not pm.ImportProject(str(BASE_DRP), name):
        raise RuntimeError("IMPORT:" + name)
    project = pm.LoadProject(name)
    if not project or project.IsRenderingInProgress():
        raise RuntimeError("PROJECT:" + name)
    tl = project.GetCurrentTimeline(); origin = tl.GetStartFrame(); clips = tl.GetItemListInTrack("video", 1)
    if [(c.GetStart() - origin, c.GetEnd() - origin) for c in clips] != EXPECTED_TIMELINE:
        raise RuntimeError("TIMELINE_DRIFT:" + name)
    return project, tl, origin, clips


def render(project, origin, mark_in, mark_out, stem):
    target = OUT / f"{stem}.mov"
    if target.exists():
        raise RuntimeError("NO_OVERWRITE:" + str(target))
    if not project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ"):
        raise RuntimeError("PRORES")
    project.SetCurrentRenderMode(1)
    if not project.SetRenderSettings({"SelectAllFrames": False, "MarkIn": origin + mark_in, "MarkOut": origin + mark_out,
        "TargetDir": str(OUT), "CustomName": stem, "ExportVideo": True, "ExportAudio": True,
        "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 30, "AudioCodec": "lpcm", "AudioSampleRate": 48000}):
        raise RuntimeError("SETTINGS")
    job = project.AddRenderJob()
    if not job or not project.StartRendering([job], False):
        raise RuntimeError("START")
    deadline = time.monotonic() + 1200
    while project.IsRenderingInProgress() and time.monotonic() < deadline:
        time.sleep(.5)
    status = project.GetRenderJobStatus(job); project.DeleteRenderJob(job)
    if status.get("JobStatus") != "Complete" or not target.exists():
        raise RuntimeError("RENDER:" + repr(status))
    return {"path": str(target), "sha256": sha(target), "bytes": target.stat().st_size,
            "frames": mark_out - mark_in + 1, "status": status}


def main():
    if sha(BASE_DRP) != EXPECTED_BASE_DRP or sha(BASE_MASTER) != EXPECTED_BASE_MASTER:
        raise RuntimeError("BASE_DRIFT")
    resolve = d.scriptapp("Resolve")
    if not resolve or resolve.GetProductName() != "DaVinci Resolve Studio":
        raise RuntimeError("RESOLVE_UNAVAILABLE")
    pm = resolve.GetProjectManager(); initial = pm.GetCurrentProject(); initial_name = initial.GetName() if initial else None
    receipt = {"schema": "PREMIUM_QC_LOCAL_TRIALS_V01", "request_id": REQUEST_ID,
      "resolve": {"product": resolve.GetProductName(), "version": resolve.GetVersionString()},
      "base": {"drp_sha256": sha(BASE_DRP), "master_sha256_before": sha(BASE_MASTER)},
      "colour_trials": [], "caption_trials": [], "full_master_rendered": False,
      "publication_authorized": False, "production_deployment_authorized": False}
    try:
        for key, cdl in COLOURS.items():
            name = "UNCHAINED_PREMIUM_QC_" + key + "_V01"
            existing = OUT / ("AAKHRI_PREMIUM_" + key + "_HLG.mov")
            existing_drp = OUT / f"{name}.drp"
            if existing.exists() and existing_drp.exists():
                receipt["colour_trials"].append({"variant": key, "cdl": cdl,
                  "affected_clips": 0 if cdl is None else "RECORDED_IN_EXISTING_PROJECT",
                  "sample_frames": list(SAMPLE), "render": {"path": str(existing), "sha256": sha(existing),
                  "bytes": existing.stat().st_size, "frames": SAMPLE[1] - SAMPLE[0] + 1,
                  "status": "COMPLETE_REUSED_AFTER_CAPTION_PARSER_FAILURE"}, "drp_sha256": sha(existing_drp)})
                continue
            project, tl, origin, clips = clone(pm, name)
            if cdl:
                affected = 0
                for clip in clips:
                    if clip.GetEnd() - origin > SAMPLE[0] and clip.GetStart() - origin <= SAMPLE[1]:
                        if not clip.SetCDL(cdl): raise RuntimeError("CDL:" + key)
                        affected += 1
            else: affected = 0
            pm.SaveProject(); drp = OUT / f"{name}.drp"; pm.ExportProject(name, str(drp), False)
            out = render(project, origin, SAMPLE[0], SAMPLE[1], "AAKHRI_PREMIUM_" + key + "_HLG")
            receipt["colour_trials"].append({"variant": key, "cdl": cdl, "affected_clips": affected,
              "sample_frames": list(SAMPLE), "render": out, "drp_sha256": sha(drp)})
            pm.CloseProject(project)
        for key, cfg in CAPTIONS.items():
            name = "UNCHAINED_PREMIUM_QC_" + key + "_V01"
            if name in pm.GetProjectListInCurrentFolder():
                # Only an interrupted disposable caption clone can reach here:
                # successful renders are protected by render() NO_OVERWRITE.
                if (OUT / ("AAKHRI_PREMIUM_" + key + "_HLG.mov")).exists():
                    raise RuntimeError("EXISTING_RENDER_REQUIRES_RECEIPT:" + key)
                if not pm.DeleteProject(name): raise RuntimeError("DELETE_INTERRUPTED:" + name)
            project, tl, origin, clips = clone(pm, name)
            readbacks = []
            for idx in (0, 1):
                src = OUT / f"{key}_clip_{idx:02d}_source.comp"; patched = OUT / f"{key}_clip_{idx:02d}_patched.comp"
                clips[idx].ExportFusionComp(str(src), 1); text = src.read_text(encoding="utf-8")
                if idx == 0:
                    x,y,s=cfg["hook"]; text=tool(text,"UN_BRAND_HOOK",lambda b:style(b,center=(x,y),size=s,rgb=(.96,.94,.88),font="Montserrat",weight="Medium"))
                    text=tool(text,"Merge1Blend",lambda b:curve(b,[(0,0),(cfg["fade"],1),(78,1),(88,0)])); text=tool(text,"Merge2Blend",lambda b:curve(b,[(0,0),(88,0)]))
                else:
                    x,y,s=cfg["title"]; text=tool(text,"UN_BRAND_TITLE",lambda b:style(b,center=(x,y),size=s,rgb=(.847,.722,.314),font="Cinzel",weight="SemiBold"))
                    x,y,s=cfg["artist"]; text=tool(text,"UN_BRAND_ARTIST",lambda b:style(b,center=(x,y),size=s,rgb=(.96,.94,.88),font="Montserrat",weight="Medium"))
                    text=tool(text,"Merge3Blend",lambda b:curve(b,[(0,0),(cfg["fade"],1),(90,1)])); text=tool(text,"Merge4Blend",lambda b:curve(b,[(0,0),(cfg["fade"],1),(90,1)]))
                    text=tool(text,"Merge1Blend",lambda b:curve(b,[(0,0),(114,0)])); text=tool(text,"Merge2Blend",lambda b:curve(b,[(0,0),(114,0)]))
                patched.write_text(text, encoding="utf-8"); clips[idx].ImportFusionComp(str(patched)); rb=OUT/f"{key}_clip_{idx:02d}_readback.comp"; clips[idx].ExportFusionComp(str(rb),1)
                body=rb.read_text(encoding="utf-8"); assert 'Font = Input { Value = "Montserrat", },' in body
                if idx==1: assert 'Font = Input { Value = "Cinzel", },' in body and 'Style = Input { Value = "SemiBold", },' in body
                readbacks.append({"clip":idx,"source_sha256":sha(src),"patched_sha256":sha(patched),"readback_sha256":sha(rb)})
            pm.SaveProject(); drp=OUT/f"{name}.drp"; pm.ExportProject(name,str(drp),False)
            out=render(project,origin,0,179,"AAKHRI_PREMIUM_"+key+"_HLG")
            receipt["caption_trials"].append({"variant":key,"configuration":cfg,"readbacks":readbacks,"render":out,"drp_sha256":sha(drp)})
            pm.CloseProject(project)
    finally:
        if initial_name: pm.LoadProject(initial_name)
    receipt["base"]["master_sha256_after"] = sha(BASE_MASTER)
    if receipt["base"]["master_sha256_after"] != EXPECTED_BASE_MASTER: raise RuntimeError("MASTER_CHANGED")
    receipt["status"] = "LOCAL_TRIALS_RENDERED_PRIVATE_ONLY"
    (OUT / "PREMIUM_QC_LOCAL_TRIALS_V01.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print(json.dumps(receipt,indent=2))


if __name__ == "__main__": main()
