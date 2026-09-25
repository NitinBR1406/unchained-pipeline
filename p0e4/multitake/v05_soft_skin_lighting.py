"""Bounded V05 soft-lighting refinement on top of V04 natural skin."""
from __future__ import annotations
import colorsys, hashlib
from pathlib import Path
from multitake.v04_natural_skin import new_transform as v04_transform
from multitake.r1_highlight_refinement import smoothstep, gamut_safe

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def new_transform(rgb):
    """Gently compress bright skin peaks; retain hue, texture and midtones."""
    r,g,b=v04_transform(rgb); y=.2627*r+.6780*g+.0593*b; c=(r-y,g-y,b-y)
    sat=max(r,g,b)-min(r,g,b); h=colorsys.rgb_to_hsv(r,g,b)[0]*360
    dist=min(abs(h-28),360-abs(h-28))
    skin=(1-smoothstep(16,43,dist))*smoothstep(.035,.13,sat)
    high=smoothstep(.56,.76,y)*(1-smoothstep(.965,.997,y))
    peak=smoothstep(.72,.93,y)
    weight=skin*high
    if weight <= 1e-12 and skin*peak <= 1e-12:
        return (r,g,b)
    y2=y-.010*weight-.010*skin*peak*peak
    chroma_scale=1-.035*weight
    return gamut_safe(y2,c,chroma_scale)

def write_cube(path,size=33):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    lines=['TITLE "UNCHAINED V05 SOFT SKIN LIGHTING"',f'LUT_3D_SIZE {size}','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
    for b in range(size):
      for g in range(size):
       for r in range(size):
        lines.append('%.9f %.9f %.9f'%new_transform((r/(size-1),g/(size-1),b/(size-1))))
    p.write_text('\n'.join(lines)+'\n')
    return {'path':str(p),'sha256':sha256(p),'operation':'V04_PLUS_BOUNDED_HIGH_LUMINANCE_SKIN_COMPRESSION_AND_CHROMA_SOFTENING','max_additional_encoded_luma_delta':-.020,'max_bright_skin_chroma_reduction_fraction':.035,'midtones_preserved_by_weighting':True,'background_delta_requested':0.0,'spatial_mask':False,'skin_smoothing':False,'face_manipulation':False,'physical_relighting_claimed':False,'clipped_detail_recovery_claimed':False}
