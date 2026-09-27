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
