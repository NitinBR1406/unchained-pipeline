"""Offline projection of frozen discovery; never accesses iCloud or production."""
import csv, hashlib, json
try:
    from .batch_semantics import apply_batch
except ImportError:
    from batch_semantics import apply_batch
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT/'p0e4/evidence/catalog_discovery_v02'
OUT = ROOT/'p0e4/evidence/catalog_minimal_review_v01'
def read(n): return json.loads((SRC/(n+'.json')).read_text())
def write(n, v): (OUT/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def build():
    OUT.mkdir(exist_ok=True)
    for line in (SRC/'SHA256SUMS.txt').read_text().splitlines():
        sha,name=line.split(maxsplit=1); p=SRC/name.lstrip('*')
        if not p.exists(): p=ROOT/name.lstrip('*')
        assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
    pointer=json.loads((ROOT/'p0e4/MASTER_STATE_LATEST.json').read_text())
    assert pointer['state_version']>=29
    assert hashlib.sha256((ROOT/pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
    candidates=read('SONG_FOLDER_CANDIDATES'); assets=read('TECHNICAL_ASSET_INVENTORY'); byid={a['asset_id']:a for a in assets}
    allowed={'TYPE':['UNKNOWN','ORIGINAL','COVER','ORIGINAL_RECREATION','RECREATION_OTHER','MASHUP','MEDLEY','REFERENCE','INSTRUMENTAL','OTHER','N/A']}
    for f in ['MUSIC_READY','LYRICS_READY','VOCALS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY']:allowed[f]=['UNKNOWN','YES','NO','N/A']
    allowed.update(PRIORITY=['UNKNOWN','HIGH','MEDIUM','LOW','BACKLOG','N/A'],NEXT_ACTION=['UNKNOWN','CONFIRM_IDENTITY','REVIEW_REFERENCE','WRITE_MUSIC','WRITE_LYRICS','RECORD_VOCALS','ARRANGE','MIX_MASTER','REVISE','REHEARSE','REVIEW_WITH_VATSAL','NO_ACTION','OTHER','N/A'],ACTION_OWNER=['UNKNOWN','NITIN','VATSAL','NITIN_AND_VATSAL','OTHER','N/A'])
    mixed=['Downloads/Final videos ','Downloads/wetransfer_apna-bana-le-mp4_2023-10-03_1015','Downloads/wetransfer_apna-bana-le-mp4_2023-10-03_1015 2','Downloads/wetransfer_bekhayali-mp4_2023-11-22_2238']
    categories={k:[] for k in ['clear_song_folders','nitin_2008_children','mashup_medley_named_folders','collections_containers','non_song_admin','ambiguous_identity']}
    rows=[]; dispositions=[]
    for c in candidates:
        path=c['path']; reason=''; dest=None
        if path=='Downloads/Stater':
            dest='non_song_admin'; reason='Work/admin hierarchy; one embedded media asset is retained separately, not proof that the parent is a song.'
        elif path in mixed:
            dest='collections_containers'; reason='Multiple distinct song-labelled assets; not one song.'
        elif path.startswith('Downloads/'):
            dest='ambiguous_identity';reason='Possible media/version folder for an existing song; identity mapping requires confirmation, no independent readiness row.'
        elif path in ['Intro beat','Songs voor 2022/Chunar']:
            dest='ambiguous_identity';reason='Confirm whether separate item or existing-song arrangement/version before readiness review.'
        elif path.startswith('NITIN 2008/'):
            dest='nitin_2008_children'
        elif c['classification']=='MASHUP_MEDLEY_CANDIDATE':dest='mashup_medley_named_folders'
        else:dest='clear_song_folders'
        categories[dest].append(c['candidate_id'])
        dispositions.append({'candidate_id':c['candidate_id'],'path':path,'category':dest,'reason':reason or 'Song-oriented file grouping; semantic type and readiness unproven.'})
        if path.startswith('Downloads/'):continue
        row={'candidate_id':c['candidate_id'],'name':c['label'],'path':path,'block':dest,'identity_confirmed':'UNKNOWN',**{f:'UNKNOWN' for f in allowed},'asset_count':len(c['asset_ids']),'question':'Confirm/correct identity and only the semantic facts you know.'}
        if dest=='nitin_2008_children':row['question']='Is this one of the eight original-song recreations? Confirm/correct title and TYPE. No ownership or readiness inferred.'
        if dest=='ambiguous_identity':row['question']=reason
        rows.append(row)
    links=[];duplicate_only=[];removed=set(); owners={}
    for c in candidates:
        if not c['path'].startswith('Downloads/'):
            for aid in c['asset_ids']: owners.setdefault(byid[aid]['path'],[]).append(c['candidate_id'])
    for g in read('EXACT_BYTE_DUPLICATES')['groups']:
        targets={i for p in g['paths'] for i in owners.get(p,[])}
        loose=[x for x in read('UNASSIGNED_MEDIA_CANDIDATES') if x['path'] in g['paths']]
        if len(targets)==1:
            for x in loose:
                links.append({'asset_path':x['path'],'candidate_id':next(iter(targets)),'sha256':g['sha256'],'basis':'EXACT_BYTE_EQUALITY_TO_ASSET_ALREADY_IN_FOLDER','semantic_identity_or_readiness_inferred':False});removed.add(x['candidate_id'])
        elif not targets and loose:
            duplicate_only.append({'representative':loose[0]['path'],'alias_paths':[x['path'] for x in loose[1:]],'sha256':g['sha256'],'song_identity':'UNKNOWN'})
            removed.update(x['candidate_id'] for x in loose[1:])
    unassigned=[x for x in read('UNASSIGNED_MEDIA_CANDIDATES') if x['candidate_id'] not in removed]
    admin=next(c for c in candidates if c['path']=='Downloads/Stater')
    retained_admin_media=[byid[x] for x in admin['asset_ids']]
    questions=[
      {'id':'N2008','names':[r['name'] for r in rows if r['block']=='nitin_2008_children'],'question':'Confirm/correct these eight identities as the eight original-song recreations. Batch TYPE=ORIGINAL_RECREATION is available only after your explicit confirmation. Readiness is a separate decision.','answer':'UNKNOWN'},
      {'id':'APNA','paths':[c['path'] for c in candidates if c['path'].startswith('Downloads/') and ('Apna' in c['path'] or 'apna' in c['path'])],'question':'Apna Bana Levideo’s: associate with Apna bana le? The two identically named transfer bundles contain four songs each. Confirm per-song links; equal names/sizes do not prove duplicate bytes.','answer':'UNKNOWN'},
      {'id':'HUA','paths':[c['path'] for c in candidates if c['path'].startswith('Downloads/') and ('HUA' in c['path'] or 'hua-main' in c['path'])],'question':'Associate these video folders with Hua Mein, or correct?','answer':'UNKNOWN'},
      {'id':'OTHER_DOWNLOADS','paths':[c['path'] for c in candidates if c['path'].startswith('Downloads/') and any(s in c['path'] for s in ['Baarish videos','phir-mohabbat','saari-duniya'])],'question':'Confirm associations: Baarish videos -> which Baarish song? phir-mohabbat -> Phil Moh? saari-duniya -> Saari Duniya? These are suggestions only.','answer':'UNKNOWN'},
      {'id':'MIXED_MEDIA','paths':mixed,'question':'Mixed video bundles are not songs. Confirm relevant per-asset links only; no separate container readiness required.','answer':'UNKNOWN'},
      {'id':'INTRO','paths':['Intro beat','Khairiyat'],'question':'Is Intro beat an arrangement asset for Khairiyat or a separate catalog item?','answer':'UNKNOWN'},
      {'id':'CHUNAR','paths':['Songs voor 2022/Chunar','Chunar 2025'],'question':'One song with different versions, or separate catalog items? Do not answer readiness twice if one song.','answer':'UNKNOWN'},
      {'id':'LOOSE_MEDIA','question':'Unassigned media is held outside the song review. Identify only items you want in the catalog; no need to label every download. Unresolved items remain explicitly UNKNOWN.','answer':'UNKNOWN'}]
    counts={'source_candidates':len(candidates),'semantic_rows':len(rows),'immediate_semantic_rows':sum(r['block']!='ambiguous_identity' for r in rows),'conditional_identity_rows':sum(r['block']=='ambiguous_identity' for r in rows),'download_candidates_removed_from_readiness':11,'admin_candidates_excluded':1,'additional_mixed_containers':4,'download_media_folders_identity_first':6,'exact_hash_links':len(links),'redundant_unassigned_aliases':sum(len(g['alias_paths']) for g in duplicate_only),'remaining_original_unassigned_representatives':len(unassigned),'admin_embedded_media_held_separately':len(retained_admin_media)}
    result={'artifact':'NITIN_MINIMAL_SEMANTIC_REVIEW_V01','status':'WAITING_FOR_NITIN','source':'CATALOG_DISCOVERY_V02','parent_master_state_version':pointer['state_version'],'counts':counts,'allowed_values':allowed,'rows':rows,'identity_questions':questions,'rules':['All semantic defaults UNKNOWN. Category is routing, not TYPE.','Batch answers apply only to explicitly selected rows.','Final-video approval is not a song-wide music/lyrics/vocals/mix/live approval.','No MASTER_CATALOG_V01 until received review. No publication authorization.'],'nitin_2008_identity_status':'AWAITING_CONFIRMATION_AS_EIGHT_ORIGINAL_SONG_RECREATIONS'}
    assert all(r[f]=='UNKNOWN' for r in rows for f in allowed)
    event_path=ROOT/'p0e4/evidence/catalog_semantic_events/NITIN_2008_SEMANTIC_CONFIRMATION_V01.json'
    if event_path.exists():
        event=json.loads(event_path.read_text())
        expected={r['candidate_id']:r['path'] for r in rows if r['block']=='nitin_2008_children'}
        assert {r['candidate_id']:r['path'] for r in event['subject_rows']}==expected
        assert event['set_fields']=={'identity_confirmed':'YES','TYPE':'ORIGINAL_RECREATION','NEXT_ACTION':'REVIEW_WITH_VATSAL','ACTION_OWNER':'NITIN_AND_VATSAL'}
        for row in rows:
            if row['candidate_id'] in expected:
                row.update(event['set_fields'])
                row['semantic_evidence_event_id']=event['event_id']
                row['question']='Identity and original-recreation TYPE confirmed by Nitin. Readiness and priority remain UNKNOWN.'
        q=next(q for q in questions if q['id']=='N2008')
        q.update(question='Eight identities and TYPE confirmed by Nitin; no further identity confirmation required.',answer='YES — all eight are the existing original songs from approximately 2008 in the Vatsal recreation package.',evidence_event_id=event['event_id'])
        result['nitin_2008_identity_status']='CONFIRMED_BY_NITIN'
        result['status']='PARTIAL_REVIEW_RECEIVED_REMAINING_FIELDS_UNKNOWN'
        result['applied_semantic_events']=[{'event_id':event['event_id'],'path':str(event_path.relative_to(ROOT)),'sha256':hashlib.sha256(event_path.read_bytes()).hexdigest()}]
        result['counts']['nitin_2008_identities_confirmed']=8
        result['counts']['nitin_2008_readiness_confirmed']=0
    batch_path=ROOT/'p0e4/evidence/catalog_semantic_events/NITIN_BATCH_1_5_MASHUPS_SEMANTIC_CONFIRMATION_V01.json'
    if batch_path.exists():
        result,receipt,queues=apply_batch(result,json.loads(batch_path.read_text()))
        rows=result['rows'];counts=result['counts']
        result['applied_semantic_events'].append({'event_id':receipt['event_id'],'path':str(batch_path.relative_to(ROOT)),'sha256':hashlib.sha256(batch_path.read_bytes()).hexdigest()})
        write('BATCH_SEMANTIC_VALIDATION_RECEIPT',receipt)
        for name,queue in queues.items():
            write(name,queue)
            export_fields=['candidate_id','name','path','TYPE','MUSIC_READY','VOCALS_READY','LYRICS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY','PRIORITY','NEXT_ACTION','ACTION_OWNER']
            with (OUT/(name+'.csv')).open('w',newline='') as stream:
                writer=csv.DictWriter(stream,export_fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(queue['rows'])
    write('NITIN_MINIMAL_SEMANTIC_REVIEW_V01',result)
    write('REVIEW_REDUCTION_AUDIT',{'counts':counts,'candidate_dispositions':dispositions,'categories':categories,'original_exclusions':read('NON_SONG_EXCLUSIONS'),'existing_containers':read('COLLECTIONS_AND_CHILDREN'),'exact_hash_links':links,'unassigned_duplicate_alias_groups':duplicate_only,'unassigned_representatives':unassigned,'admin_embedded_media_retained':retained_admin_media,'limitations':['No identity merges on names or sizes. No new iCloud reads.','75 immediate semantic rows remain because readiness is not technically provable.','Two conditional rows and six media folders need identity decisions; no candidates silently dropped.']})
    fields=['candidate_id','name','path','block','identity_confirmed',*allowed]
    with (OUT/'NITIN_MINIMAL_SEMANTIC_REVIEW_V01.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)
    assert len(dispositions)==88 and len({x['candidate_id'] for x in dispositions})==88
    assert len(rows)==77 and counts['immediate_semantic_rows']==75 and len(links)==2
    assert sum(r['block']=='nitin_2008_children' for r in rows)==8
    assert all(r[f]=='UNKNOWN' for r in rows for f in ['LYRICS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY','PRIORITY'])
    next_ready={'status':'WAITING_FOR_NITIN','ready_nonhuman_count':0,'task':'Receive remaining semantic review','MASTER_CATALOG_V01_created':False,'publication_authorized':False,'production_mutation':False}
    if batch_path.exists():
        next_ready.update(status='WAITING_FOR_NITIN_CONTROL_TOTAL_RECONCILIATION',task='Confirm explicit-row totals 36 ready / 31 vocal-pending, or name four regular jn-to-jj corrections.',remaining_questions=[{'priority':1,'question':'Resolve row answers versus stated 40/23 regular totals; do not resend the whole batch.'},{'priority':2,'question':'For the next selected vocal session only, specify priority and owner if needed. Other unknown semantics may remain UNKNOWN.'},{'priority':3,'question':'When relevant, confirm Intro beat association and remaining download identities; Chunar stays separate and NITIN 2008 identity is already confirmed.'}],unconfirmed_semantics=['LYRICS_READY','MIX_MASTER_READY','REVISION_REQUIRED','LIVE_READY','PRIORITY'],untouched_readiness_rows=['Aakhri Ishq','Intro beat','NITIN 2008 (8 children)'])
    write('NEXT_READY',next_ready)
    template=(ROOT/'p0e4/catalog/minimal_review_template.html').read_text()
    embedded=json.dumps(result,ensure_ascii=False).replace('<','\\u003c')
    (OUT/'NITIN_MINIMAL_SEMANTIC_REVIEW_V01.html').write_text(template.replace('__DATA__',embedded))
    print(json.dumps(counts,indent=2))
if __name__=='__main__':build()
