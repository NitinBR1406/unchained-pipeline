"""Third bounded HLG refinement: peak facial highlights including bright eyelid skin."""
from __future__ import annotations
import colorsys, hashlib, json
from pathlib import Path
from multitake.r1_face_background_softness import new_transform as v02_transform
from multitake.r1_highlight_refinement import smoothstep, gamut_safe

VARIANTS=("CURRENT_V02_GENTLER_FACE_CALMER_BACKGROUND","NEW_V03_PEAK_HIGHLIGHTS_EYELIDS")

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def new_transform(rgb):
    """Composite V02 with bounded skin-hue high-luma compression; no spatial/face mask."""
    r,g,b=v02_transform(rgb); y=.2627*r+.6780*g+.0593*b; c=(r-y,g-y,b-y); sat=max(r,g,b)-min(r,g,b)
    h=colorsys.rgb_to_hsv(r,g,b)[0]*360; dist=min(abs(h-28),360-abs(h-28))
    skin=(1-smoothstep(16,42,dist))*smoothstep(.045,.14,sat)*smoothstep(.34,.52,y)*(1-smoothstep(.94,.995,y))
    bright_lid_skin=smoothstep(.48,.66,y)*(1-smoothstep(.78,.91,y))
    peak=smoothstep(.68,.92,y)
    y2=y-.004*skin*bright_lid_skin-.020*skin*peak*peak
    return gamut_safe(y2,c,1.0)

def write_cube(path,size=33):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    lines=['TITLE "UNCHAINED R1 V03 PEAK HIGHLIGHTS EYELIDS"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
    for b in range(size):
      for g in range(size):
       for r in range(size):
        o=new_transform((r/(size-1),g/(size-1),b/(size-1)));lines.append('%.9f %.9f %.9f'%o)
    p.write_text('\n'.join(lines)+'\n')
    return {'path':str(p),'sha256':sha256(p),'size':size,'operation':'COMPOSITE_V02_PLUS_BOUNDED_SKIN_HUE_PEAK_COMPRESSION','additional_bright_eyelid_skin_max_encoded_delta':-.004,'additional_peak_skin_highlight_max_encoded_delta':-.020,'background_delta':0.0,'spatial_mask':False,'semantic_eyelid_detection_claimed':False,'blur':False,'skin_smoothing':False,'face_manipulation':False}

def validate_contract(c):
    assert c['schema']=='R1_PEAK_HIGHLIGHTS_EYELIDS_CONTRACT_V03'
    assert c['variant_order']==list(VARIANTS) and c['segment_seconds']==5
    assert len(c['representative_scenes'])==4 and c['full_master_allowed'] is False
    assert c['color_management']=={'input':'Rec.2100 HLG','timeline':'Rec.2100 HLG','output':'Rec.2100 HLG','tone_mapping':'None','gamut_mapping':'None'}
    assert c['background_change_requested'] is False
    assert c['references_separated'] == ['SOURCE_BYTES_REFERENCE','RESOLVE_DECODE_REFERENCE','IDENTITY_ROUNDTRIP_REFERENCE']
    assert c['governance']['final_color_approved'] is False and c['governance']['publication_authorized'] is False

def load(path):
    c=json.loads(Path(path).read_text());validate_contract(c);return c
