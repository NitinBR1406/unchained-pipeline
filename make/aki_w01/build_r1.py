"""R1 v2: AKI Publication Reconcile (INACTIVE, on-demand). READ-ONLY on social platforms; it DOES update internal
registrations in data store 196442 (reconcile_status / reconcile_note / reconcile_at, and status=PUBLISHED only when proven).

Handles the unknown-outcome cases P2 never retries:
  - OUTCOME_UNKNOWN : the publish call errored after it may already have published;
  - PUBLISHING with an expired lock : P2 crashed after the claim, lost its claim, or the id write-back failed.

Evidence levels (v2, 2026-10-14):
  1. PROVEN  - a platform id that P2 itself received from the upload response for THIS placement and THIS attempt
               (Error_Log: WRITEBACK_FAIL_AFTER_UPLOAD / WRITEBACK_SKIPPED_CLAIM_LOST "a=<attempt> id=<id>"), looked up BY ID on the
               platform and checked: exact account/page (IG owner.id, FB post from.id), media/product type, creation time inside the
               attempt window, and the exact text. Only then: status=PUBLISHED, published_via=RECONCILED_BY_ID.
  2. CANDIDATE - no stored id; recent posts with the exact text, right account, right media type AND created inside the attempt
               window. Text overlap is never proof, even with one result: status unchanged, reconcile_status=CANDIDATE_UNVERIFIED
               (or MULTIPLE_CANDIDATES), candidate ids in reconcile_note -> human decision.
  3. NOT_FOUND - no candidate. Not proof of absence (search/visibility delay, YouTube search is global and cannot be limited
               to the own channel). Status unchanged -> human decision; never an automatic new upload.
Attempt window: attempt_started_at (P2 f2 claim; fallback lock_until - 45 min) - 2 min .. + 6 h.
TikTok is not looked up (no API access)."""
import json
DS, ERR = 196442, 168812
IG, FB, YT = 14369479, 14363628, 14374103
IG_ACCOUNT, FB_PAGE = "17841457677776171", "839373332878305"
START = '{{formatDate(addMinutes(ifempty(1.data.attempt_started_at; addMinutes(1.data.lock_until; -45)); -2); "X")}}'
END = '{{formatDate(addHours(ifempty(1.data.attempt_started_at; addMinutes(1.data.lock_until; -45)); 6); "X")}}'
def eq(a, b): return {"a": a, "b": b, "o": "text:equal"}
def ne(a, b): return {"a": a, "b": b, "o": "text:notequal"}
def inwin(ts):
    t = '{{formatDate(%s; "X")}}' % ts
    return [{"a": t, "b": START, "o": "number:greaterorequal"}, {"a": t, "b": END, "o": "number:lessorequal"}]
def upd(mid, data, flt=None):
    m = {"id": mid, "mapper": {"key": "{{1.key}}", "data": data, "upsert": False, "overwriteArrays": False},
         "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS}}
    if flt: m["filter"] = flt
    return m
def ch_is(*chs): return {"name": "channel " + "/".join(chs), "conditions": [[eq("{{1.data.channel}}", c)] for c in chs]}
def andf(f, extra, name): return {"name": f["name"] + " + " + name, "conditions": [g + extra for g in f["conditions"]]}
SID = "{{5.stored_id}}"

def proven(mid, getter, checks, url):
    return upd(mid, {"status": "PUBLISHED", "platform_post_id": SID, "platform_url": url, "published_via": "RECONCILED_BY_ID",
                     "published_at": "{{ifempty(1.data.published_at; now)}}", "reconcile_status": "VERIFIED_PLATFORM_ID", "reconcile_at": "{{now}}",
                     "reconcile_note": "stored upload id from P2 (Error_Log, attempt {{1.data.attempt_count}}) verified on the platform",
                     "lock_until": "", "m24h_status": "PENDING", "m72h_status": "PENDING", "m7d_status": "PENDING"},
               {"name": "platform object matches account, type, attempt window and text", "conditions": [checks]})
def mismatch(mid, checks):
    return upd(mid, {"reconcile_status": "STORED_ID_MISMATCH", "reconcile_at": "{{now}}",
                     "reconcile_note": "stored id " + SID + " exists but does not match account/type/window/text; human decision required"},
               {"name": "stored id does not match", "conditions": [[dict(c, o={"text:equal": "text:notequal", "text:notequal": "text:equal",
                "number:greaterorequal": "number:less", "number:lessorequal": "number:greater"}[c["o"]])] for c in checks]})
def unverifiable(mid):
    return [upd(mid, {"reconcile_status": "STORED_ID_NOT_VERIFIABLE", "reconcile_at": "{{now}}",
                      "reconcile_note": "lookup of stored id " + SID + " failed; human decision required"})]
def by_id(base, chs, lookup, checks, url):
    get = dict(lookup, id=base, filter=ch_is(*chs), onerror=unverifiable(base + 9))
    return {"flow": [get, {"id": base + 1, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
        {"flow": [proven(base + 2, base, checks, url)]}, {"flow": [mismatch(base + 3, checks)]}]}]}

def candidates(base, chs, src, conds, label):
    """list recent posts -> aggregate those matching text + account + type + attempt window -> classify; never PUBLISHED."""
    s = dict(src, id=base, filter=ch_is(*chs))
    agg = {"id": base + 1, "mapper": {"id": "{{%d.id}}" % base}, "module": "builtin:BasicAggregator", "version": 1,
           "parameters": {"feeder": base}, "filter": {"name": "exact text + account + type + inside attempt window", "conditions": [conds]}}
    n = "{{length(%d.array)}}" % (base + 1)
    note = "{{length(%d.array)}} candidate(s) [{{join(map(%d.array; \"id\"); \",\")}}] by %s; text match is not proof; human decision required" % (base + 1, base + 1, label)
    return {"flow": [s, agg, upd(base + 2, {"reconcile_status": "{{if(%s = 0; \"NOT_FOUND\"; if(%s = 1; \"CANDIDATE_UNVERIFIED\"; \"MULTIPLE_CANDIDATES\"))}}" % (n[2:-2], n[2:-2]),
                                            "reconcile_at": "{{now}}", "reconcile_note": note})]}

IGT = {"instagram_reels": "REELS", "instagram_feed": "FEED"}
routes_id = [
 by_id(100, ["instagram_reels", "instagram_feed"], {"mapper": {"id": SID}, "module": "instagram-business:GetMedia", "version": 1, "parameters": {"__IMTCONN__": IG}},
       [eq("{{100.owner.id}}", IG_ACCOUNT), eq("{{100.media_product_type}}", '{{if(1.data.channel = "instagram_reels"; "REELS"; "FEED")}}'),
        eq("{{100.caption}}", "{{1.data.caption}}")] + inwin("100.timestamp"), "{{100.permalink}}"),
 by_id(110, ["facebook_reels"], {"mapper": {"page_id": FB_PAGE, "video_id": SID}, "module": "facebook-pages:GetVideo", "version": 6, "parameters": {"__IMTCONN__": FB}},
       [eq("{{110.id}}", SID), eq("{{110.description}}", "{{1.data.caption}}")] + inwin("110.created_time"), "https://www.facebook.com/reel/" + SID),
 by_id(120, ["facebook_feed"], {"mapper": {"page_id": FB_PAGE, "id": SID}, "module": "facebook-pages:GetPost", "version": 6, "parameters": {"__IMTCONN__": FB}},
       [eq("{{120.from.id}}", FB_PAGE), eq("{{120.message}}", "{{1.data.caption}}")] + inwin("120.created_time"), "{{120.permalink_url}}"),
 by_id(130, ["youtube_shorts", "youtube_hero"], {"mapper": {"id": SID}, "module": "youtube:ActionGetVideo", "version": 3, "parameters": {"account": YT}},
       [eq("{{130.id}}", SID), eq("{{130.title}}", "{{1.data.title}}")] + inwin("130.dateCreated"), "{{130.url}}"),
]
routes_cand = [
 candidates(200, ["instagram_reels", "instagram_feed"], {"mapper": {"accountId": IG_ACCOUNT, "limit": 50}, "module": "instagram-business:GetUserMedia", "version": 1,
            "parameters": {"__IMTCONN__": IG}},
            [eq("{{200.caption}}", "{{1.data.caption}}"), eq("{{200.owner.id}}", IG_ACCOUNT),
             eq("{{200.media_product_type}}", '{{if(1.data.channel = "instagram_reels"; "REELS"; "FEED")}}')] + inwin("200.timestamp"), "IG caption+owner+type+window"),
 candidates(210, ["facebook_reels"], {"mapper": {"page_id": FB_PAGE, "type": "uploaded", "limit": 50}, "module": "facebook-pages:ListVideos", "version": 6,
            "parameters": {"__IMTCONN__": FB}},
            [eq("{{210.description}}", "{{1.data.caption}}")] + inwin("210.created_time"), "FB page video description+window"),
 candidates(220, ["facebook_feed"], {"mapper": {"page_id": FB_PAGE, "limit": 50}, "module": "facebook-pages:ListPosts", "version": 6, "parameters": {"__IMTCONN__": FB}},
            [eq("{{220.message}}", "{{1.data.caption}}")] + inwin("220.created_time"), "FB page post message+window"),
 candidates(230, ["youtube_shorts", "youtube_hero"], {"mapper": {"query": "{{1.data.title}}", "maxResults": 25, "order": "date",
            "publishedAfter": '{{formatDate(addMinutes(ifempty(1.data.attempt_started_at; addMinutes(1.data.lock_until; -45)); -2); "YYYY-MM-DDTHH:mm:ss[Z]")}}'},
            "module": "youtube:ActionSearchVideo", "version": 3, "parameters": {"account": YT}},
            [eq("{{230.title}}", "{{1.data.title}}")] + inwin("230.dateCreated"), "YouTube global search title+window (own channel cannot be verified)"),
]
flow = [
 {"id": 1, "mapper": {"filter": [[eq("campaign_id", "aakhri-ishq"), eq("status", "OUTCOME_UNKNOWN")],
                                 [eq("campaign_id", "aakhri-ishq"), eq("status", "PUBLISHING")]]},
  "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": DS}},
 {"id": 2, "filter": {"name": "claim expired (P2 no longer working on it) and not TikTok", "conditions": [[
     {"a": '{{if(1.data.lock_until; formatDate(1.data.lock_until; "X"); 0)}}', "b": '{{formatDate(now; "X")}}', "o": "number:lessorequal"},
     ne("{{1.data.platform_api}}", "tiktok")]]},
  "mapper": {"variables": [{"name": "attempt", "value": "{{1.data.attempt_count}}"}]}, "module": "util:SetVariables", "version": 1},
 # stored platform id for THIS placement + attempt, as logged by P2 (write-back failed or claim lost after a successful upload)
 {"id": 3, "mapper": {"filter": [[eq("post_id", "{{1.key}}"), {"a": "error_type", "b": "WRITEBACK_", "o": "text:contain"},
                                  {"a": "error_type", "b": " a={{1.data.attempt_count}} id=", "o": "text:contain"}]]},
  "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": ERR}},
 {"id": 4, "mapper": {"id": '{{replace(3.error_type; /^.* id=([^ ]+).*$/; "$1")}}'}, "module": "builtin:BasicAggregator", "version": 1,
  "parameters": {"feeder": 3}},
 {"id": 5, "mapper": {"variables": [{"name": "stored_id", "value": '{{if(length(distinct(map(4.array; "id"))) = 1; first(map(4.array; "id")); "")}}'},
                                    {"name": "stored_ids", "value": '{{length(distinct(map(4.array; "id")))}}'}]}, "module": "util:SetVariables", "version": 1},
 {"id": 10, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
     {"flow": [{"id": 11, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "filter": {"name": "exactly one stored id", "conditions": [[ne(SID, "")]]},
                "routes": routes_id}]},
     {"flow": [{"id": 12, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "filter": {"name": "no stored id", "conditions": [[eq("{{5.stored_ids}}", "0")]]},
                "routes": routes_cand}]},
     {"flow": [upd(13, {"reconcile_status": "CONFLICTING_STORED_IDS", "reconcile_at": "{{now}}",
                        "reconcile_note": "{{5.stored_ids}} different stored ids for this attempt; human decision required"},
                   {"name": "more than one stored id", "conditions": [[{"a": "{{5.stored_ids}}", "b": "1", "o": "number:greater"}]]})]}]},
]
bp = {"name": "R1: AKI Publication Reconcile v2 (read-only on platforms; proven only by stored id) — INACTIVE", "flow": flow,
      "metadata": {"instant": False, "version": 1, "designer": {"orphans": []}, "scenario": {"dlq": False, "dataloss": False, "maxErrors": 3, "autoCommit": True,
                   "roundtrips": 1, "sequential": True, "confidential": False, "freshVariables": False, "autoCommitTriggerLast": True}}}
from make_error_refs import bind_error_refs
bind_error_refs(bp['flow'])
if __name__ == '__main__':
    json.dump(bp, open('R1_blueprint.json', 'w'), ensure_ascii=False)
    print(len(json.dumps(bp)))
