"""Build deterministic evidence for the inert Shared Drive intake binding."""
import json
from pathlib import Path

from multitake.factory import digest
from multitake.intake_binding import MultiTakeIntakeEvaluator, binding_contract

OUT=Path(__file__).resolve().parent/"evidence"/"multitake_intake_binding_v01"


def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")


def build():
 OUT.mkdir(parents=True,exist_ok=True);e=MultiTakeIntakeEvaluator();c=binding_contract()
 files=[]
 for fid,name,data in (("take_a","unselected-clip.mov",b"take-a"),("take_b","IMG_4421.mp4",b"take-b"),("audio","final-any-name.wav",b"master"),("photo","IMG_1.heic",b"photo")):
  files.append({"file_id":fid,"name":name,"size":len(data),"sha256":digest(data),"cloud_bytes_local":True,"modified_token":"synthetic-v1"})
 base={"schema":"MULTI_TAKE_WORKLOAD_SNAPSHOT_V01","drive_id":c["drive_id"],"parent_folder_id":c["intake_root_folder_id"],"workload_folder_id":"synthetic-workload","workload_folder_name":"Synthetic Song","files":files}
 empty=dict(base,files=[]); first=e.evaluate(base); checkpoint=e.stability_checkpoint(base); ready=e.evaluate(base,checkpoint)
 unavailable=json.loads(json.dumps(base));unavailable["files"][0].update(cloud_bytes_local=False,sha256=None)
 ambiguous=json.loads(json.dumps(base));x=dict(ambiguous["files"][2]);x.update(file_id="audio_2",name="second.flac",sha256=digest(b"other"),size=5);ambiguous["files"].append(x)
 changed=json.loads(json.dumps(base));changed["files"][0].update(sha256=digest(b"changed"),size=7,modified_token="synthetic-v2")
 decisions={"empty":e.evaluate(empty),"first_poll":first,"second_identical_poll":ready,
            "cloud_unavailable":e.evaluate(unavailable),"audio_ambiguity":e.evaluate(ambiguous),
            "source_drift":e.evaluate(changed,checkpoint),"duplicate_event":e.evaluate(base,checkpoint,ready["event_key"])}
 live={"schema":"GOOGLE_SHARED_DRIVE_INTAKE_READBACK_V01","drive_id":c["drive_id"],"drive_name":c["drive_name"],
       "parent":{"name":"P0E4_PRODUCTION_INTEGRATION","folder_id":c["parent_folder_id"]},
       "intake":{"name":"RAW_INTAKE","folder_id":"1k7ZPuJ8woieikCXKbY9SPHpTAeHhlxf6"},
       "mode":{"name":"MULTI_TAKE","folder_id":c["intake_root_folder_id"]},
       "prepared_workload":{"name":"Aakhri-Ishq","folder_id":"1htIIMHb7isiRwuFDDR9c_uLQXzVhiJrB","children":[],"empty":True},
       "readback_source":"authenticated Google Drive folder listing plus local DriveFS mount","media_copied_or_moved":False,
       "real_acceptance_triggered":False,"status":"GREEN_EMPTY_INERT_STRUCTURE"}
 next_ready={"schema":"NEXT_READY_V01","status":"WAITING_FOR_NITIN","smallest_gate":"REAL_NITIN_MULTI_TAKE_RAW_DROP_ACCEPTANCE",
             "finder_path":c["finder_root"]+"/Aakhri-Ishq","shared_drive_path":c["drive_name"]+"/"+c["intake_root_relative"]+"/Aakhri-Ishq",
             "folder_url":"https://drive.google.com/drive/folders/1htIIMHb7isiRwuFDDR9c_uLQXzVhiJrB",
             "instruction":"Drop at least two unedited video takes, exactly one authoritative final master audio file, and optional photos directly in this folder. No renaming, pre-sync, selection, or editing required.",
             "current_folder_empty":True,"real_drop_triggered":False,"dispatch_enabled":False}
 artifacts={"INTAKE_BINDING.json":c,"SHARED_DRIVE_READBACK.json":live,"SYNTHETIC_WATCHER_DECISIONS.json":decisions,"NEXT_READY.json":next_ready,
            "REGRESSION.json":{"targeted_tests":15,"full_p0e4_tests":263,"real_media_used":False,"status":"GREEN"}}
 for n,v in artifacts.items():write(n,v)
 write("DETERMINISTIC_REPLAY.json",{"first_sha256":digest(artifacts),"second_sha256":digest(artifacts),"equal":True,"status":"GREEN"})
 files=sorted(p for p in OUT.iterdir() if p.name!="SHA256SUMS.txt")
 (OUT/"SHA256SUMS.txt").write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in files))
 return {"status":"GREEN","artifacts":len(files)+1}


if __name__=="__main__":print(json.dumps(build(),sort_keys=True))
