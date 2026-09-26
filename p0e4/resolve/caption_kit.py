import hashlib
import json

class CaptionKitError(ValueError):
    pass

def canonical_sha256(value):
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()

def build_cache_key(variant, template_sha256, render_contract, source_binding):
    if len(template_sha256)!=64:
        raise CaptionKitError("TEMPLATE_SHA256_REQUIRED")
    payload={"text":variant.get("text"),"timing_ms":variant.get("timing_ms"),"styling":{k:variant.get(k) for k in ("font","font_primary","font_secondary","style","size","size_primary","size_secondary","position","accent","entrance_frames","exit_frames")},"template":variant.get("template"),"template_sha256":template_sha256,"render_contract":render_contract,"source_binding":source_binding}
    return canonical_sha256(payload)

def validate_render_gate(config):
    fonts=config["font_contract"]["resolve_inventory"]
    missing=[name for name in config["font_contract"]["required"] if not fonts.get(name,{}).get("installed",False)]
    if missing:
        raise CaptionKitError("REQUIRED_BRAND_FONTS_NOT_INSTALLED:"+",".join(missing))
    if config["variants"][-1].get("actual_lyric_mode")!="HOLD":
        raise CaptionKitError("UNVERIFIED_LYRIC_MODE_MUST_HOLD")
    return True
