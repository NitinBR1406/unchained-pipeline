import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def test_integrated_preview_contract():
 c=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/config.json").read_text())
 i=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/integrated_preview_v01.json").read_text())
 assert c["effects_default_enabled"] is False
 assert i["defaults"]["lyrics_on_missing_verification"]=="OMIT"
 assert i["instance"]["lyrics"] is None
 assert i["rhythm_instance"]["counts"]=={"cuts":5,"zooms":5,"shakes":4}
 assert i["brand_standard_sha256"]==sha(ROOT/"p0e4/branding/UNCHAINED_BRAND_STANDARD_V01.json")
 assert {"text","timing","brand_standard_sha256","logo_sha256","rhythm_event_schedule","effect_strength"}<=set(c["cache_key_fields"])

def test_source_aware_ceiling_free_v08_contract():
 v=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/integrated_preview_ceiling_free_v08.json").read_text())
 assert v["inherits"]=="integrated_preview_source_sync_v07.json"
 assert v["source_geometry_profile"]=={
  "apply_before_text_and_logo":True,
  "center":[0.5,0.72],
  "minimum_size":2.3,
  "recovery_may_cross_below_minimum":False,
  "source_sha256":"8361dc4346bf351abef670bb168aaa170e0c03539656aec8d2a6819646175971",
 }
 assert v["motion_migration"]["method"]=="PROPORTIONAL_SCALE_ABOVE_SOURCE_SPECIFIC_BASE"
 assert v["motion_migration"]["relative_timing_and_intensity_preserved"] is True
 assert {"source_geometry_profile","safe_base_center","safe_base_minimum_size","relative_motion_curve_sha256"}<=set(v["cache_invalidation_additions"])
