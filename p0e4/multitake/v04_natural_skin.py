"""Bounded V04 natural-skin refinement on top of selected V03 HLG color."""
from __future__ import annotations
import colorsys,hashlib
from pathlib import Path
from multitake.r1_peak_highlights_eyelids import new_transform as v03_transform
from multitake.r1_highlight_refinement import smoothstep,gamut_safe

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def new_transform(rgb):
    r,g,b=v03_transform(rgb);y=.2627*r+.6780*g+.0593*b;c=(r-y,g-y,b-y);sat=max(r,g,b)-min(r,g,b)
    h=colorsys.rgb_to_hsv(r,g,b)[0]*360;dist=min(abs(h-28),360-abs(h-28))
    skin=(1-smoothstep(18,45,dist))*smoothstep(.035,.13,sat)*smoothstep(.16,.36,y)*(1-smoothstep(.94,.995,y))
    return gamut_safe(y,c,1-.075*skin)
def write_cube(path,size=33):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);lines=['TITLE "UNCHAINED V04 NATURAL SKIN"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
    for b in range(size):
      for g in range(size):
       for r in range(size): lines.append('%.9f %.9f %.9f'%new_transform((r/(size-1),g/(size-1),b/(size-1))))
    p.write_text('\n'.join(lines)+'\n');return {'path':str(p),'sha256':sha256(p),'operation':'V03_PLUS_BOUNDED_SKIN_HUE_CHROMA_REDUCTION','max_skin_chroma_reduction_fraction':.075,'luma_change_requested':False,'spatial_mask':False,'skin_smoothing':False,'face_manipulation':False}
