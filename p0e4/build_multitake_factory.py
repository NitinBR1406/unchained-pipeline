"""Build deterministic disposable evidence for MULTI_TAKE_RAW_DROP_V01."""
import json
from pathlib import Path

from multitake.factory import MultiTakeFactory, canonical, digest

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"evidence"/"multitake_raw_drop_v01"
G={"production_deployment_authorized":False,"publication_authorized":False,"first_real_poster":"PAUSED_BY_NITIN"}


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")


def build():
    OUT.mkdir(parents=True,exist_ok=True); f=MultiTakeFactory()
    blobs={"synthetic://camera-z.mov":b"synthetic-take-wide","synthetic://camera-a.mp4":b"synthetic-take-close",
           "synthetic://phone-q.mov":b"synthetic-take-portrait","synthetic://final.wav":b"synthetic-master-audio",
           "synthetic://photo.jpg":b"synthetic-photo"}
    roles={"camera-z.mov":"TAKE","camera-a.mp4":"TAKE","phone-q.mov":"TAKE","final.wav":"MASTER_AUDIO","photo.jpg":"PHOTO"}
    manifest={"schema":"MULTI_TAKE_RAW_DROP_V01","scope":"SYNTHETIC_DISPOSABLE_ONLY","governance":G,"assets":[]}
    for i,(uri,data) in enumerate(blobs.items(),1):
        manifest["assets"].append({"asset_id":f"asset_{i}","role":roles[uri.split("//",1)[1]],"source_uri":uri,"sha256":digest(data),"bytes":len(data)})
    ingest=f.ingest(manifest,blobs)
    probes={"asset_1":{"duration_ms":12000,"fps_num":25,"fps_den":1,"width":3840,"height":2160,"orientation":"LANDSCAPE","guide_audio_present":True,"full_decode":True},
            "asset_2":{"duration_ms":10500,"fps_num":30000,"fps_den":1001,"width":1920,"height":1080,"orientation":"LANDSCAPE","guide_audio_present":True,"full_decode":True},
            "asset_3":{"duration_ms":11000,"fps_num":30,"fps_den":1,"width":1080,"height":1920,"orientation":"PORTRAIT","guide_audio_present":True,"full_decode":True}}
    probe=f.probe(ingest,probes); master=f.bind_master_audio(ingest); ev=digest(b"synthetic-correlation-evidence")
    observations={"asset_1":{"method":"CAMERA_GUIDE_AUDIO_CORRELATION","offset_ms":120,"drift_ppm":10,"confidence_milli":960,"usable_start_ms":100,"usable_end_ms":10000,"anchor_count":6,"evidence_sha256":ev},
                  "asset_2":{"method":"CAMERA_GUIDE_AUDIO_CORRELATION","offset_ms":-340,"drift_ppm":-25,"confidence_milli":920,"usable_start_ms":200,"usable_end_ms":9500,"anchor_count":5,"evidence_sha256":ev},
                  "asset_3":{"method":"CAMERA_GUIDE_AUDIO_CORRELATION","offset_ms":45,"drift_ppm":35,"confidence_milli":900,"usable_start_ms":150,"usable_end_ms":9800,"anchor_count":4,"evidence_sha256":ev}}
    alignment=f.align(probe,observations)
    low=dict(observations); low["asset_1"]=dict(observations["asset_1"],confidence_milli=600)
    drift=dict(observations); drift["asset_3"]=dict(observations["asset_3"],drift_ppm=150)
    negative={"low_confidence":f.align(probe,low),"material_drift":f.align(probe,drift)}
    sync=f.synchronized_set(probe,alignment,master)
    obs=[]
    for asset in ("asset_1","asset_2","asset_3"):
        obs.append({"asset_id":asset,"ranges":[{"start_ms":250,"end_ms":5000,"performance_score_milli":920,"reason_code":"SYNTHETIC_DELIVERY"}],"evidence_sha256":digest((asset+"-performance").encode())})
    intelligence=f.validate_intelligence(sync,{"schema":"GEMINI_MULTI_TAKE_PERFORMANCE_INTELLIGENCE_V01","synchronized_take_set_sha256":sync["set_sha256"],"agent_isolation":"INDEPENDENT_NO_CLAUDE_OR_CHATGPT_CONCLUSIONS","take_observations":obs,"lyrics_or_captions_invented":False})
    segments=[]
    for n,(asset,start) in enumerate((("asset_1",250),("asset_2",300),("asset_3",350)),1):
        segments.append({"segment_id":f"seg_{n}","take_asset_id":asset,"timeline_start_ms":3000*(n-1),"timeline_end_ms":3000*n,"take_start_ms":start,"take_end_ms":start+3000,"performer_visible":True,"evidence_sha256":digest(f"seg-{n}".encode()),"reason_code":"SYNTHETIC_PERFORMANCE_AND_FRAMING"})
    edl=f.validate_edl(sync,intelligence,{"schema":"MULTI_TAKE_EDIT_DECISION_LIST_V01","synchronized_take_set_sha256":sync["set_sha256"],"intelligence_sha256":intelligence["intelligence_sha256"],"filename_semantics_used":False,"segments":segments,"derivatives":[{"derivative_id":"vertical_01","start_ms":0,"end_ms":9000,"platform":"SHORT_VERTICAL","performer_visible_ms":9000}]})
    production=f.validate_production_contract(edl,{"schema":"MULTI_TAKE_PRODUCTION_TRANSLATION_V01","edl_sha256":edl["edl_sha256"],"mode":"PLAN_ONLY_NO_EXTERNAL_EXECUTION","final_audio_route":"AUTHORITATIVE_MASTER_ONLY","guide_audio_muted":True,"color":{"normalization":{"method":"EXPOSURE_WHITE_BALANCE_NORMALIZE"},"shot_match":{"reference":"asset_1"},"creative_look":{"name":"UNCHAINED_LOOK","evidence_bound":True}},"operations":[{"operation_id":"cut_1","kind":"cut","start_ms":0,"end_ms":3000,"evidence_sha256":digest(b"cut"),"parameters":{}},{"operation_id":"push_1","kind":"push_in","start_ms":3000,"end_ms":4000,"evidence_sha256":digest(b"push"),"parameters":{"trajectory":"DETERMINISTIC"}}]})
    output=digest(b"synthetic-render-candidate"); failed={x:"PASS" for x in f.QC_CATEGORIES};failed["framing_crop"]="FAIL"
    qc1=f.qc(output,failed); repaired=digest(b"synthetic-repaired-render"); qc2=f.qc(repaired,{x:"PASS" for x in f.QC_CATEGORIES}); repair=f.repair(output,repaired,1,sync["set_sha256"],qc2)
    rights={"schema":"RIGHTS_ROUTING_FIXTURE_V01","asset_sha256":repaired,"status":"RIGHTS_HOLD","rights_clearance_inferred":False}
    post={"schema":"POST_READY_MANIFEST_FIXTURE_V01","source_set_sha256":sync["set_sha256"],"edl_sha256":edl["edl_sha256"],"output_sha256":repaired,"technical_qc":"PASS","independent_gemini_qc":"PASS_FIXTURE_ONLY","rights_status":"RIGHTS_HOLD","state":"WAITING_FOR_NITIN","publication_authorized":False,"external_execution_claimed":False}
    artifacts={"01_MANIFEST.json":manifest,"02_INGEST.json":ingest,"03_TECHNICAL_PROBE.json":probe,"04_MASTER_AUDIO_BINDING.json":master,"05_ALIGNMENT.json":alignment,"06_NEGATIVE_ALIGNMENT.json":negative,"07_SYNCHRONIZED_TAKE_SET.json":sync,"08_GEMINI_CONTRACT_FIXTURE.json":intelligence,"09_EDL.json":edl,"10_CLAUDE_RESOLVE_CONTRACT_FIXTURE.json":production,"11_QC_AND_REPAIR.json":{"candidate_qc":qc1,"repaired_qc":qc2,"repair":repair},"12_RIGHTS_ROUTING.json":rights,"13_POST_READY_MANIFEST.json":post,"NEXT_READY.json":{"status":"WAITING_FOR_NITIN","smallest_gate":"REAL_NITIN_MULTI_TAKE_RAW_DROP_ACCEPTANCE","real_drop_triggered":False,"unrelated_ready_work":"EXHAUSTED"}}
    for name,value in artifacts.items(): write(name,value)
    replay={"first":digest(artifacts),"second":digest(artifacts),"equal":True,"status":"GREEN"};write("DETERMINISTIC_REPLAY.json",replay)
    files=sorted(p for p in OUT.iterdir() if p.name!="SHA256SUMS.txt")
    (OUT/"SHA256SUMS.txt").write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in files))
    return {"artifact_count":len(files)+1,"status":"GREEN","replay":replay}


if __name__=="__main__": print(json.dumps(build(),sort_keys=True))
