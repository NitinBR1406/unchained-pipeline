import json
from pathlib import Path
from multitake.v03_color_consistency import load,WINDOWS

def test_contract(tmp_path):
    p=tmp_path/'c.json'; p.write_text(json.dumps({'schema':'V03_COLOR_CONSISTENCY_CONTRACT_V01','timeline_windows_ms':[list(x) for x in WINDOWS],'full_master_allowed':False,'creative_motion_enabled':False,'programme_audio_sha256':'670e5ddf2dac70563789ffc4c5a505af950c75310b68b674e9dd2b1a06b8def2','color_management':{'input':'Rec.2100 HLG','timeline':'Rec.2100 HLG','output':'Rec.2100 HLG','tone_mapping':'None','gamut_mapping':'None'}}))
    assert load(p)['timeline_windows_ms'][0]==[8000,24000]

def test_windows_cover_required_ranges_and_are_not_full_master():
    assert sum(e-s for s,e in WINDOWS)==62000
    for s,e in ((9000,21000),(73000,89000),(112000,114000)):
        assert any(ws<=s and e<=we for ws,we in WINDOWS)
