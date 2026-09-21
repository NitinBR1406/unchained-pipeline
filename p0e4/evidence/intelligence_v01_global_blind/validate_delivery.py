"""Offline delivery integrity and consistency checks; does not certify source claims."""
from pathlib import Path
import json, hashlib, re, subprocess, sys

root=Path(__file__).resolve().parent
out=root/'SYNTHESIS'
gate=json.loads(subprocess.check_output([sys.executable,str(root/'verify_freezes.py')]))
assert gate['synthesis_allowed']
all_json=list(root.rglob('*.json'))
for file in all_json: json.loads(file.read_text())
def read(name): return json.loads((out/name).read_text())
registry={x['reference_id']:x for x in read('REFERENCE_REGISTRY_V01.json')['references']}
assert len(registry)==32
zones=read('TOP_REFERENCE_ZONES_V01.json')['zones']
assert len(zones)==10 and len({z['zone_id'] for z in zones})==10
for z in zones:
    assert z['rank'] is None and z['recommended_absolute_key'] is None
    assert len(set(z['reference_ids']))==z['supporting_examples_n']
    assert z['independent_tests_of_zone_effect_n']==0
    for rid in z['reference_ids']:
        r=registry[rid]
        assert r['canonical_recording_key'] is None and r['canonical_recording_bpm'] is None
        if z['proposed_bpm_range']:
            lo,hi=z['proposed_bpm_range']; assert lo<=r['reported_bpm']<=hi,(z['zone_id'],rid)
        expected=z['proposed_mode'].removesuffix('_candidate')
        assert r['reported_mode']==expected,(z['zone_id'],rid)
engine=read('SONG_SUCCESS_INTELLIGENCE_ENGINE_V01.json')
for name in ['SUCCESS_SIGNAL_SCORE','REFERENCE_MATCH_SCORE','NITIN_FIT_SCORE','EXPECTED_RETENTION_PROFILE']:
    assert engine['outputs'][name]['value'] is None
assert engine['governance']=={'PRODUCTION_DEPLOYMENT_AUTHORIZED':False,'PUBLICATION_AUTHORIZED':False,'FIRST_REAL_POSTER':'PAUSED_BY_NITIN','writes_to_operational_state':False}
assert read('VOCAL_KEY_OPTIMIZER_V01.json')['NITIN_FIT_SCORE'] is None
assert read('SONG_SUCCESS_INTELLIGENCE_V01.json')['unique_recordings_total'] is None
for name,relative in read('DELIVERY_INDEX_V01.json')['outputs'].items(): assert (out/relative).is_file(),name
links=0
for f in out.glob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
        if target.startswith(('https://','http://','#')): continue
        assert (f.parent/target).exists(),(f.name,target); links+=1
audit={'status':'PASS','checks':['all_three_freeze_manifests','JSON_parse','registry_unique_ids','zone_membership_mode_and_bpm','zone_denominators','no_numeric_predictive_scores','governance_unchanged','delivery_index_paths','readable_local_links'], 'json_files_checked':len(all_json),'references_n':len(registry),'zones_n':len(zones),'local_links_checked':links,'limitations':'Integrity, membership and policy checks; not audio verification or certification of every source claim.'}
(root/'DELIVERY_VALIDATION.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit,indent=2))
