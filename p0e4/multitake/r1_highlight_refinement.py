"""Bounded R1 highlight/background refinement in the encoded Rec.2100 HLG domain."""
from __future__ import annotations

import colorsys, hashlib, json
from pathlib import Path


VARIANTS=("CURRENT_R1_CALMER_BACKGROUND_RICHER_SUBJECT_CANDIDATE","REVISED_GENTLER_HIGHLIGHTS_CALMER_BACKGROUND")


def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def smoothstep(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a))); return t*t*(3-2*t)


def gamut_safe(y,c,scale):
    limit=scale
    for v in c:
        if v>0: limit=min(limit,(1-y)/v)
        elif v<0: limit=min(limit,(0-y)/v)
    s=max(0.0,min(scale,limit*.995))
    return tuple(max(0.0,min(1.0,y+v*s)) for v in c)


def revised_transform(rgb):
    """Preserve hue/skin structure; apply a small signal-domain shoulder and chroma gating."""
    r,g,b=rgb; y=.2627*r+.6780*g+.0593*b; c=(r-y,g-y,b-y); sat=max(rgb)-min(rgb)
    h=colorsys.rgb_to_hsv(r,g,b)[0]*360; dist=min(abs(h-28),360-abs(h-28))
    skin=(1-smoothstep(16,42,dist))*smoothstep(.055,.16,sat)*smoothstep(.13,.28,y)*(1-smoothstep(.80,.96,y))
    neutral=1-smoothstep(.065,.26,sat)
    shoulder=smoothstep(.70,.94,y)
    y2=y-.020*shoulder*shoulder
    scale=1.035-.100*neutral+.065*skin
    return gamut_safe(y2,c,scale)


def write_cube(path,size=33):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    lines=['TITLE "UNCHAINED R1 HIGHLIGHT BACKGROUND REFINEMENT"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
    for b in range(size):
        for g in range(size):
            for r in range(size):
                out=revised_transform((r/(size-1),g/(size-1),b/(size-1)))
                lines.append('%.9f %.9f %.9f'%out)
    p.write_text('\n'.join(lines)+'\n')
    return {'path':str(p),'sha256':sha256(p),'size':size,'operation':'BOUNDED_HLG_SIGNAL_SHOULDER_PLUS_HUE_CHROMA_GATING',
            'highlight_max_encoded_delta':-.020,'background_neutral_chroma_delta':-.100,'skin_chroma_delta':.065,
            'spatial_mask':False,'blur':False,'semantic_subject_isolation_claimed':False}


def validate_contract(c):
    assert c['schema']=='R1_HIGHLIGHT_BACKGROUND_REFINEMENT_CONTRACT_V01'
    assert c['variant_order']==list(VARIANTS) and c['segment_seconds']>=5 and c['segment_seconds']<=8
    assert len(c['representative_scenes'])==4 and c['full_master_allowed'] is False
    assert c['color_management']=={'input':'Rec.2100 HLG','timeline':'Rec.2100 HLG','output':'Rec.2100 HLG','tone_mapping':'None','gamut_mapping':'None'}
    assert c['governance']['final_color_approved'] is False and c['governance']['publication_authorized'] is False


def load(path):
    c=json.loads(Path(path).read_text());validate_contract(c);return c
