"""Contract fixture for tests/test_p2_request_contract.py, extracted from the STORED P2 read-back (not from the builder).
Usage: python3 make_contract_fixture.py P2_9974134_STORED_<ver>.json <old_fixture.json> <out_fixture.json>
The synthetic placement and auth header note are carried over from the previous fixture unchanged."""
import json
import sys
from pathlib import Path

stored = json.loads(Path(sys.argv[1]).read_text())
old = json.loads(Path(sys.argv[2]).read_text())


def walk(flow):
    for m in flow:
        yield m
        for r in m.get("routes", []):
            yield from walk(r["flow"])
        yield from walk(m.get("onerror", []))


mods = {m["id"]: m for m in walk(stored["blueprint"]["flow"])}
FETCH = {"instagram_reels": 300, "instagram_feed": 340, "facebook_reels": 380, "facebook_feed": 420,
         "youtube_shorts": 460, "youtube_hero": 500}
REGISTER = {"instagram_reels": 315, "instagram_feed": 355}
routes = []
for ch, f in FETCH.items():
    fetch, gate, upload = mods[f], mods[f + 3], mods[f + 6]
    hv = mods[f + 1]["mapper"]["variables"][0]
    assert hv["name"] == "bytes_sha256" and gate["module"].startswith("http:")
    fence = mods[f + 23]
    assert fence["module"] == "datastore:GetRecord" and fence["filter"]["name"].startswith("gate: eligible")
    r = dict(channel=ch, fetch_module=fetch["module"], fetch_id=f, fetch_filter=fetch.get("filter"),
             hash_variable=hv, gate_id=f + 3, gate_prefilter=gate["filter"], request_template=gate["mapper"]["data"],
             request_url=gate["mapper"]["url"], parse_id=f + 4, upload_module=upload["module"],
             upload_filter=fence["filter"], upload_fence_id=f + 23, ownership_filter=upload["filter"],
             blocked_hash_filter=mods[1000 + f + 11]["filter"], blocked_gate_filter=mods[1000 + f + 9]["filter"])
    if ch in REGISTER:
        reg = REGISTER[ch]
        assert mods[reg]["module"] == "json:ParseJSON"
        r.update(register_id=reg, register_source=mods[reg]["mapper"]["json"],
                 blocked_hosting_filter=mods[1000 + reg + 3]["filter"])
    routes.append(r)

out = dict(source="Make scenario 9974134 (P2 version f2) as stored in Make on %s (read back via API)" % stored["lastEdit"],
           auth_keychain_header=old["auth_keychain_header"], routes=routes, synthetic_placement=old["synthetic_placement"])
Path(sys.argv[3]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print("routes", len(routes), "->", sys.argv[3])
