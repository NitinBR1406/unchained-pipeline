"""Filename hints never establish song identity, completion, rights or readiness."""
from copy import deepcopy
from pathlib import PurePosixPath
import re
from integration.contracts import canonical,digest,require,keys,sha,timestamp,verify_refs,text

STATES=('MUSIC_READY_VOCAL_PENDING','VOCALS_READY_VATSAL_PENDING','REVISION_REQUIRED','STEMS_REQUIRED','LIVE_READY','CATALOG_REACTIVATION_READY','RECREATION_2008_LYRICS_REVIEW','COVER_SWAP_CANDIDATE')
ROLES=('music','lyrics','vocals','tuning','mix','master','instrumental_backing','stems','midi_project','bpm','key','video_content')
BACKLOG=('Master Catalog & Song Lifecycle Engine','Catalog Reactivation Engine','Legacy Cover/Vocal Pending Workflow','2008 Recreation Workflow','Live Performance Library','Setlist Intelligence Engine','Historical Content→New Content Engine','governed Digital Twin Catalog Content','Song→Live→Revenue attribution')
FLAGS=dict(production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')


def stable(kind,value):return kind+':'+digest(canonical(value))[:24]


def path(value):
 text(value);p=PurePosixPath(value)
 require(not p.is_absolute() and '..' not in p.parts and str(p)==value and value!='.','unsafe/noncanonical relative path')
 return p


def reference(value):
 if type(value) is str:text(value)
 else:keys(value,'uri sha256');text(value['uri']);sha(value['sha256'])


def hints(name):
 """Candidate search clues only, not semantic evidence or role assignments."""
 n=name.lower();rules={'lyrics':r'lyric|tekst','vocals':r'vocal|vox','tuning':r'tun(e|ing)|melodyne','mix':r'mix','master':r'master','instrumental_backing':r'instrumental|backing|karaoke','stems':r'stem','midi_project':r'\.(mid|midi|logicx|als|flp|cpr|ptx)$','video_content':r'\.(mp4|mov|mkv|jpg|png)$','music':r'\.(wav|mp3|aif|aiff|m4a|flac)$','bpm':r'\bbpm\b','key':r'\bkey\b'}
 return sorted(k for k,v in rules.items() if re.search(v,n))


def validate_inventory(inv):
 keys(inv,'schema schema_version observed_at source_root scope_status folders')
 require(inv['schema']=='CATALOG_INVENTORY_V01' and type(inv['schema_version']) is int and inv['schema_version']==1,'inventory version')
 timestamp(inv['observed_at']);text(inv['source_root']);text(inv['scope_status'])
 require(type(inv['folders']) is list,'folders list required')
 seen=set();asset_seen={}
 for folder in inv['folders']:
  keys(folder,'relative_path entries source_ref complete');p=path(folder['relative_path']);reference(folder['source_ref'])
  require(folder['relative_path'] not in seen,'duplicate folder');seen.add(folder['relative_path'])
  require(type(folder['complete']) is bool and type(folder['entries']) is list,'inventory completeness type')
  for item in folder['entries']:
   keys(item,'relative_path kind bytes sha256 availability source_ref');ip=path(item['relative_path'])
   require(p in ip.parents,'entry outside folder');reference(item['source_ref']);text(item['kind']);text(item['availability'])
   require(item['bytes'] is None or type(item['bytes']) is int and item['bytes']>=0,'invalid bytes')
   if item['sha256'] is not None:sha(item['sha256'])
   if item['relative_path'] in asset_seen:
    require(asset_seen[item['relative_path']]==item['sha256'],'conflicting asset SHA')
    raise ValueError('duplicate asset path')
   asset_seen[item['relative_path']]=item['sha256']
 canonical(inv)


def compile_catalog(inv,observations=None,resolver=None):
 """Optional observations attest explicit facts with verified evidence bytes.

 Facts are never inferred from filenames. No approval, release or financial fact
 is accepted here. Qualified production attestations may route human work only.
 """
 validate_inventory(inv);observations=[] if observations is None else observations
 require(type(observations) is list,'observations list')
 obs={}
 for o in observations:
  keys(o,'relative_path field value evidence_refs');require(o['relative_path'] in {f['relative_path'] for f in inv['folders']},'unknown observation target')
  require(resolver is not None,'semantic evidence resolver required');verify_refs(o['evidence_refs'],resolver)
  field=o['field'];value=o['value']
  require(field in set(ROLES)|{'classification','song_title','production_status','next_action','action_owner'},'unsupported semantic field or approval escalation')
  if field in ROLES:require(value in ('UNKNOWN','PRESENT_VERIFIED','ABSENT_VERIFIED','READY_VERIFIED','REVISION_REQUIRED'),'role status')
  elif field=='classification':require(value in ('UNKNOWN','ORIGINAL','COVER','RECREATION_2008','COLLECTION'),'classification')
  elif field=='production_status':require(value in STATES or value=='UNKNOWN','lifecycle state')
  elif field=='action_owner':require(value in ('NITIN','VATSAL','UNKNOWN'),'owner')
  else:text(value)
  key=(o['relative_path'],field);require(key not in obs,'duplicate semantic observation');obs[key]=deepcopy(o)
 rows=[];gaps=[];queues={k:[] for k in ('NITIN_ACTION_QUEUE','VATSAL_ACTION_QUEUE','LIVE_READY_QUEUE','CATALOG_REACTIVATION_QUEUE')}
 for folder in sorted(inv['folders'],key=lambda x:x['relative_path']):
  rel=folder['relative_path'];sid=stable('catalog_source',[inv['source_root'],rel]);songid=stable('song',[inv['source_root'],rel])
  def fact(k,default='UNKNOWN'):return obs.get((rel,k),{}).get('value',default)
  roles={k:fact(k) for k in ROLES};classification=fact('classification');state=fact('production_status')
  # Production readiness is a separate explicit observation; never derived from presence.
  needs={'MUSIC_READY_VOCAL_PENDING':{'music':'READY_VERIFIED','vocals':'ABSENT_VERIFIED'},'VOCALS_READY_VATSAL_PENDING':{'vocals':'READY_VERIFIED'},'STEMS_REQUIRED':{'stems':'ABSENT_VERIFIED'},'LIVE_READY':{'instrumental_backing':'READY_VERIFIED','lyrics':'READY_VERIFIED'},'RECREATION_2008_LYRICS_REVIEW':{},'REVISION_REQUIRED':{},'CATALOG_REACTIVATION_READY':{'master':'READY_VERIFIED'},'COVER_SWAP_CANDIDATE':{}}
  if state!='UNKNOWN':
   require(all(roles[k]==v for k,v in needs[state].items()),'lifecycle prerequisites not evidenced')
   require(classification in ('ORIGINAL','COVER','RECREATION_2008'),'song identity/classification required')
   if state=='RECREATION_2008_LYRICS_REVIEW':require(classification=='RECREATION_2008','recreation classification conflict')
   if state=='COVER_SWAP_CANDIDATE':require(classification=='COVER','cover classification conflict')
   if state=='REVISION_REQUIRED':require('REVISION_REQUIRED' in roles.values(),'revision target missing')
  assets=[dict(asset_id=stable('asset',[inv['source_root'],e['relative_path']]),**deepcopy(e),candidate_role_hints=hints(e['relative_path']),verified_role='UNKNOWN') for e in sorted(folder['entries'],key=lambda x:x['relative_path'])]
  row=dict(catalog_source_id=sid,song_id=songid,folder_label=PurePosixPath(rel).name,song_title=fact('song_title'),classification=classification,relative_path=rel,inventory_complete=folder['complete'],source_ref=deepcopy(folder['source_ref']),verified_components=roles,assets=assets,production_status=state,next_action=fact('next_action','REVIEW_INVENTORY_AND_IDENTIFY_SONG_AND_COMPONENTS'),action_owner=fact('action_owner','NITIN'),live_performance_ready=state=='LIVE_READY',financial_stages={k:'UNKNOWN' for k in ('budget','quote','invoice','payment','revenue')},semantic_evidence=[deepcopy(o) for (r,k),o in sorted(obs.items()) if r==rel],attribution=dict(content_id=None,campaign_id=None,derivative_id=None,package_id=None,publication_id=None,experiment_id=None,hypothesis_id=None,song_id=songid,live_performance_id=None,setlist_id=None,analytics_id=None,audience_id=None,lead_id=None,booking_id=None,stream_id=None,ad_id=None,partnership_id=None,revenue_id=None,learning_id=None),publication_authorized=False)
  rows.append(row)
  gaps.append(dict(catalog_source_id=sid,unknown_components=[k for k,v in roles.items() if v=='UNKNOWN'],inventory_incomplete=not folder['complete'],unhashed_assets=[e['asset_id'] for e in assets if e['sha256'] is None],identity_unresolved=classification=='UNKNOWN' or row['song_title']=='UNKNOWN'))
  action=dict(catalog_source_id=sid,song_id=songid,next_action=row['next_action'],action_owner=row['action_owner'],production_status=state,source_ref=deepcopy(folder['source_ref']))
  if row['action_owner'] in ('NITIN','VATSAL'):queues[row['action_owner']+'_ACTION_QUEUE'].append(action)
  if state=='LIVE_READY':queues['LIVE_READY_QUEUE'].append(action)
  if state=='CATALOG_REACTIVATION_READY':queues['CATALOG_REACTIVATION_QUEUE'].append(action)
 base=dict(schema_version=1,inventory_sha256=digest(canonical(inv)),observed_at=inv['observed_at'],**FLAGS)
 out={'MASTER_CATALOG_V01':dict(base,schema='MASTER_CATALOG_V01',records=rows),'CATALOG_GAP_REPORT_V01':dict(base,schema='CATALOG_GAP_REPORT_V01',records=gaps)}
 out.update({k:dict(base,schema=k,records=v) for k,v in queues.items()})
 out['PRODUCTION_SHEET_VIEW_V01']=dict(base,schema='PRODUCTION_SHEET_VIEW_V01',mode='OFFLINE_VIEW_NO_SHEET_MUTATION',rows=[{'SONG_ID':r['song_id'],'FOLDER_LABEL':r['folder_label'],'SONG_TITLE':r['song_title'],'NEXT_ACTION':r['next_action'],'ACTION_OWNER':r['action_owner'],'PRODUCTION_STATUS':r['production_status'],'FINANCIAL_STAGES':r['financial_stages'],'ASSET_IDS':[a['asset_id'] for a in r['assets']],'STEMS':r['verified_components']['stems'],'LIVE_PERFORMANCE_READY':r['live_performance_ready'],'ATTRIBUTION':r['attribution']} for r in rows])
 out['FACTORY_EXPANSION_BACKLOG_V01']=dict(base,schema='FACTORY_EXPANSION_BACKLOG_V01',lifecycle_states=list(STATES),engines=[dict(engine_id=stable('engine',x),name=x,status='AUTHORIZED_BACKLOG_NOT_IMPLEMENTED') for x in BACKLOG])
 return out
