"""Read-only iCloud metadata discovery; never hydrate dataless files or follow links."""
import os,json,hashlib,signal,stat,wave,csv
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/nitinramdaras/Library/Mobile Documents/com~apple~CloudDocs')
OUT=Path('p0e4/evidence/catalog_discovery_v02')
MEDIA={'.wav','.aiff','.aif','.mp3','.m4a','.flac','.mp4','.mov','.m4v','.aac','.avi'}
EXCLUDE={'ING docs':'ADMIN_FINANCIAL','Automatiseringsocialmedia':'AUTOMATION_ADMIN','CAT docs':'ADMIN_DOCUMENTS'}
CONTAINERS={'NITIN 2008','Songs voor 2022','Video’s','Video-Opnames ','Optreden 10 mei oefening en opname','Downloads'}
def timeout(*args):raise TimeoutError('bounded read timeout')
signal.signal(signal.SIGALRM,timeout)
def bounded(fn,seconds=8):
 signal.alarm(seconds)
 try:return fn()
 finally:signal.alarm(0)
def save(name,obj):
 (OUT/(name+'.json')).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def sid(path):return 'cat2_'+hashlib.sha256(path.encode()).hexdigest()[:16]
def readbytes(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);assets=[];dirs=[];excluded=[];errors=[]
 top=bounded(lambda:sorted(os.scandir(ROOT),key=lambda e:e.name.casefold()))
 def walk(path,depth=0):
  try:entries=bounded(lambda:sorted(os.scandir(path),key=lambda e:e.name.casefold()))
  except Exception as e:errors.append({'path':str(path.relative_to(ROOT)),'error':type(e).__name__});return
  for e in entries:
   p=Path(e.path);rel=str(p.relative_to(ROOT))
   try:s=bounded(lambda:e.stat(follow_symlinks=False))
   except Exception as ex:errors.append({'path':rel,'error':type(ex).__name__});continue
   if e.name in EXCLUDE or e.name=='.DS_Store' or (depth==0 and p.suffix.lower()=='.pdf' and e.name!='Lyrics.pdf'):
    excluded.append({'path':rel,'reason':EXCLUDE.get(e.name,'NON_MUSIC_ADMIN_OR_SYSTEM_METADATA'),'basis':'name/type routing only; contents not read','reversible':True});continue
   if stat.S_ISDIR(s.st_mode):
    dirs.append({'path':rel,'depth':depth,'flags':s.st_flags})
    if depth<12:walk(p,depth+1)
    else:errors.append({'path':rel,'error':'DEPTH_LIMIT'})
    continue
   row={'asset_id':sid(rel),'path':rel,'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'flags':s.st_flags,'allocated_blocks':s.st_blocks,'extension':p.suffix.lower(),'sha256':None,'availability':'UNKNOWN','technical':{},'semantic_completion':'UNKNOWN'}
   if stat.S_ISLNK(s.st_mode):row['availability']='SYMLINK_NOT_FOLLOWED'
   elif s.st_flags & 0x40000000 or e.name.endswith('.icloud'):row['availability']='NOT_LOCAL_AVAILABLE'
   elif stat.S_ISREG(s.st_mode):
    row['availability']='LOCAL_METADATA_OBSERVED'
    if p.suffix.lower() in MEDIA and s.st_size<=1024**3:
     try:
      row['sha256']=bounded(lambda:readbytes(p),5)
      after=p.stat();assert (after.st_size,after.st_mtime_ns)==(s.st_size,s.st_mtime_ns)
      row['availability']='LOCAL_BYTES_VERIFIED'
      if p.suffix.lower()=='.wav':
       def wavinfo():
        with wave.open(str(p),'rb') as w:return {'format':'PCM_WAVE','channels':w.getnchannels(),'sample_rate_hz':w.getframerate(),'sample_width_bytes':w.getsampwidth(),'frames':w.getnframes(),'duration_seconds':w.getnframes()/w.getframerate(),'validation':'header parsed; full decode not performed'}
       try:row['technical']=bounded(wavinfo)
       except Exception as ex:row['technical']={'probe_status':type(ex).__name__}
     except Exception as ex:row.update(sha256=None,availability='UNKNOWN',read_error=type(ex).__name__)
   assets.append(row)
 walk(ROOT)
 candidates=[];collections=[]
 def candidate(path,kind,ids):
  candidates.append({'candidate_id':sid(path),'path':path,'label':Path(path).name,'classification':kind,'classification_confidence':'PROVISIONAL','asset_ids':ids,'TYPE':'UNKNOWN','not_canonical_song_identity':True})
 for e in top:
  if not e.is_dir(follow_symlinks=False) or e.name in EXCLUDE:continue
  group=[a for a in assets if a['path'].startswith(e.name+'/')];media=[a for a in group if a['extension'] in MEDIA]
  if e.name in CONTAINERS:
   children=[]
   if e.name=='NITIN 2008':
    for a in media:
     candidate(a['path'],'INDIVIDUAL_SONG_CANDIDATE_IN_COLLECTION',[a['asset_id']]);children.append(sid(a['path']))
   else:
    immediate=[d['path'] for d in dirs if d['depth']==1 and d['path'].startswith(e.name+'/')]
    for d in immediate:
     aa=[a['asset_id'] for a in media if a['path'].startswith(d+'/')]
     if aa:candidate(d,'CHILD_FOLDER_CANDIDATE',aa);children.append(sid(d))
    direct=[a for a in media if a['path'].count('/')==1]
    for a in direct:candidate(a['path'],'UNASSIGNED_MEDIA_CANDIDATE',[a['asset_id']]);children.append(sid(a['path']))
   collections.append({'path':e.name,'classification':'COLLECTION_OR_SPECIAL_CONTAINER','children':children,'asset_count':len(group),'is_song':False})
  elif media:
   kind='MASHUP_MEDLEY_CANDIDATE' if any(t in e.name.lower() for t in ['mash','medley']) else 'SONG_FOLDER_CANDIDATE'
   candidate(e.name,kind,[a['asset_id'] for a in group])
  else:collections.append({'path':e.name,'classification':'UNRESOLVED_CONTAINER','children':[],'asset_count':len(group),'is_song':False})
 for a in assets:
  if '/' not in a['path'] and a['extension'] in MEDIA:candidate(a['path'],'UNASSIGNED_MEDIA_CANDIDATE',[a['asset_id']])
 # Unassigned recordings are assets, not inferred songs; one container question replaces per-file readiness forms.
 unassigned=[c for c in candidates if c['classification']=='UNASSIGNED_MEDIA_CANDIDATE']
 candidates=[c for c in candidates if c['classification']!='UNASSIGNED_MEDIA_CANDIDATE']
 for col in collections:
  ids={c['candidate_id'] for c in candidates};col['unassigned_asset_candidate_ids']=[i for i in col['children'] if i not in ids];col['children']=[i for i in col['children'] if i in ids]
 save('UNASSIGNED_MEDIA_CANDIDATES',unassigned)
 fields=['TYPE','MUSIC_READY','LYRICS_READY','VOCALS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY','PRIORITY','NEXT_ACTION','ACTION_OWNER']
 review=[dict(candidate_id=c['candidate_id'],label=c['label'],path=c['path'],asset_count=len(c['asset_ids']),**{f:'UNKNOWN' for f in fields}) for c in candidates]
 observed=datetime.now(timezone.utc).isoformat()
 save('CATALOG_DISCOVERY_V02',{'observed_at':observed,'source_root':str(ROOT),'top_level':[{'name':e.name,'directory':e.is_dir(follow_symlinks=False)} for e in top],'directories':dirs,'errors':errors,'top_level_discovery_complete':True,'recursive_discovery_complete':not errors,'source_mutation_requested':False,'cloud_hydration_requested':False,'limitations':['Filename/type classifications provisional','No semantic readiness inferred','No full audio decode; WAV header metadata only','Archives not expanded; document contents not read','File read may update OS access metadata; no source writes performed']})
 save('SONG_FOLDER_CANDIDATES',candidates);save('NON_SONG_EXCLUSIONS',excluded);save('COLLECTIONS_AND_CHILDREN',collections);save('TECHNICAL_ASSET_INVENTORY',assets)
 save('NITIN_SEMANTIC_REVIEW_QUEUE',{'status':'WAITING_FOR_NITIN','instructions':'Confirm/correct candidate identity and TYPE first; merge duplicate versions. For readiness/revision/live use ✓ / ✗ / ?; ? stays UNKNOWN. Batch answers by folder/collection are allowed only when explicitly applicable. PRIORITY: high/medium/low/?; NEXT_ACTION and ACTION_OWNER: confirm/correct or ?. No default owner or readiness inferred.','container_questions':[{'path':c['path'],'question':'Bevat deze map zelfstandige nummers of alleen versies/referenties/opnames? Bevestig of corrigeer de indeling; geen readiness per mediabestand nodig.','answer':'UNKNOWN','unassigned_count':len(c.get('unassigned_asset_candidate_ids',[]))} for c in collections],'rows':review,'master_catalog_status':'DEFERRED_UNTIL_SEMANTIC_REVIEW','shared_drive_or_production_mutation':False})
 with (OUT/'NITIN_SEMANTIC_REVIEW_QUEUE.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(review[0]));w.writeheader();w.writerows(review)
 print(json.dumps({'top_level':len(top),'assets':len(assets),'candidates':len(candidates),'collections':len(collections),'exclusions':len(excluded),'errors':len(errors),'hashed':sum(a['sha256'] is not None for a in assets)}))
if __name__=='__main__':main()
