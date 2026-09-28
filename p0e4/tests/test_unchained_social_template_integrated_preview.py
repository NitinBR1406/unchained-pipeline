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

def test_caption_legibility_v09_contract():
 v=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/integrated_preview_caption_legibility_v09.json").read_text())
 assert v["inherits"]=="integrated_preview_ceiling_free_v08.json"
 timing=v["caption_timing"]
 assert timing["opening_hook_frames"][1] < 88
 assert timing["inherited_hook_disabled_from_clip_index"]==1
 assert timing["inherited_small_song_id_disabled"] is True
 style=v["caption_style"]
 assert style["opening_hook"]["size"]>=0.09
 assert style["title"]["size"]>=0.11
 assert style["artist"]["size"]>=0.065
 assert style["title"]["center"][1] < style["artist"]["center"][1]
 assert style["outline"]["opacity"]>0
 assert style["local_backing"]["appearance"]=="border_fill"
 assert style["local_backing"]["opacity"]>0
 assert all(v["preserved"].values())

def test_caption_sharpness_v10_contract():
 v=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/integrated_preview_caption_sharpness_v10.json").read_text())
 assert v["inherits"]=="integrated_preview_caption_legibility_v09.json"
 assert v["root_cause"]["proven"] is True
 style=v["caption_style"]
 assert style["opening_hook"]["size"]>0.09
 assert style["title"]["size"]>0.11
 assert style["artist"]["size"]>0.065
 for key in ("opening_hook","title","artist"):
  assert style[key]["opacity"]==1.0
  assert style[key]["softness"]==0.0
 assert style["outline"]["softness"]==0.0
 assert style["outline"]["thickness"]<0.035
 assert style["local_backing"]["opacity"]>0.52
 assert v["timing_inherited_unchanged"] is True
 assert all(v["preserved"].values())

def test_caption_clean_v11_contract():
 v=json.loads((ROOT/"p0e4/resolve/templates/UNCHAINED_SOCIAL_TEMPLATE_V01/integrated_preview_caption_clean_v11.json").read_text())
 assert v["inherits"]=="integrated_preview_caption_sharpness_v10.json"
 style=v["caption_style"]
 assert style["outline"]["enabled"] is False
 assert style["local_backing"]["enabled"] is False
 assert style["drop_shadow"]["enabled"] is False
 assert style["glow"]["enabled"] is False
 assert style["opening_hook"]["size"]==0.105
 assert style["title"]["size"]==0.125
 assert style["artist"]["size"]==0.075
 assert all(v["preserved"].values())
