"""Transparent mixed-master drum-transient discovery; never an effect policy."""
from __future__ import annotations
import hashlib,json,wave
from pathlib import Path
import numpy as np

METHOD_VERSION='KICK_SNARE_MIXED_MASTER_HEURISTIC_V01'
SETTINGS={'hop_ms':10,'window_ms':42.667,'kick_band_hz':[35,180],'snare_band_hz':[700,6000],'broad_band_hz':[35,9000],'minimum_gap_ms':120,'candidate_robust_z':2.4,'high_confidence_margin':0.28,'medium_confidence_margin':0.12}
def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read_pcm24(path):
 with wave.open(str(path),'rb') as w:
  assert w.getsampwidth()==3 and w.getnchannels()==2
  rate=w.getframerate();raw=np.frombuffer(w.readframes(w.getnframes()),dtype=np.uint8).reshape(-1,3)
 v=(raw[:,0].astype(np.int32)|(raw[:,1].astype(np.int32)<<8)|(raw[:,2].astype(np.int32)<<16));v=np.where(v&0x800000,v-0x1000000,v).astype(np.float32)/8388608
 return v.reshape(-1,2).mean(axis=1),rate
def robust_z(x):
 med=np.median(x);mad=np.median(np.abs(x-med))+1e-12
 return (x-med)/(1.4826*mad)
def peak_indices(values,threshold,distance):
 candidates=[i for i in range(1,len(values)-1) if values[i]>=threshold and values[i]>=values[i-1] and values[i]>=values[i+1]]
 chosen=[]
 for i in sorted(candidates,key=lambda j:float(values[j]),reverse=True):
  if all(abs(i-j)>=distance for j in chosen):chosen.append(i)
 return np.array(sorted(chosen),dtype=int)
def analyze(path):
 path=Path(path);audio,rate=read_pcm24(path);hop=round(rate*SETTINGS['hop_ms']/1000);win=2048;window=np.hanning(win).astype(np.float32)
 n=1+(len(audio)-win)//hop;frames=np.lib.stride_tricks.as_strided(audio,shape=(n,win),strides=(audio.strides[0]*hop,audio.strides[0]),writeable=False)
 mag=np.abs(np.fft.rfft(frames*window,axis=1)).astype(np.float32);freq=np.fft.rfftfreq(win,1/rate)
 flux=np.maximum(np.diff(mag,axis=0,prepend=mag[:1]),0)
 def band(lo,hi):return flux[:,(freq>=lo)&(freq<hi)].mean(axis=1)
 low,high,broad=band(35,180),band(700,6000),band(35,9000);bz=robust_z(np.log1p(broad));peaks=peak_indices(bz,SETTINGS['candidate_robust_z'],round(SETTINGS['minimum_gap_ms']/SETTINGS['hop_ms']))
 lz,hz=robust_z(np.log1p(low)),robust_z(np.log1p(high));events=[]
 for i in peaks:
  ls=max(0,float(lz[i]));hs=max(0,float(hz[i]));total=ls+hs+1e-9;k=ls/total;s=hs/total;margin=abs(k-s)
  if max(ls,hs)<1.6 or margin<SETTINGS['medium_confidence_margin']:label='uncertain'
  else:label='kick' if k>s else 'snare'
  conf='high' if margin>=SETTINGS['high_confidence_margin'] and max(ls,hs)>=3 else ('medium' if label!='uncertain' else 'low')
  ms=int(round(i*hop*1000/rate));events.append({'time_ms':ms,'frame_30fps':round(ms*30/1000),'classification':label,'confidence':conf,'confidence_score':round(min(.95,.35+.1*max(ls,hs)+.45*margin),3),'broadband_robust_z':round(float(bz[i]),3),'low_band_robust_z':round(float(lz[i]),3),'snare_band_robust_z':round(float(hz[i]),3),'kick_ratio':round(k,3),'snare_ratio':round(s,3),'source':'MIXED_MASTER_ONLY'})
 return {'schema':METHOD_VERSION,'input':{'path':str(path.resolve()),'sha256':sha256(path),'sample_rate':rate,'channels':2,'sample_width_bits':24,'duration_ms':round(len(audio)*1000/rate)},'settings':SETTINGS,'events':events,'counts':{x:sum(e['classification']==x for e in events) for x in ('kick','snare','uncertain')},'limitations':['Heuristic classification from a mastered stereo mix, not isolated drum stems.','Vocals, bass, cymbals and arrangement transients can cause false positives or class ambiguity.','Confidence is method-internal and uncalibrated; it is not a probability of correctness.','No event implies an effect and no creative mapping is selected.']}
def main(src,out):Path(out).write_text(json.dumps(analyze(src),indent=2,sort_keys=True)+'\n')
if __name__=='__main__':
 import argparse;p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');a=p.parse_args();main(a.source,a.output)
