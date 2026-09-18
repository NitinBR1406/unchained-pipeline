"""Offline review evidence projection only. No runtime, authority, or media mutations.
Run from repository root with the existing isolated P0-E4 Python environment.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'p0e4'))
import handoff as h
from control_plane.ledger import EventLedger
from control_loop.state_model import derive

OUT = Path(__file__).parent
BASE = ROOT/'p0e4/evidence/resume'
TESTED = '7d4738394b5bb433dd9f9023460b10d3f44b19c1'
PARENT_HASH = '416437c4f30685bf4772ca09ed702679715a7c7dcc1596eeaa149c2a78fa2311'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, obj):
    (OUT/name).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
def main():
    parent = BASE/'state/UNCHAINED_MASTER_PROJECT_STATE_V06.json'
    assert sha(parent)==PARENT_HASH
    state=json.loads(parent.read_text())
    packet=json.loads((BASE/'RELEASE_REVIEW_PACKET.json').read_text())
    media=json.loads((BASE/'MEDIA_QC.json').read_text())
    campaign=json.loads((ROOT/'campaigns/aakhri-ishq/campaign.json').read_text())
    regression=json.loads((OUT/'REGRESSION.json').read_text())
    assert regression['tested_sha']==TESTED
    assert len(regression['suites'])==37 and all(s['exit_code']==0 for s in regression['suites'])
    integrity=[]
    for manifest in (ROOT/'p0e4/evidence/SHA256SUMS.txt',BASE/'SHA256SUMS.txt'):
        for line in manifest.read_text().splitlines():
            digest, path=line.split(maxsplit=1)
            target=manifest.parent/path.strip().lstrip('*')
            passed=target.exists() and sha(target)==digest
            integrity.append({'manifest':str(manifest.relative_to(ROOT)), 'path':str(target.relative_to(ROOT)), 'sha256':digest,'pass':passed})
    assert all(x['pass'] for x in integrity)
    frozen_changes=subprocess.check_output(['git','diff',h.FREEZE,TESTED,'--name-only'],cwd=ROOT,text=True).splitlines()
    assert all(p.startswith('p0e4/') or p=='.github/workflows/p0e4-integration.yml' for p in frozen_changes)
    assets={a['file_id']:a for a in media['assets']}
    assert len(assets)==4
    assert len(packet['packages'])==7
    assert [p['platform'] for p in packet['packages']]==campaign['platform_targets']
    checks=[]
    for p in packet['packages']:
        proposed=p['selected_asset_proposal']; a=assets[proposed['file_id']]
        assert all(proposed[k]==a[k] for k in ('sha256','size_bytes','name'))
        assert proposed['duration']==a['probe']['duration']
        assert proposed in p['asset_candidates']
        assert a['technical_decode_pass'] and a['full_av_decode_exit_code']==0 and a['bytes_unchanged']
        assert all(p.get(k) for k in ('title','caption','description','hashtags','cta'))
        assert p['rights_status']=='RIGHTS_HOLD' and p['selected_asset'] is None and p['publish_datetime'] is None
        checks.append({'platform':p['platform'],'asset_id':proposed['file_id'],'sha256':proposed['sha256'],
            'identity_and_metadata_qc':'PASS','decode_evidence':'REUSED_HASH_VERIFIED_PRIOR_FULL_DECODE',
            'title_characters':len(p['title']),'caption_characters':len(p['caption']),
            'lineage':'MASTER_IDENTITY_OBSERVED_APPROVAL_UNBOUND' if p['platform']=='youtube_hero' else 'NIET_AANGETOOND',
            'platform_current_policy_certification':'NOT_PERFORMED', 'creative_approval_inferred':False})
    report={'tested_sha':TESTED,'regression_suites_passed':37,'prior_manifest_entries_verified':integrity,
        'frozen_components_changed':False,'diff_from_frozen':frozen_changes,'package_checks':checks,
        'approval_binding':{'status':'NITIN_GATE_REQUIRED','approval_created':False,
            'reason':'Placeholder lacks an exact byte identity. Matching name, timing, render config and Drive identity do not authorize replacing the decision hash. No authoritative prior binding located in inspected evidence.'},
        'rights':{'status':'RIGHTS_HOLD','clearance_evidence_found':False,
            'required_evidence':['composition/publisher permission and platform scope','backing-master provenance and permission','Content ID expectation supported by evidence'],
            'search_scope':'Repository campaign/evidence plus DRIVE_DISCOVERY.json; not a universal absence claim.'},
        'lineage':{'derivative_parent_sha_and_cut_receipt':'NIET_AANGETOOND',
            'master_duration_seconds_observed':208.42,'campaign_duration_seconds':208.625,
            'duration_delta_seconds':-0.205,'duration_delta_disposition':'Observation only; does not establish a defect or authorize rendering.'},
        'independent_qc':{'gemini':'NOT_AVAILABLE_IN_CALLABLE_TOOLS','claude':'NOT_AVAILABLE_IN_CALLABLE_TOOLS',
            'pending':'Exact-SHA visual/audio review of four unique assets: LOOK MATCH/DEVIATION against approved baseline, motion/lip-sync, crop/text safe areas, cut continuity and audio boundaries. Persist per-asset verdict with reviewer and source hashes. Do not grant human approval.',
            'human_message_relay_required':False,'dispatch_performed':False},
        'resolved':['Seven proposals each checked against campaign targets, hashed media evidence and candidate lists','Prior P0-E4 evidence manifests revalidated','Current frozen-source diff and regression verified','Human review reduced to four unique assets and one platform/copy decision matrix'],
        'remaining':['NITIN_FINAL_VIDEO_APPROVAL_SHA_BINDING','RIGHTS_CLEARANCE','RELEASE_PACKAGE_REVIEW'],
        'publish_ready':False,'publication_authorized':False,'production_deployment_authorized':False,
        'first_real_poster':'PAUSED_BY_NITIN','new_authoritative_integration_runs':0,
        'limits':'No new media download/decode or audiovisual creative review; previous full-decode evidence reused with manifest integrity. Live integration remains run 35325952509 on 41230edcaac11218ec7576530ce79065522a42f2; this review packet was not exercised by that run.'}
    write('REVIEW_QC.json',report)
    lines=['# Aakhri Ishq — concrete review, geen publicatietoestemming','',
        'Status: BLOCKED. Vier unieke bestanden, zeven voorstellen. Technische metadata en bestaande decode-evidence gecontroleerd; creatieve goedkeuring en rechten niet afgeleid.','',
        '## Minimale besluiten / bewijs','',
        '1. Bevestig uitsluitend of de bestaande final-video-goedkeuring bij de onderstaande exacte presentatie-master hoort. Geen nieuwe goedkeuring wordt automatisch geregistreerd.',
        '2. Lever/verwijs naar bestaand rechtenbewijs voor compositie, backing-master en toegestaan platformgebruik, plus onderbouwde Content ID-verwachting. Zonder bewijs blijft RIGHTS_HOLD.',
        '3. Accepteer of wijzig de vier assets en de zeven onderstaande copy/platformvoorstellen. Derivative-herkomst en bestaande goedkeuringsscope zijn NIET AANGETOOND. Een naam of technische PASS bewijst deze niet.',
        '', 'Pas na deze voorwaarden kan PUBLISH_READY worden beoordeeld. Daarna volgt afzonderlijk NITIN_PUBLISH_APPROVAL en STOP vóór publicatie. Geen planning is vastgelegd.','',
        '## Vier unieke assets','']
    for a in packet['verified_assets']:
        lines.extend([f"- [{a['name']}](https://drive.google.com/file/d/{a['file_id']}/view) — {a['duration']:.2f} s; SHA256 `{a['sha256']}`."])
    lines.extend(['','## Zeven voorstellen','', '| Platform | Asset | Titel | Caption |','|---|---|---|---|'])
    for p in packet['packages']:
        lines.append(f"| {p['platform']} | {p['selected_asset_proposal']['name']} | {p['title'].replace('|', '&#124;')} | {p['caption']} |")
    lines.extend(['','CTA voor alle voorstellen: **Welk moment raakt jou?**',
        'Hashtags: **#AakhriIshq #UnchainedNitin #CoverPerformance**.',
        'De exacte descriptions en alle metadata blijven ter review in ../resume/RELEASE_REVIEW_PACKET.json; niets is geselecteerd of ingepland.',
        '', '## Resterende onafhankelijke QC', '', report['independent_qc']['pending'],
        'Gemini/Claude zijn niet beschikbaar als callable integration in deze sessie. Er is geen QC-aanvraag verstuurd en Nitin hoeft geen AI-berichten door te geven. Een volgende gekoppelde agent kan dit dossier rechtstreeks gebruiken.',
        '', 'De circa 0,205 seconde afwijking tussen campagneduur en gemeten masterduur is vastgelegd als observatie, zonder her-render of defectclaim.',
        'De oude Drive master-status van 5 september beschrijft een andere clean-base-versie en vervangt de latere repositorybeslissing niet.'])
    (OUT/'HUMAN_REVIEW.md').write_text('\n'.join(lines)+'\n')
    refs=[{'path':str((OUT/n).relative_to(ROOT)),'sha256':sha(OUT/n)} for n in ('REVIEW_QC.json','HUMAN_REVIEW.md','REGRESSION.json','DRIVE_DISCOVERY.json','DRIVE_MASTER_STATUS_REFERENCE.md')]
    summary={'tested_sha':TESTED,'verdict':'BLOCKED_NOT_GREEN','evidence_refs':refs,'remaining':report['remaining']}
    old=(BASE/'state/ENGINEERING_EVENT_LEDGER.jsonl').read_bytes()
    ledger_path=OUT/'ENGINEERING_EVENT_LEDGER.jsonl'
    if not ledger_path.exists(): ledger_path.write_bytes(old)
    assert ledger_path.read_bytes().startswith(old)
    ledger=EventLedger(str(ledger_path))
    event=h.make_event('p0e4-v07-review-evidence','EVIDENCE_REGISTERED','2026-09-18T09:29:09Z','codex',inputs=summary)
    records=ledger.read_all()
    if len(records)==1: ledger.append(event)
    else:
        assert len(records)==2 and records[-1]['inputs']==summary
    derived=derive(ledger,keyring={})
    assert derived['state_version']==2
    new=copy.deepcopy(state)
    new.update(state_version=12,updated_at='2026-09-18T09:29:09Z',updated_by='codex')
    new['p0e4']['review_followup']=summary
    new['state_lineage']={'parent_version':11,'parent_sha256':PARENT_HASH,
        'engineering_ledger_head_hash':derived['ledger_head_hash'],'engineering_transition_count':2}
    new['provenance'].append({'phase':'P0-E4','status':'REVIEW_EVIDENCE_REGISTERED_BLOCKED',**summary})
    assert new['authorizations']==state['authorizations'] and new['production_state']==state['production_state']
    assert new['current_release']==state['current_release']
    write('UNCHAINED_MASTER_PROJECT_STATE_V07.json',new)
    print(json.dumps({'packages':len(checks),'manifest_entries':len(integrity),'state_version':12,'release':'BLOCKED'}))
if __name__=='__main__': main()
