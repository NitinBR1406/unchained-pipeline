"""Apply explicit batch rows only. Total mismatches stay visible, never corrected by guessing."""
from copy import deepcopy

def apply_batch(review, event):
    result=deepcopy(review);rows={r['candidate_id']:r for r in result['rows']}
    before=deepcopy(rows);seen=set();conflicts=[]
    for item in event['items']:
        cid=item['candidate_id']
        if cid in seen:raise ValueError('Duplicate candidate ID')
        seen.add(cid)
        if cid not in rows or rows[cid]['path']!=item['path'] or item['path'].strip()!=item['input_name']:
            raise ValueError('Candidate ID/path/name mismatch')
        r=rows[cid]
        if r['block']=='nitin_2008_children':raise ValueError('NITIN 2008 excluded from batch readiness')
        expected=event['code_meanings'].get(item['code'])
        if expected!={'MUSIC_READY':'YES','VOCALS_READY':{'jj':'YES','jn':'NO'}.get(item['code'])}:raise ValueError('Invalid code meaning')
        fields=item['set_fields']
        if set(fields)-{'MUSIC_READY','VOCALS_READY','TYPE'} or any(fields.get(k)!=v for k,v in expected.items()):raise ValueError('Unspecified or inconsistent fields')
        for k,v in fields.items():
            if v not in result['allowed_values'][k]:raise ValueError('Invalid enum')
            if k=='TYPE' and r[k] not in ('UNKNOWN',v):
                conflicts.append({'candidate_id':cid,'field':k,'existing':r[k],'requested':v});continue
            r[k]=v
        r['semantic_evidence_event_id']=event['event_id']
        r['question']='Music/vocals answers recorded from Nitin; other fields remain unconfirmed. Control totals await reconciliation.'
    regular=[i for i in event['items'] if i['batch'].startswith('BATCH')]
    mash=[i for i in event['items'] if i['batch']=='MASHUP/MEDLEY ITEMS']
    count=lambda items,k,v:sum(rows[i['candidate_id']][k]==v for i in items)
    actual={'regular_items':len(regular),'regular_music_yes':count(regular,'MUSIC_READY','YES'),'regular_vocals_yes':count(regular,'VOCALS_READY','YES'),'regular_vocals_no':count(regular,'VOCALS_READY','NO'),'mashup_medley_items':len(mash),'mashup_medley_music_yes':count(mash,'MUSIC_READY','YES'),'mashup_medley_vocals_no':count(mash,'VOCALS_READY','NO'),'total_items':len(seen),'vocal_pending':count(event['items'],'VOCALS_READY','NO')}
    mismatches={k:{'expected':v,'observed':actual[k]} for k,v in event['expected_control_totals'].items() if actual[k]!=v}
    for cid,r in rows.items():
        if cid not in seen:
            if r!=before[cid]:raise ValueError('Unrelated row changed')
        else:
            for k,v in before[cid].items():
                if k not in {'MUSIC_READY','VOCALS_READY','TYPE','question','semantic_evidence_event_id'} and r[k]!=v:raise ValueError('Unrelated field changed')
    receipt={'schema_version':1,'event_id':event['event_id'],'candidate_id_path_validation':'PASS','explicit_fields_validation':'PASS','unrelated_fields_and_rows_unchanged':'PASS','nitin_2008_unchanged':'PASS','expected_control_totals':event['expected_control_totals'],'observed_control_totals':actual,'control_total_mismatches':mismatches,'type_conflicts':conflicts,'status':'WAITING_FOR_NITIN_CONTROL_TOTAL_RECONCILIATION' if mismatches or conflicts else 'PASS','row_assignments_applied':len(seen),'all_checks_passed':not(mismatches or conflicts)}
    result['batch_semantic_validation']=receipt
    result['status']=receipt['status']
    result['counts']['batch_readiness_confirmed']=len(seen)
    q=next(q for q in result['identity_questions'] if q['id']=='CHUNAR')
    q.update(question='Historical Songs voor 2022/Chunar retained separately from Chunar 2025; no merge authorized.',answer='KEEP_SEPARATE_HISTORICAL_VERSION',evidence_event_id=event['event_id'])
    result['identity_questions'].insert(0,{'id':'BATCH_CONTROL_TOTALS','question':'Explicit answers produce 36 regular jj and 27 regular jn, plus 4 mashup/medley jn: 31 vocal-pending. Confirm row-based totals or specify four jn-to-jj corrections; no answers changed to force totals.','answer':'UNKNOWN','evidence_event_id':event['event_id']})
    result['historical_grouping_constraints']={'Songs voor 2022':'PRESERVE','Songs voor 2022/Chunar':'KEEP_SEPARATE_FROM_CHUNAR_2025_WITHOUT_EXPLICIT_IDENTITY_EVIDENCE'}
    queues={}
    for name,vocal in [('NITIN_VOCAL_QUEUE_V01','NO'),('MUSIC_AND_VOCALS_READY_V01','YES')]:
        entries=[deepcopy(r) for r in result['rows'] if r['MUSIC_READY']=='YES' and r['VOCALS_READY']==vocal]
        queues[name]={'artifact':name,'predicate':{'MUSIC_READY':'YES','VOCALS_READY':vocal},'count':len(entries),'status':'DERIVED_FROM_EXPLICIT_ROWS_CONTROL_TOTALS_UNRECONCILED' if mismatches else 'DERIVED_FROM_CONFIRMED_FIELDS','rows':entries,'not_established':['LYRICS_READY','MIX_MASTER_READY','STEMS_READY','LIVE_READY','RIGHTS_CLEARANCE','PUBLISH_READY'],'publication_authorized':False}
    return result,receipt,queues
