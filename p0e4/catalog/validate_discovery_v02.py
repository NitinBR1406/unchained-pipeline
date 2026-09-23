"""Offline evidence validation; never reads iCloud or changes semantic status."""
import json,hashlib
from pathlib import Path
P=Path('p0e4/evidence/catalog_discovery_v02')
def load(n):return json.loads((P/(n+'.json')).read_text())
def main():
 a=load('TECHNICAL_ASSET_INVENTORY');c=load('SONG_FOLDER_CANDIDATES');cols=load('COLLECTIONS_AND_CHILDREN');q=load('NITIN_SEMANTIC_REVIEW_QUEUE')
 ids={x['asset_id'] for x in a};assert len(ids)==len(a)
 assert len({x['candidate_id'] for x in c})==len(c)
 assert all(set(x['asset_ids'])<=ids for x in c)
 assert all(x['sha256'] is None for x in a if x['availability']=='NOT_LOCAL_AVAILABLE')
 assert all(x['availability']=='LOCAL_BYTES_VERIFIED' for x in a if x['sha256'])
 assert not any(x['path']=='NITIN 2008' for x in c)
 col=next(x for x in cols if x['path']=='NITIN 2008');assert len(col['children'])==8
 assert all(x['is_song'] is False for x in cols)
 assert len(q['rows'])==len(c)
 for r in q['rows']:
  for f in ['TYPE','MUSIC_READY','LYRICS_READY','VOCALS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY','PRIORITY','NEXT_ACTION','ACTION_OWNER']:assert r[f]=='UNKNOWN'
 assert q['shared_drive_or_production_mutation'] is False
 assert not any(x['path'].startswith(('ING docs/','Automatiseringsocialmedia/')) for x in a)
 pointer=json.loads(Path('p0e4/MASTER_STATE_LATEST.json').read_text());assert pointer['state_version']>=29
 assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
 print('PASS: asset references, cloud-byte nulls, collection separation, semantic unknowns, exclusion boundaries and master hash')
if __name__=='__main__':main()
