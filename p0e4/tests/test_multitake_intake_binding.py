import copy
import unittest

from multitake.intake_binding import MultiTakeIntakeEvaluator, binding_contract
from multitake.factory import digest


class IntakeBindingTests(unittest.TestCase):
 def setUp(self):
  self.e=MultiTakeIntakeEvaluator(); self.c=binding_contract()
  self.s={"schema":"MULTI_TAKE_WORKLOAD_SNAPSHOT_V01","drive_id":self.c["drive_id"],"parent_folder_id":self.c["intake_root_folder_id"],"workload_folder_id":"wf","workload_folder_name":"Song One","files":[]}
  for fid,name,data in (("v1","random-z.mov",b"v1"),("v2","random-a.mp4",b"v2"),("a1","anything.wav",b"a"),("p1","photo.heic",b"p")):
   self.s["files"].append({"file_id":fid,"name":name,"size":len(data),"sha256":digest(data),"cloud_bytes_local":True,"modified_token":"1"})
 def run2(self,s=None,emitted=None):
  s=s or self.s; return self.e.evaluate(s,self.e.stability_checkpoint(s),emitted)
 def test_binding_is_exact_and_inert(self): self.assertFalse(self.c["production_dispatch_enabled"]);self.assertIn("RAW_INTAKE/MULTI_TAKE",self.c["finder_root"])
 def test_empty_no_trigger(self):
  s=copy.deepcopy(self.s);s["files"]=[];self.assertEqual(self.e.evaluate(s)["status"],"EMPTY_NO_TRIGGER")
 def test_first_poll_pending(self): self.assertEqual(self.e.evaluate(self.s)["status"],"PENDING_STABILITY")
 def test_second_poll_ready_but_no_dispatch(self):
  r=self.run2();self.assertTrue(r["trigger_eligible"]);self.assertFalse(r["dispatch_enabled"]);self.assertEqual(r["manifest"]["master_audio_file_id"],"a1")
 def test_missing_master_waits(self):
  s=copy.deepcopy(self.s);s["files"]=[x for x in s["files"] if x["file_id"]!="a1"];self.assertEqual(self.e.evaluate(s)["status"],"WAITING_INCOMPLETE_FILE_SET")
 def test_one_take_waits(self):
  s=copy.deepcopy(self.s);s["files"]=[x for x in s["files"] if x["file_id"]!="v2"];self.assertEqual(self.e.evaluate(s)["status"],"WAITING_INCOMPLETE_FILE_SET")
 def test_audio_ambiguity_holds(self):
  s=copy.deepcopy(self.s);x=copy.deepcopy(s["files"][2]);x.update(file_id="a2",name="other.flac",sha256=digest(b"b"));s["files"].append(x);self.assertEqual(self.e.evaluate(s)["status"],"HOLD_MASTER_AUDIO_AMBIGUITY")
 def test_cloud_unavailable_holds(self):
  s=copy.deepcopy(self.s);s["files"][0]["cloud_bytes_local"]=False;s["files"][0]["sha256"]=None;self.assertEqual(self.e.evaluate(s)["status"],"HOLD_CLOUD_BYTES_UNAVAILABLE")
 def test_unsupported_holds(self):
  s=copy.deepcopy(self.s);x=copy.deepcopy(s["files"][0]);x.update(file_id="x",name="notes.txt",sha256=digest(b"x"),size=1);s["files"].append(x);self.assertEqual(self.e.evaluate(s)["status"],"HOLD_UNSUPPORTED_FILE")
 def test_video_duplicate_suppressed(self):
  s=copy.deepcopy(self.s);x=copy.deepcopy(s["files"][0]);x.update(file_id="v3",name="copy.mov");s["files"].append(x);self.assertEqual(len(self.run2(s)["aliases"]),1)
 def test_duplicate_event_suppressed(self):
  r=self.run2();self.assertEqual(self.run2(emitted=r["event_key"])["status"],"DUPLICATE_EVENT_SUPPRESSED")
 def test_source_drift_holds(self):
  cp=self.e.stability_checkpoint(self.s);s=copy.deepcopy(self.s);s["files"][0].update(sha256=digest(b"changed"),size=7,modified_token="2");self.assertEqual(self.e.evaluate(s,cp)["status"],"HOLD_SOURCE_DRIFT")
 def test_new_file_restarts_stability(self):
  cp=self.e.stability_checkpoint(self.s);s=copy.deepcopy(self.s);x=copy.deepcopy(s["files"][-1]);x.update(file_id="p2",name="more.jpg",sha256=digest(b"more"),size=4);s["files"].append(x);self.assertEqual(self.e.evaluate(s,cp)["status"],"PENDING_STABILITY")
 def test_wrong_drive_fails(self):
  s=copy.deepcopy(self.s);s["drive_id"]="wrong";self.assertRaises(ValueError,self.e.evaluate,s)
 def test_filename_order_irrelevant(self):
  a=self.run2();s=copy.deepcopy(self.s);s["files"].reverse();b=self.run2(s);self.assertEqual(a["event_key"],b["event_key"])


if __name__=="__main__": unittest.main()
