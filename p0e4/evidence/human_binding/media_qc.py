"""Read-only exact-byte QC; derived preview images only, no source/video edits.
Requires numpy/Pillow in the bundled runtime. Uses existing ffmpeg executable.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3]
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(cmd):
 p=subprocess.run(cmd,capture_output=True,timeout=600)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-2000:])
 return p.stdout

def alignment(x,y,rate):
 m=len(y);n=len(x)
 yc=y-y.mean();length=1<<(n+m-1).bit_length()
 dot=np.fft.irfft(np.fft.rfft(x,length)*np.fft.rfft(yc[::-1],length),length)[m-1:n]
 cs=np.r_[0.,np.cumsum(x)];cs2=np.r_[0.,np.cumsum(x*x)]
 variance=np.maximum(cs2[m:]-cs2[:-m]-(cs[m:]-cs[:-m])**2/m,1e-12)
 corr=dot/np.sqrt(variance*np.sum(yc*yc))
 i=int(np.argmax(corr))
 return {'best_offset_seconds':round(i/rate,5),'normalized_waveform_correlation':round(float(corr[i]),6),
         'interpretation':'Signal similarity only; not an authenticated render lineage or creative approval.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cache',required=True);ap.add_argument('--ffmpeg',required=True);ap.add_argument('--out',required=True)
 args=ap.parse_args();cache=Path(args.cache);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 old=json.loads((ROOT/'p0e4/evidence/resume/MEDIA_QC.json').read_text())
 rate=8000;audios={};rows=[]
 for a in old['assets']:
  path=cache/a['name'];before=sha(path)
  if before!=a['sha256'] or path.stat().st_size!=a['size_bytes']:raise ValueError('Exact asset mismatch: '+a['name'])
  ff=[args.ffmpeg,'-nostdin','-v','error','-xerror','-i',str(path)]
  run(ff+['-map','0:v:0','-map','0:a:0','-f','null','-'])
  raw=run(ff+['-map','0:a:0','-ac','1','-ar',str(rate),'-f','f32le','-'])
  audio=np.frombuffer(raw,dtype='<f4').astype(np.float64);audios[a['file_id']]=audio
  duration=a['probe']['duration'];times=[min(t,duration-0.1) for t in ([.1,40,60,100,140,180,duration-.2] if duration>100 else [.1,duration*.25,duration*.5,duration*.75,duration-.2])]
  canvas=Image.new('RGB',(270*len(times),510),'#111111');draw=ImageDraw.Draw(canvas)
  for i,t in enumerate(times):
   raw=run([args.ffmpeg,'-nostdin','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-vf','scale=270:480','-pix_fmt','rgb24','-f','rawvideo','-'])
   image=Image.frombytes('RGB',(270,480),raw);canvas.paste(image,(i*270,30));draw.text((i*270+5,8),f'{t:.2f}s',fill='white')
  preview=a['name'].replace('.mp4','_contact.jpg');canvas.save(out/preview,quality=88)
  def rms(segment):return round(float(np.sqrt(np.mean(segment**2))),7)
  rows.append({'file_id':a['file_id'],'name':a['name'],'sha256':before,'size_bytes':path.stat().st_size,
   'full_av_decode':'PASS','source_unchanged':sha(path)==before,'probe_prior_hash_bound':a['probe'],
   'audio_measurement':{'sample_rate':rate,'channels_for_analysis':1,'duration_seconds':len(audio)/rate,
      'first_100ms_rms':rms(audio[:800]),'last_100ms_rms':rms(audio[-800:]),'first_sample':float(audio[0]),'last_sample':float(audio[-1]),
      'peak_abs_mono_resampled':float(np.max(np.abs(audio))),'limits':'Mono resampling measurements are not perceived loudness, true peak or listening review.'},
   'contact_sheet':preview,'sample_times_seconds':times,
   'motion_lipsync_review':'NOT_PERFORMED_FULL_MOTION','perceptual_audio_boundary_review':'NOT_PERFORMED',
   'creative_approval_inferred':False})
  print(a['name'],'sha/decode PASS',flush=True)
 master=audios['1ifHVAW1E0NjhN-eguBWUMNRekoemweAn']
 for r in rows:
  if r['file_id']!='1ifHVAW1E0NjhN-eguBWUMNRekoemweAn':
   r['audio_alignment_to_master']=alignment(master,audios[r['file_id']],rate)
 (out/'MEDIA_QC.json').write_text(json.dumps({'assets':rows,'method':'Exact SHA check + full A/V decode + mono 8kHz waveform match + stated static frame samples','limits':'No authenticated cut receipt; no independent Gemini/Claude result; no full-motion or listening approval.'},indent=2)+'\n')
 print('Media evidence complete')
if __name__=='__main__':main()
