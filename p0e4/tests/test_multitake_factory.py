import copy
import unittest

from multitake.factory import MultiTakeFactory, digest


G={"production_deployment_authorized":False,"publication_authorized":False,"first_real_poster":"PAUSED_BY_NITIN"}


class MultiTakeTests(unittest.TestCase):
 def setUp(self):
  self.f=MultiTakeFactory(); self.blobs={"synthetic://a.mov":b"take-a","synthetic://b.mov":b"take-b","synthetic://master.wav":b"master"}
  self.m={"schema":"MULTI_TAKE_RAW_DROP_V01","scope":"SYNTHETIC_DISPOSABLE_ONLY","governance":G,"assets":[
   {"asset_id":"t1","role":"TAKE","source_uri":"synthetic://a.mov","sha256":digest(b"take-a"),"bytes":6},
   {"asset_id":"t2","role":"TAKE","source_uri":"synthetic://b.mov","sha256":digest(b"take-b"),"bytes":6},
   {"asset_id":"m1","role":"MASTER_AUDIO","source_uri":"synthetic://master.wav","sha256":digest(b"master"),"bytes":6}]}
  self.i=self.f.ingest(self.m,self.blobs)
  self.p=self.f.probe(self.i,{"t1":{"duration_ms":10000,"fps_num":25,"fps_den":1,"width":1920,"height":1080,"orientation":"LANDSCAPE","guide_audio_present":True,"full_decode":True},"t2":{"duration_ms":9000,"fps_num":30000,"fps_den":1001,"width":1080,"height":1920,"orientation":"PORTRAIT","guide_audio_present":True,"full_decode":True}})
  ev=digest(b"alignment")
  self.o={"t1":{"method":"CAMERA_GUIDE_AUDIO_CORRELATION","offset_ms":120,"drift_ppm":10,"confidence_milli":940,"usable_start_ms":100,"usable_end_ms":9000,"anchor_count":5,"evidence_sha256":ev},"t2":{"method":"CAMERA_GUIDE_AUDIO_CORRELATION","offset_ms":-300,"drift_ppm":-20,"confidence_milli":910,"usable_start_ms":200,"usable_end_ms":8500,"anchor_count":4,"evidence_sha256":ev}}
  self.a=self.f.align(self.p,self.o); self.s=self.f.synchronized_set(self.p,self.a,self.f.bind_master_audio(self.i))
  obs=[{"asset_id":x,"ranges":[{"start_ms":200,"end_ms":4000,"performance_score_milli":900,"reason_code":"DELIVERY"}],"evidence_sha256":digest(x.encode())} for x in ("t1","t2")]
  self.g=self.f.validate_intelligence(self.s,{"schema":"GEMINI_MULTI_TAKE_PERFORMANCE_INTELLIGENCE_V01","synchronized_take_set_sha256":self.s["set_sha256"],"agent_isolation":"INDEPENDENT_NO_CLAUDE_OR_CHATGPT_CONCLUSIONS","take_observations":obs,"lyrics_or_captions_invented":False})
  self.e={"schema":"MULTI_TAKE_EDIT_DECISION_LIST_V01","synchronized_take_set_sha256":self.s["set_sha256"],"intelligence_sha256":self.g["intelligence_sha256"],"filename_semantics_used":False,"segments":[{"segment_id":"s1","take_asset_id":"t1","timeline_start_ms":0,"timeline_end_ms":3000,"take_start_ms":200,"take_end_ms":3200,"performer_visible":True,"evidence_sha256":digest(b"s1"),"reason_code":"DELIVERY"},{"segment_id":"s2","take_asset_id":"t2","timeline_start_ms":3000,"timeline_end_ms":6000,"take_start_ms":300,"take_end_ms":3300,"performer_visible":True,"evidence_sha256":digest(b"s2"),"reason_code":"FRAMING"}],"derivatives":[{"derivative_id":"d1","start_ms":0,"end_ms":5000,"platform":"SHORT","performer_visible_ms":5000}]}

 def test_ingest_and_master_route(self): self.assertEqual(self.f.bind_master_audio(self.i)["take_audio_use"],"SYNC_EVIDENCE_ONLY")
 def test_real_scope_blocked(self):
  m=copy.deepcopy(self.m);m["scope"]="REAL";self.assertRaises(ValueError,self.f.ingest,m,self.blobs)
 def test_source_drift_blocked(self):
  m=copy.deepcopy(self.m);m["assets"][0]["sha256"]="0"*64;self.assertRaises(ValueError,self.f.ingest,m,self.blobs)
 def test_duplicate_suppressed(self):
  m=copy.deepcopy(self.m);m["assets"].insert(2,{"asset_id":"dup","role":"TAKE","source_uri":"synthetic://a2.mov","sha256":digest(b"take-a"),"bytes":6});b=dict(self.blobs,**{"synthetic://a2.mov":b"take-a"})
  self.assertEqual(self.f.ingest(m,b)["aliases"][0]["status"],"DUPLICATE_SUPPRESSED")
 def test_probe_supports_different_media(self): self.assertTrue(self.p["takes"][0]["normalization"]["frame_rate_conform"])
 def test_low_confidence_hold(self):
  o=copy.deepcopy(self.o);o["t1"]["confidence_milli"]=600;self.assertEqual(self.f.align(self.p,o)["status"],"HOLD_ALIGNMENT_REVIEW")
 def test_drift_hold(self):
  o=copy.deepcopy(self.o);o["t2"]["drift_ppm"]=150;self.assertIn("MATERIAL_DRIFT",self.f.align(self.p,o)["takes"][1]["hold_reasons"])
 def test_insufficient_anchors_hold(self):
  o=copy.deepcopy(self.o);o["t1"]["anchor_count"]=2;self.assertEqual(self.f.align(self.p,o)["status"],"HOLD_ALIGNMENT_REVIEW")
 def test_bad_usable_range_hold(self):
  o=copy.deepcopy(self.o);o["t2"]["usable_end_ms"]=99999;self.assertEqual(self.f.align(self.p,o)["status"],"HOLD_ALIGNMENT_REVIEW")
 def test_sync_set_rejects_hold(self):
  a=copy.deepcopy(self.a);a["status"]="HOLD_ALIGNMENT_REVIEW";self.assertRaises(ValueError,self.f.synchronized_set,self.p,a,self.f.bind_master_audio(self.i))
 def test_intelligence_binding(self):
  g=copy.deepcopy(self.g);g["synchronized_take_set_sha256"]="0"*64;self.assertRaises(ValueError,self.f.validate_intelligence,self.s,g)
 def test_edl_green(self): self.assertEqual(self.f.validate_edl(self.s,self.g,self.e)["status"],"GREEN_MACHINE_READABLE")
 def test_edl_gap_fails(self):
  e=copy.deepcopy(self.e);e["segments"][1]["timeline_start_ms"]=3100;self.assertRaises(ValueError,self.f.validate_edl,self.s,self.g,e)
 def test_edl_outside_usable_fails(self):
  e=copy.deepcopy(self.e);e["segments"][0]["take_start_ms"]=0;self.assertRaises(ValueError,self.f.validate_edl,self.s,self.g,e)
 def test_performance_rule_fails(self):
  e=copy.deepcopy(self.e);e["segments"][1]["performer_visible"]=False;self.assertRaises(ValueError,self.f.validate_edl,self.s,self.g,e)
 def test_derivative_limit(self):
  e=copy.deepcopy(self.e);e["derivatives"]=[dict(self.e["derivatives"][0],derivative_id=str(x)) for x in range(5)];self.assertRaises(ValueError,self.f.validate_edl,self.s,self.g,e)
 def test_production_contract_and_text_gate(self):
  edl=self.f.validate_edl(self.s,self.g,self.e);c={"schema":"MULTI_TAKE_PRODUCTION_TRANSLATION_V01","edl_sha256":edl["edl_sha256"],"mode":"PLAN_ONLY_NO_EXTERNAL_EXECUTION","final_audio_route":"AUTHORITATIVE_MASTER_ONLY","guide_audio_muted":True,"color":{"normalization":{},"shot_match":{},"creative_look":{}},"operations":[{"operation_id":"z","kind":"zoom","start_ms":0,"end_ms":1000,"evidence_sha256":digest(b"z"),"parameters":{}}]}
  self.assertEqual(self.f.validate_production_contract(edl,c)["status"],"VALIDATED_PLAN_ONLY")
  c["operations"][0]["kind"]="caption";self.assertRaises(ValueError,self.f.validate_production_contract,edl,c)
 def test_excessive_effects_fail(self):
  edl=self.f.validate_edl(self.s,self.g,self.e);c={"schema":"MULTI_TAKE_PRODUCTION_TRANSLATION_V01","edl_sha256":edl["edl_sha256"],"mode":"PLAN_ONLY_NO_EXTERNAL_EXECUTION","final_audio_route":"AUTHORITATIVE_MASTER_ONLY","guide_audio_muted":True,"color":{"normalization":{},"shot_match":{},"creative_look":{}},"operations":[{"operation_id":"x","kind":"effect","start_ms":0,"end_ms":2000,"evidence_sha256":digest(b"x"),"parameters":{}}]}
  self.assertRaises(ValueError,self.f.validate_production_contract,edl,c)
 def test_each_qc_defect_routes_repair(self):
  good={x:"PASS" for x in self.f.QC_CATEGORIES}
  for defect in self.f.QC_CATEGORIES:
   q=dict(good);q[defect]="FAIL";self.assertEqual(self.f.qc(digest(b"out"),q)["status"],"REPAIR_REQUIRED")
 def test_qc_green_and_repair_reqc(self):
  q=self.f.qc(digest(b"new"),{x:"PASS" for x in self.f.QC_CATEGORIES});self.assertEqual(self.f.repair(digest(b"old"),digest(b"new"),1,self.s["set_sha256"],q)["status"],"GREEN_AFTER_RE_QC")
 def test_repair_budget(self):
  q=self.f.qc(digest(b"new"),{x:"PASS" for x in self.f.QC_CATEGORIES});self.assertRaises(ValueError,self.f.repair,digest(b"old"),digest(b"new"),3,self.s["set_sha256"],q)
 def test_deterministic_replay(self): self.assertEqual(self.f.validate_edl(self.s,self.g,self.e),self.f.validate_edl(self.s,self.g,self.e))


if __name__=='__main__': unittest.main()
