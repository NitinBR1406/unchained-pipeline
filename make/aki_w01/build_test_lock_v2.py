"""TEST worker + probes for T1 (9975568) and T2 (9975668). SYNTHETIC ONLY. Test store 168532 (empty, no scenario usages,
fields post_id/timestamp), never the campaign store 196442. No platform module, no upload (upload = an AddRecord marker).

mode=work: mirrors P2 f2 ordering on synthetic keys in 168532:
  tlock:<place>:a<n>   insert-only lock (post_id = owner execution id)          [P2: plock:<placement>:a<n> in 196442]
  tstate:<place>       placement state, post_id = "<STATUS>|<owner>|<attempt>"   [P2: status / claim_token / attempt_count]
  tup:<place>:<owner uuid> one record per simulated upload (counts uploads; key <= 50 chars)
  tlog:*               auto-key log rows (post_id = event text)                 [P2: Error_Log]
 inputs: place, attempt, sleep1 (after lock, before claim), sleep2 (before upload fence), sleep3 (after upload, before write-back),
         fail_after_claim (1 = crash right after the claim), wb_fail (1 = write-back hits a missing key).
probe modes: probe_tostring, probe_statuscode, probe_missing, probe_agg_empty, probe_url (P2 IG hosting filter, test bucket)."""
import json
TS = 168532
P2URL = json.load(open('TEST_P2_IG_FILTERS.json'))      # written by the P2 test-bucket export below
def eq(a, b): return {"a": a, "b": b, "o": "text:equal"}
def ne(a, b): return {"a": a, "b": b, "o": "text:notequal"}
def mode(m): return {"name": "mode = " + m, "conditions": [[eq("{{var.input.mode}}", m)]]}
I = lambda k: "{{var.input.%s}}" % k
ME = "{{19.owner}}"   # per-bundle {{uuid}} owner token (var.execution.id is empty in Make runs)
STATE = "tstate:" + I("place")
OWNV = "PUBLISHING|" + ME + "|" + I("attempt")
def add(mid, key, text, overwrite=False, extra=None):
    m = {"id": mid, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": TS},
         "mapper": {"key": key, "overwrite": overwrite, "data": {"post_id": text, "timestamp": "{{now}}"}}}
    if extra: m.update(extra)
    return m
def logrow(mid, text): return {"id": mid, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": TS},
                               "mapper": {"overwrite": False, "data": {"post_id": text, "timestamp": "{{now}}"}}}
def sleep(mid, k): return {"id": mid, "module": "util:FunctionSleep", "version": 1, "mapper": {"duration": "{{ifempty(var.input.%s; 1)}}" % k}}
def get(mid): return {"id": mid, "module": "datastore:GetRecord", "version": 1, "parameters": {"datastore": TS}, "mapper": {"key": STATE, "returnWrapped": False}}
def upd(mid, key, text, extra=None):
    m = {"id": mid, "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": TS},
         "mapper": {"key": key, "upsert": False, "overwriteArrays": False, "data": {"post_id": text, "timestamp": "{{now}}"}}}
    if extra: m.update(extra)
    return m
own = lambda g: {"name": "this execution still owns the claim", "conditions": [[eq("{{%d.post_id}}" % g, OWNV)]]}
lost = lambda g: {"name": "claim lost", "conditions": [[ne("{{%d.post_id}}" % g, OWNV)]]}
A = "a=" + I("attempt")
work = [
 {"id": 19, "module": "util:SetVariables", "version": 1, "filter": mode("work"), "mapper": {"variables": [{"name": "owner", "value": "{{uuid}}"}]}},
 dict(add(2, "tlock:" + I("place") + ":a" + I("attempt"), ME,
          extra={"onerror": [logrow(3, "LOCK_REFUSED " + A + " exec=" + ME + " err={{ifempty(2.error.type; \"NO_TYPE\")}}: {{ifempty(2.error.message; \"NO_DETAIL\")}}")]}),
      ),
 sleep(4, "sleep1"),
 upd(5, STATE, OWNV, extra={"onerror": [logrow(6, "CLAIM_WRITE_FAIL " + A + " exec=" + ME + " err={{ifempty(5.error.type; \"NO_TYPE\")}}: {{ifempty(5.error.message; \"NO_DETAIL\")}}")]}),
 {"id": 7, "module": "json:ParseJSON", "version": 1, "mapper": {"json": '{{if(var.input.fail_after_claim = "1"; "CRASH_AFTER_CLAIM"; "{}")}}'}},
 sleep(8, "sleep2"),
 get(9),
 {"id": 10, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [
   {"flow": [dict(add(11, "tup:" + I("place") + ":" + ME, "SIMULATED_UPLOAD " + A + " exec=" + ME), filter=own(9)),
             sleep(12, "sleep3"), get(13),
             {"id": 14, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [
               {"flow": [dict(upd(15, STATE + '{{if(var.input.wb_fail = "1"; "-MISSING"; "")}}', "PUBLISHED|" + ME + "|" + I("attempt"),
                                  extra={"onerror": [logrow(16, "WRITEBACK_FAIL_AFTER_UPLOAD " + A + " id=SIM-" + ME + " err={{ifempty(15.error.type; \"NO_TYPE\")}}")]}),
                              filter=own(13))]},
               {"flow": [dict(logrow(17, "WRITEBACK_SKIPPED_CLAIM_LOST " + A + " id=SIM-" + ME + " owner={{13.post_id}}"), filter=lost(13))]}]}]},
   {"flow": [dict(logrow(18, "CLAIM_LOST_BEFORE_UPLOAD " + A + " exec=" + ME + " state={{9.post_id}}"), filter=lost(9))]}]},
]
GH404 = "https://raw.githubusercontent.com/NitinBR1406/unchained-pipeline/3a6fbffdb53db243d5d6a24ace913a98b83df1d3/tests/fixtures/synthetic_media/DOES_NOT_EXIST.bin"
def http404(mid, m, handler):
    return {"id": mid, "module": "http:MakeRequest", "version": 4, "parameters": {"authenticationType": "noAuth"}, "filter": mode(m),
            "mapper": {"url": GH404, "method": "get", "timeout": 15, "shareCookies": False, "parseResponse": False, "allowRedirects": False,
                       "stopOnHttpError": True, "requestCompressedContent": False},
            "onerror": [{"id": mid + 1, "module": "json:ParseJSON", "version": 1, "mapper": {"json": handler % mid}},
                        {"id": mid + 2, "module": "builtin:Ignore", "version": 1, "mapper": None}]}
probes = [
 {"flow": [dict(add(70, I("place"), "KEY_PROBE len={{length(var.input.place)}}"), filter=mode("probe_key"))]},
 # status 1 = expression evaluated without error AND gave the expected kind of value; status 3 = not
 {"flow": [http404(40, "probe_tostring", '{{if(length(toString(%d.error)) > 0; "{}"; "MARKER_EMPTY_NOT_JSON")}}')]},
 {"flow": [http404(43, "probe_statuscode", '{{if(%d.error.statusCode = 404; "{}"; "MARKER_NOT_404_NOT_JSON")}}')]},
 {"flow": [http404(46, "probe_missing", '{{if(ifempty(%d.error.no_such_field; "DEFAULT") = "DEFAULT"; "{}"; "MARKER_NOT_DEFAULT_NOT_JSON")}}')]},
 {"flow": [{"id": 50, "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": TS}, "filter": mode("probe_agg_empty"),
            "mapper": {"filter": [[{"a": "post_id", "b": "NO_SUCH_VALUE_PROBE", "o": "text:equal"}]], "limit": 5}},
           {"id": 51, "module": "builtin:BasicAggregator", "version": 1, "parameters": {"feeder": 50}, "mapper": {"post_id": "{{50.post_id}}"}},
           {"id": 52, "module": "json:ParseJSON", "version": 1, "mapper": {"json": '{{if(length(51.array) = 0; "MARKER_AGG_EMITTED_EMPTY_NOT_JSON"; "{}")}}'}}]},
 {"flow": [{"id": P2URL["reg_id"], "module": "json:ParseJSON", "version": 1, "filter": mode("probe_url"), "mapper": {"json": I("reg")}},
           {"id": 60, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [
             {"flow": [{"id": 61, "module": "util:SetVariables", "version": 1, "filter": P2URL["ok"], "mapper": {"variables": [{"name": "url_ok", "value": "1"}]}}]},
             {"flow": [{"id": 62, "module": "json:ParseJSON", "version": 1, "filter": P2URL["bad"], "mapper": {"json": "MARKER_URL_REJECTED_NOT_JSON"}}]}]}]},
]
flow = [{"id": 1, "module": "json:ParseJSON", "version": 1, "mapper": {"json": '{{if(var.input.mode = "probe_url"; var.input.rec; "{}")}}'}},
        {"id": 90, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [{"flow": work}] + probes}]
bp = {"name": "TEST LOCK/PROBE v2 (uuid owner): synthetic, test store 168532 only (no campaign store, no upload) — manual", "flow": flow,
      "metadata": {"instant": False, "version": 1, "scenario": {"dlq": False, "dataloss": False, "maxErrors": 3, "autoCommit": True, "roundtrips": 1,
                   "sequential": True, "confidential": False, "freshVariables": False, "autoCommitTriggerLast": True}}}
iface = {"input": [{"name": k, "type": "text", "required": k == "mode"} for k in
                   ("mode", "place", "attempt", "sleep1", "sleep2", "sleep3", "fail_after_claim", "wb_fail", "rec", "reg")], "output": []}
used = set()
def w(f):
    for m in f:
        used.add(m["module"]); w(m.get("onerror") or [])
        for r in m.get("routes") or []: w(r["flow"])
        assert m.get("parameters", {}).get("datastore") in (None, TS), m
w(flow)
assert used <= {"json:ParseJSON", "builtin:BasicRouter", "datastore:AddRecord", "datastore:GetRecord", "datastore:UpdateRecord", "datastore:SearchRecord",
                "builtin:BasicAggregator", "util:FunctionSleep", "util:SetVariables", "http:MakeRequest", "builtin:Ignore"}, used
assert "196442" not in json.dumps(bp)
json.dump(bp, open("TEST_LOCK_V2_blueprint.json", "w"), ensure_ascii=False); json.dump(iface, open("TEST_LOCK_V2_interface.json", "w"))
print(sorted(used), len(json.dumps(bp)))
