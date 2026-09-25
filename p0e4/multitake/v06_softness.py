"""Bounded V06 peak-transition softening on the accepted V05 review baseline."""
from __future__ import annotations
import colorsys,hashlib
from pathlib import Path
from multitake.v05_soft_skin_lighting import new_transform as v05_transform
from multitake.r1_highlight_refinement import smoothstep,gamut_safe
def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def new_transform(rgb):
 r,g,b=v05_transform(rgb);y=.2627*r+.6780*g+.0593*b;c=(r-y,g-y,b-y);sat=max(r,g,b)-min(r,g,b)
 h=colorsys.rgb_to_hsv(r,g,b)[0]*360;dist=min(abs(h-28),360-abs(h-28))
 skin=(1-smoothstep(16,44,dist))*smoothstep(.03,.12,sat);bright=smoothstep(.52,.74,y)*(1-smoothstep(.97,.998,y));w=skin*bright
 if w<=1e-12:return (r,g,b)
 return gamut_safe(y-.012*w,c,1-.020*w)
def write_cube(path,size=33):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);lines=['TITLE "UNCHAINED V06 SOFTER SKIN LIGHTING"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
 for b in range(size):
  for g in range(size):
   for r in range(size):lines.append('%.9f %.9f %.9f'%new_transform((r/(size-1),g/(size-1),b/(size-1))))
 p.write_text('\n'.join(lines)+'\n');return {'path':str(p),'sha256':sha256(p),'operation':'V05_PLUS_SLIGHT_BRIGHT_SKIN_TRANSITION_SOFTENING','max_additional_encoded_luma_delta':-.012,'max_additional_bright_skin_chroma_reduction_fraction':.020,'background_delta_requested':0.0,'spatial_mask':False,'skin_smoothing':False,'physical_relighting_claimed':False,'clipped_detail_recovery_claimed':False}
