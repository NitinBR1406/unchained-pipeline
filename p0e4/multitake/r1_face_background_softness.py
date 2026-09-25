"""Second bounded HLG refinement: gentler skin highlights and calmer neutral background."""
from __future__ import annotations
import colorsys, hashlib, json
from pathlib import Path
from multitake.r1_highlight_refinement import revised_transform as v01_transform, smoothstep, gamut_safe

VARIANTS=("CURRENT_V01_REVISED_HLG","NEW_V02_GENTLER_FACE_CALMER_BACKGROUND")

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def new_transform(rgb):
    """Composite the accepted V01 technical basis with bounded hue/luma/chroma gating."""
    r,g,b=v01_transform(rgb); y=.2627*r+.6780*g+.0593*b; c=(r-y,g-y,b-y); sat=max(r,g,b)-min(r,g,b)
    h=colorsys.rgb_to_hsv(r,g,b)[0]*360; dist=min(abs(h-28),360-abs(h-28))
    skin=(1-smoothstep(17,43,dist))*smoothstep(.055,.16,sat)*smoothstep(.16,.30,y)*(1-smoothstep(.91,.985,y))
    neutral=(1-smoothstep(.065,.22,sat))*smoothstep(.30,.52,y)
    skin_mid=smoothstep(.38,.76,y); skin_peak=smoothstep(.66,.93,y)
    background_high=smoothstep(.44,.84,y)
    y2=y-.010*skin*skin_mid-.014*skin*skin_peak*skin_peak-.010*neutral*background_high
    scale=1-.045*neutral
    return gamut_safe(y2,c,scale)

def write_cube(path,size=33):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    lines=['TITLE "UNCHAINED R1 V02 GENTLER FACE CALMER BACKGROUND"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
    for b in range(size):
      for g in range(size):
       for r in range(size):
        o=new_transform((r/(size-1),g/(size-1),b/(size-1)));lines.append('%.9f %.9f %.9f'%o)
    p.write_text('\n'.join(lines)+'\n')
    return {'path':str(p),'sha256':sha256(p),'size':size,'operation':'COMPOSITE_V01_PLUS_SKIN_HIGHLIGHT_AND_NEUTRAL_BACKGROUND_GATING','additional_skin_midtone_max_encoded_delta':-.010,'additional_skin_highlight_max_encoded_delta':-.014,'additional_neutral_background_luma_delta':-.010,'additional_neutral_background_chroma_delta':-.045,'spatial_mask':False,'blur':False,'skin_smoothing':False,'semantic_face_tracking_claimed':False}

def validate_contract(c):
    assert c['schema']=='R1_FACE_BACKGROUND_SOFTNESS_CONTRACT_V02'
    assert c['variant_order']==list(VARIANTS) and c['segment_seconds']==5
    assert len(c['representative_scenes'])==4 and c['full_master_allowed'] is False
    assert c['color_management']=={'input':'Rec.2100 HLG','timeline':'Rec.2100 HLG','output':'Rec.2100 HLG','tone_mapping':'None','gamut_mapping':'None'}
    assert c['references_separated'] == ['SOURCE_BYTES_REFERENCE','RESOLVE_DECODE_REFERENCE','IDENTITY_ROUNDTRIP_REFERENCE']
    assert c['governance']['final_color_approved'] is False and c['governance']['publication_authorized'] is False

def load(path):
    c=json.loads(Path(path).read_text());validate_contract(c);return c
