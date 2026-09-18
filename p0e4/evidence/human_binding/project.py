"""Additive V08 evidence projection using the frozen ledger/reducer.

An explicit user statement is preserved as evidence, not forged into an Ed25519
HUMAN_GATE_GRANTED event. No approval store, runtime gate or production state is written.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'p0e4'))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

OUT=Path(__file__).parent
PARENT=ROOT/'p0e4/evidence/review/UNCHAINED_MASTER_PROJECT_STATE_V07.json'
PARENT_SHA='db5e558f53d800b94303b4e74df74eee7dc57a8fb808c96b02086065abd47e79'
SOURCE_SHA='f6f84bff0b33e79f7921676fc9b52ef030cb6b839536b679b7c9a8bfebc4f159'
MASTER_SHA='0c6fdfc23439d195a2ff4aa4d809fd4621912d0023db5003bc7a6d972d0117b1'
STATEMENT='Ik bevestig dat mijn bestaande NITIN_FINAL_VIDEO_APPROVAL voor Aakhri Ishq betrekking heeft op AKI_SHOTSTACK_PRESENTATION_MASTER_V01.mp4 met SHA256 '+MASTER_SHA+'.'

def digest(raw): return hashlib.sha256(raw).hexdigest()
def ref(path): return {'path':str(path.relative_to(ROOT)),'sha256':digest(path.read_bytes())}
def check(ok,why):
    if not ok: raise ValueError(why)
def write(path,obj): path.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')

def facts(source,parent,prior,media):
    check(digest(source)==SOURCE_SHA,'source evidence hash mismatch')
    check(digest(parent)==PARENT_SHA,'V07 parent mismatch')
    text=source.decode()
    check(STATEMENT in text,'exact human binding absent')
    for s in ('Aakhri Ishq instrumental/backing: EIGEN PRODUCTIE',
              'Explicit composition/publication licence previously obtained: NEE',
              'Exact version previously tested/uploaded for Content ID: NEE'):
        check(s in text,'human rights fact absent')
    check(prior['gate']=='NITIN_FINAL_VIDEO_APPROVAL' and prior['decision']=='APPROVE'
          and prior['asset_id']=='production_master_v01'
          and prior['artifact_sha256']=='AKI_PRODUCTION_MASTER_V01_SHA_PENDING_LOCAL_RENDER',
          'existing decision differs')
    check(media['sha256']==MASTER_SHA and media['file_id']=='1ifHVAW1E0NjhN-eguBWUMNRekoemweAn'
          and media['name']=='AKI_SHOTSTACK_PRESENTATION_MASTER_V01.mp4','candidate identity differs')
    return {'source_sha256':SOURCE_SHA,'source_kind':'EXPLICIT_USER_SUPPLIED_FILE_IN_THIS_TASK',
        'speaker_as_supplied':'Nitin','decision_date_as_supplied':'2026-09-18','decision_time':'NOT_SUPPLIED',
        'registered_by':'codex','human_binding_statement':STATEMENT,
        'existing_approval':copy.deepcopy(prior),
        'binding':{'status':'RESOLVED_EXPLICIT_HUMAN_ATTESTATION','asset_sha256':MASTER_SHA,
                   'asset_name':media['name'],'file_id':media['file_id'],
                   'scope':'Binding of existing final-video decision only; not new approval'},
        'rights_facts':{'backing_master_origin':'EIGEN_PRODUCTIE_HUMAN_DECLARED',
                       'explicit_composition_publication_licence_previously_obtained':False,
                       'exact_version_content_id_previously_tested':False,
                       'third_party_backing_origin_question':'ANSWERED_BY_OWNER',
                       'composition_clearance':'NOT_ESTABLISHED','content_id_outcome':'UNKNOWN',
                       'independent_daw_stems_or_sample_licence_audit':'NOT_PERFORMED'},
        'new_approval_created':False,'runtime_signed_grant_created':False,
        'cryptographic_signature':'NOT_SUPPLIED_NOT_FABRICATED','rights_status':'RIGHTS_HOLD'}

def project(parent,ledger,source,prior,media):
    att=facts(source,parent,prior,media)
    derived=derive(ledger,keyring={})
    records=ledger.read_all()
    check(len(records)==3 and all(r['event_type']=='EVIDENCE_REGISTERED' for r in records),
          'only three evidence registrations accepted')
    payload=records[-1]['inputs']
    check(payload['human_evidence']==att,'evidence differs from source')
    check(set(payload)=={'human_evidence','evidence_refs','tested_sha','ingested_at','remaining'},'unexpected authority field')
    check(payload['remaining']==['RIGHTS_CLEARANCE','RELEASE_PACKAGE_REVIEW'],'cannot clear other gates')
    state=json.loads(parent)
    check(state['authorizations']['PUBLICATION_AUTHORIZED'] is False and
          state['authorizations']['PRODUCTION_DEPLOYMENT_AUTHORIZED'] is False and
          state['production_state']['first_real_poster']=='PAUSED_BY_NITIN','human gate changed')
    state['state_version']=10+derived['state_version']
    state['updated_at']=payload['ingested_at'];state['updated_by']='codex'
    state['p0e4']['human_binding_followup']=payload
    state['p0e4']['remaining']=[
        {'gate':'RIGHTS_CLEARANCE','reason':'Owner declares own backing and no prior explicit composition licence; campaign-specific composition/lyrics/platform coverage and Content ID outcome not established.'},
        {'gate':'RELEASE_PACKAGE_REVIEW','reason':'Exact-SHA derivative approval/lineage and final package decision not established; see current QC scope.'}]
    state['p0e4']['final_video_binding']=att['binding']
    state['p0e4']['rights_facts']=att['rights_facts']
    state['p0e4']['verdict']='BLOCKED_NOT_GREEN'
    state['state_lineage']={'parent_version':12,'parent_sha256':PARENT_SHA,
        'engineering_ledger_head_hash':derived['ledger_head_hash'],'engineering_transition_count':derived['state_version']}
    state['provenance'].append({'phase':'P0-E4','status':'HUMAN_BINDING_EVIDENCE_REGISTERED',
        'tested_sha':payload['tested_sha'],'evidence_refs':payload['evidence_refs']})
    return state

def main():
    inputs=json.loads((OUT/'PROJECTION_INPUTS.json').read_text())
    parent=PARENT.read_bytes();source=(OUT/'NITIN_SOURCE_REQUEST.txt').read_bytes()
    packet=json.loads((ROOT/'p0e4/evidence/resume/RELEASE_REVIEW_PACKET.json').read_text())
    prior=packet['approval_binding_request']['existing_decision']
    media=packet['approval_binding_request']['candidate_asset']
    att=facts(source,parent,prior,media)
    write(OUT/'HUMAN_ATTESTATION.json',att)
    payload={'human_evidence':att,'evidence_refs':[ref(OUT/n) for n in inputs['evidence_files']],
        'tested_sha':inputs['tested_sha'],'ingested_at':inputs['ingested_at'],
        'remaining':['RIGHTS_CLEARANCE','RELEASE_PACKAGE_REVIEW']}
    old=(ROOT/'p0e4/evidence/review/ENGINEERING_EVENT_LEDGER.jsonl').read_bytes()
    path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not path.exists(): path.write_bytes(old)
    check(path.read_bytes().startswith(old),'accepted ledger prefix changed')
    ledger=EventLedger(str(path))
    rows=ledger.read_all()
    if len(rows)==2:
        ledger.append(h.make_event('p0e4-v08-human-binding-evidence','EVIDENCE_REGISTERED',inputs['ingested_at'],'codex',inputs=payload))
    else: check(len(rows)==3 and rows[-1]['inputs']==payload,'immutable V08 evidence conflict')
    state=project(parent,ledger,source,prior,media)
    write(OUT/'UNCHAINED_MASTER_PROJECT_STATE_V08.json',state)
    print(json.dumps({'state_version':state['state_version'],'binding':att['binding']['status'],'rights':'RIGHTS_HOLD','release':'BLOCKED'}))
if __name__=='__main__':main()
