"""P3: AKI TikTok Direct Post (BLOCKED, INACTIVE, on-demand) — technically complete route, kept unusable.

Hard blocks (all must change before anything can run):
  * no placement has tiktok_route_enabled=TRUE (field does not exist on any record);
  * TikTok app not audited -> unaudited clients may only post SELF_ONLY to a private account (TikTok docs);
  * sandbox token in data store 168757 is expired; the TikTok Auth Exchange scenario holds a hard-coded secret;
  * photo posts need PULL_FROM_URL from a verified domain / URL prefix (no public media host approved).
Same safety chain as P2 version e: insert-only exclusive lock BEFORE the claim; fetch the exact bytes; sha256 computed over
them (+ Drive sha256Checksum for video; version-pinned, content-addressed URL for photos); the gate receives the COMPUTED
hash; any mismatch / missing hash / disallowed privacy level -> BLOCKED (never a silent stop); OUTCOME_UNKNOWN after a
possibly successful call, no blind retry.
TikTok UX rules: privacy level must be chosen by the creator per post on the approval page (unpipe.tiktok_settings; stored on
the publish grant, returned by the gate as <gate>.tiktok.*; no default; a missing choice -> BLOCKED)
and must be one of creator_info.privacy_level_options; comment/duet/stitch off unless chosen; caption editable (it is
the approved package text). A Direct Post returns a publish_id; the public post id only appears after moderation
(status/fetch) -> status SUBMITTED, reconciled later."""
import json
import os
DS, ERR, KEYCHAIN, TOK, GDRIVE = 196442, 168812, 217337, 168757, 14383570
TT = "https://open.tiktokapis.com/v2"

def upd(mid, data, flt=None):
    m = {"id": mid, "mapper": {"key": "{{1.key}}", "data": data, "upsert": False, "overwriteArrays": False},
         "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS}}
    if flt: m["filter"] = flt
    return m
def log(mid, label):
    return {"id": mid, "mapper": {"data": {"post_id": "{{1.key}}", "platform": "{{1.data.channel}}", "scenario": "P3", "raw_error": "{{ifempty(error.type; \"NO_TYPE\")}}: {{ifempty(error.message; \"NO_DETAIL\")}}",
            "timestamp": "{{now}}", "error_type": label, "status_code": "{{ifempty(error.statusCode; \"\")}}", "error_message": "{{ifempty(error.message; \"NO_DETAIL\")}}"}, "overwrite": False},
            "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ERR}}
def fail(mid, label):
    return [upd(mid, {"status": "FAILED", "last_error": label + ": {{error.message}}", "last_error_at": "{{now}}", "lock_until": ""}), log(mid + 1, label)]
def uncertain(mid, label):
    return [upd(mid, {"status": "OUTCOME_UNKNOWN", "last_error": label + ": {{error.type}} {{error.message}}", "last_error_at": "{{now}}"}), log(mid + 1, label + "/OUTCOME_UNKNOWN")]
def http(mid, url, body, onerror, extra=None):
    m = {"id": mid, "mapper": {"url": url, "method": "post", "headers": [{"name": "Authorization", "value": "Bearer {{62.access_token}}"},
          {"name": "Content-Type", "value": "application/json; charset=UTF-8"}], "contentType": "json", "inputMethod": "jsonString",
          "jsonStringBodyContent": body, "parseResponse": True, "shareCookies": False, "allowRedirects": False, "stopOnHttpError": True,
          "requestCompressedContent": False, "timeout": 120}, "module": "http:MakeRequest", "version": 4,
         "parameters": {"authenticationType": "noAuth"}, "onerror": onerror}
    if extra: m.update(extra)
    return m
def post_info(g):
    """Creator's per-post choice as returned by the publish gate (unpipe.tiktok_settings), never from the Make record."""
    return ('"post_info":{"title":"{{replace(1.data.caption; newline; \"\\n\")}}","privacy_level":"{{%d.tiktok.privacy_level}}",'
            '"disable_comment":{{%d.tiktok.disable_comment}},"disable_duet":{{%d.tiktok.disable_duet}},"disable_stitch":{{%d.tiktok.disable_stitch}}}' % (g, g, g, g))
def eq(a, b): return {"a": a, "b": b, "o": "text:equal"}
def blocked_on_error(mid, label):   # deterministic failure (e.g. hash function error): log + BLOCKED, never a silent stop
    return [log(mid, label), upd(mid + 1, {"status": "BLOCKED", "last_error": label + ": {{error.message}}", "last_error_at": "{{now}}", "lock_until": ""})]
def logged(m, log_id, label):
    m["onerror"] = [log(log_id, label)]
    return m
def ne(a, b): return {"a": a, "b": b, "o": "text:notequal"}
def gate(mid, sha_expr):
    body = ('{"content_id":"{{1.data.gate_content_id}}","platform":"{{1.data.channel}}","target_account":"{{1.data.target_account}}",'
            '"asset_sha256":"' + sha_expr + '","packaging_sha256":"{{1.data.packaging_sha256}}","schedule_version":"{{1.data.schedule_version}}",'
            '"scheduled_at_epoch":{{1.data.scheduled_at_epoch}}}')
    return [{"id": mid, "mapper": {"qs": [], "url": "https://unchained-approval.onrender.com/v/publish-eligibility", "data": body, "gzip": True,
             "method": "post", "headers": [], "useMtls": False, "bodyType": "raw", "contentType": "application/json", "serializeUrl": False,
             "shareCookies": False, "parseResponse": False, "followRedirect": True, "useQuerystring": False, "followAllRedirects": False,
             "rejectUnauthorized": True}, "module": "http:ActionSendDataAPIKeyAuth", "version": 3, "parameters": {"auth": KEYCHAIN, "handleErrors": True},
             "onerror": fail(mid + 30, "GATE_HTTP_FAIL")},
            {"id": mid + 1, "mapper": {"json": "{{toString(%d.data)}}" % mid}, "module": "json:ParseJSON", "version": 1, "onerror": fail(mid + 32, "GATE_PARSE_FAIL")}]
# TikTok photo pulls from a hosted URL. Until a hosting register + private bucket are approved (same rule as P2 IG_BUCKET),
# this route is fail-closed: the sentinel makes the gate filter false and the BLOCKED filter true.
TT_PHOTO_HOSTING = "UNCONFIGURED"
HOSTING_OFF_OK = {"a": TT_PHOTO_HOSTING, "b": "UNCONFIGURED", "o": "text:notequal"}
HOSTING_OFF_BAD = {"a": TT_PHOTO_HOSTING, "b": "UNCONFIGURED", "o": "text:equal"}
def blocked(mid, msg, conds, name):
    return upd(mid, {"status": "BLOCKED", "last_error": msg, "last_error_at": "{{now}}", "lock_until": ""}, flt={"name": name, "conditions": conds})
def priv_router(mid, then, g):
    """creator_info -> privacy level chosen by the creator must be offered; otherwise BLOCKED (no silent stop)"""
    return [{"id": mid, "mapper": {"key": "main", "returnWrapped": False}, "module": "datastore:GetRecord", "version": 1, "parameters": {"datastore": TOK}},
            dict(http(mid + 1, TT + "/post/publish/creator_info/query/", "{}", fail(mid + 40, "TT_CREATOR_INFO_FAIL")),
                 mapper=dict(http(0, "", "", [])["mapper"], url=TT + "/post/publish/creator_info/query/", jsonStringBodyContent="{}",
                             headers=[{"name": "Authorization", "value": "Bearer {{%d.access_token}}" % mid}, {"name": "Content-Type", "value": "application/json; charset=UTF-8"}])),
            {"id": mid + 2, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
                {"flow": then},
                {"flow": [blocked(mid + 3, "TT_PRIVACY_NOT_CHOSEN_OR_NOT_OFFERED: {{ifempty(%d.tiktok.privacy_level; \"NONE\")}}" % g,
                                  [[{"a": "{{%d.data.data.privacy_level_options}}" % (mid + 1), "b": "{{%d.tiktok.privacy_level}}" % g, "o": "array:notcontain"}]],
                                  "privacy level not offered by creator_info -> BLOCKED")]}]}]
def tok(mid): return "Bearer {{%d.access_token}}" % mid
def tt_http(mid, url, body, onerror, tokmid, flt=None):
    m = http(mid, url, body, onerror)
    m["mapper"]["headers"][0]["value"] = tok(tokmid)
    if flt: m["filter"] = flt
    return m
def gate_yes(p): return [eq("{{%d.reason}}" % p, "VALID_PUBLISH_APPROVAL"), eq('{{if(%d.eligible = true; "EOK"; "ENO")}}' % p, "EOK")]
def gate_no(p): return [[ne("{{%d.reason}}" % p, "VALID_PUBLISH_APPROVAL")], [ne('{{if(%d.eligible = true; "EOK"; "ENO")}}' % p, "EOK")]]

# ---- video: Drive download -> sha256 -> gate(computed) -> [DIRECT: creator_info/privacy] -> init -> single-chunk upload ----
# TT_VIDEO_MODE: INBOX (default, approved by Nitin 2026-10-15) = "Upload to TikTok": the video lands as a draft in the creator's
# TikTok inbox; caption, privacy and the final Post tap happen in the TikTok app (no audit needed). DIRECT = Direct Post (audit).
TT_VIDEO_MODE = os.environ.get("AKI_TT_VIDEO_MODE", "INBOX")
NOTIFY_TO = os.environ.get("AKI_NOTIFY_EMAIL", "")       # not committed (public repo); empty => no notification module
V = 200
v_priv = {"a": "{{%d.data.data.privacy_level_options}}" % (V + 21), "b": "{{%d.tiktok.privacy_level}}" % (V + 4), "o": "array:contain"}
video_upload = [
    tt_http(V + 30, TT + "/post/publish/video/init/",
            '{' + post_info(V + 4) + ',"source_info":{"source":"FILE_UPLOAD","video_size":{{%d.filesize}},"chunk_size":{{%d.filesize}},"total_chunk_count":1}}' % (V, V),
            fail(V + 70, "TT_INIT_FAIL"), V + 20, flt={"name": "privacy level offered by creator_info", "conditions": [[v_priv]]}),
    {"id": V + 31, "mapper": {"url": "{{%d.data.data.upload_url}}" % (V + 30), "method": "put", "headers": [
        {"name": "Content-Range", "value": "bytes 0-{{%d.filesize - 1}}/{{%d.filesize}}" % (V, V)}], "contentType": "custom", "contentTypeValue": "video/mp4",
        "rawBodyContent": "{{%d.data}}" % V, "parseResponse": False, "shareCookies": False, "allowRedirects": False, "stopOnHttpError": True,
        "requestCompressedContent": False, "timeout": 300}, "module": "http:MakeRequest", "version": 4, "parameters": {"authenticationType": "noAuth"},
     "onerror": uncertain(V + 72, "TT_UPLOAD")},
    logged(upd(V + 32, {"status": "SUBMITTED", "platform_post_id": "", "reconcile_note": "tiktok publish_id={{%d.data.data.publish_id}} (post id after moderation via status/fetch)" % (V + 30),
                 "published_via": "AUTO_P3", "lock_until": "", "last_error": ""}), V + 84, "WRITEBACK_FAIL_AFTER_SUBMIT publish_id={{%d.data.data.publish_id}}" % (V + 30))]
if TT_VIDEO_MODE == "INBOX":
    video_upload[0] = tt_http(V + 30, TT + "/post/publish/inbox/video/init/",
                              '{"source_info":{"source":"FILE_UPLOAD","video_size":{{%d.filesize}},"chunk_size":{{%d.filesize}},"total_chunk_count":1}}' % (V, V),
                              fail(V + 70, "TT_INIT_FAIL"), V + 20)
    video_upload[2] = logged(upd(V + 32, {"status": "DRAFT_IN_TIKTOK_INBOX", "platform_post_id": "",
                                          "reconcile_note": "tiktok inbox draft publish_id={{%d.data.data.publish_id}}; creator posts it in the app; post id via status/fetch or manual registration" % (V + 30),
                                          "published_via": "AUTO_P3_INBOX", "lock_until": "", "last_error": ""}),
                             V + 84, "WRITEBACK_FAIL_AFTER_SUBMIT publish_id={{%d.data.data.publish_id}}" % (V + 30))
    if NOTIFY_TO:
        video_upload.append({"id": V + 60, "module": "email:ActionSendMeEmail", "version": 7, "parameters": {}, "mapper": {
            "to": NOTIFY_TO, "subject": "TikTok-concept klaar: {{1.key}}",
            "html": "<p>De video voor <b>{{1.key}}</b> staat als concept in je TikTok-inbox. Open TikTok, plak de caption hieronder, "
                    "kies de privacy-instelling en tik op Plaatsen.</p><pre style=\"white-space:pre-wrap\">{{1.data.caption}}</pre>"
                    "<p>publish_id: {{%d.data.data.publish_id}}</p>" % (V + 30)}, "onerror": [log(V + 87, "NOTIFY_FAIL")]})
    video_gate_yes = [{"id": V + 20, "mapper": {"key": "main", "returnWrapped": False}, "module": "datastore:GetRecord", "version": 1,
                       "parameters": {"datastore": TOK}}] + video_upload
else:
    video_gate_yes = priv_router(V + 20, video_upload, V + 4)
video = {"flow": [
    {"id": V, "filter": {"name": "tiktok video (variant 9x16, Drive binary)", "conditions": [[eq("{{1.data.channel}}", "tiktok"), eq("{{1.data.format_variant}}", "9x16")]]},
     "mapper": {"select": "map", "file": "{{1.data.drive_file_id}}", "formatDocuments": "application/pdf", "formatSpreadsheets": "text/csv",
                "formatPresentations": "application/pdf", "formatDrawings": "image/jpeg"},
     "module": "google-drive:getAFile", "version": 4, "parameters": {"__IMTCONN__": GDRIVE}, "onerror": fail(V + 74, "DRIVE_DOWNLOAD_FAIL")},
    {"id": V + 1, "mapper": {"variables": [{"name": "bytes_sha256", "value": "{{sha256(%d.data)}}" % V}]}, "module": "util:SetVariables", "version": 1,
     "onerror": blocked_on_error(V + 80, "HASH_COMPUTE_FAIL")},
    {"id": V + 2, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
        {"flow": [dict(gate(V + 3, "{{%d.bytes_sha256}}" % (V + 1))[0], filter={"name": "computed bytes sha256 == registered AND Drive sha256Checksum == registered AND <= 64 MB",
                       "conditions": [[{"a": "{{1.data.asset_sha256}}", "b": "", "o": "text:notequal"}, eq("{{%d.bytes_sha256}}" % (V + 1), "{{1.data.asset_sha256}}"), eq("{{%d.sha256Checksum}}" % V, "{{1.data.asset_sha256}}"),
                                       {"a": "{{%d.filesize}}" % V, "b": "67108864", "o": "number:lessorequal"}]]}),
                  gate(V + 3, "")[1],
                  {"id": V + 5, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
                      {"flow": [dict(x, filter={"name": "gate said YES", "conditions": [gate_yes(V + 4)]}) if i == 0 else x
                                for i, x in enumerate(video_gate_yes)]},
                      {"flow": [blocked(V + 6, "GATE_NOT_ELIGIBLE: {{%d.reason}}" % (V + 4), gate_no(V + 4), "gate said NO / unexpected answer -> BLOCKED")]}]}]},
        {"flow": [blocked(V + 7, "ASSET_HASH_MISMATCH_OR_TOO_LARGE: bytes {{%d.bytes_sha256}} / drive {{ifempty(%d.sha256Checksum; \"NONE\")}} / registered {{ifempty(1.data.asset_sha256; \"NONE\")}} / size {{%d.filesize}}" % (V + 1, V, V),
                          [[ne("{{%d.bytes_sha256}}" % (V + 1), "{{1.data.asset_sha256}}")], [eq("{{1.data.asset_sha256}}", "")], [ne('{{ifempty(%d.sha256Checksum; "NONE")}}' % V, "{{1.data.asset_sha256}}")],
                           [{"a": "{{%d.filesize}}" % V, "b": "67108864", "o": "number:greater"}]],
                          "hash mismatch / missing / > 64 MB -> BLOCKED")]}]}]}
# ---- photo: GET pinned hosted JPEG -> sha256 -> gate(computed) -> creator_info/privacy -> content init (PULL_FROM_URL) ----
F = 300
f_priv = {"a": "{{%d.data.data.privacy_level_options}}" % (F + 21), "b": "{{%d.tiktok.privacy_level}}" % (F + 4), "o": "array:contain"}
photo_post = [
    tt_http(F + 30, TT + "/post/publish/content/init/",
            '{"media_type":"PHOTO","post_mode":"DIRECT_POST",' + post_info(F + 4).replace(',"disable_duet":{{%d.tiktok.disable_duet}},"disable_stitch":{{%d.tiktok.disable_stitch}}' % (F + 4, F + 4), ',"auto_add_music":false') +
            ',"source_info":{"source":"PULL_FROM_URL","photo_cover_index":0,"photo_images":["{{1.data.media_url}}"]}}',
            uncertain(F + 70, "TT_PHOTO_INIT"), F + 20, flt={"name": "privacy level offered by creator_info", "conditions": [[f_priv]]}),
    logged(upd(F + 31, {"status": "SUBMITTED", "reconcile_note": "tiktok publish_id={{%d.data.data.publish_id}}" % (F + 30), "published_via": "AUTO_P3", "lock_until": "", "last_error": ""}),
           F + 84, "WRITEBACK_FAIL_AFTER_SUBMIT publish_id={{%d.data.data.publish_id}}" % (F + 30))]
photo = {"flow": [
    {"id": F, "filter": {"name": "tiktok photo (variant 9x16jpg, hosted pinned URL)", "conditions": [[eq("{{1.data.channel}}", "tiktok_photo"), eq("{{1.data.format_variant}}", "9x16jpg")]]},
     "mapper": {"url": "{{1.data.media_url}}", "method": "get", "timeout": 120, "shareCookies": False, "parseResponse": False, "allowRedirects": False,
                "stopOnHttpError": True, "requestCompressedContent": False}, "module": "http:MakeRequest", "version": 4,
     "parameters": {"authenticationType": "noAuth"}, "onerror": fail(F + 74, "MEDIA_URL_FETCH_FAIL")},
    {"id": F + 1, "mapper": {"variables": [{"name": "bytes_sha256", "value": "{{sha256(%d.data)}}" % F}]}, "module": "util:SetVariables", "version": 1,
     "onerror": blocked_on_error(F + 80, "HASH_COMPUTE_FAIL")},
    {"id": F + 2, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
        {"flow": [dict(gate(F + 3, "{{%d.bytes_sha256}}" % (F + 1))[0], filter={"name": "computed sha256 of hosted bytes == registered AND URL pinned + content-addressed",
                       "conditions": [[HOSTING_OFF_OK, {"a": "{{1.data.asset_sha256}}", "b": "", "o": "text:notequal"}, eq("{{%d.bytes_sha256}}" % (F + 1), "{{1.data.asset_sha256}}"), {"a": "{{1.data.media_url}}", "b": "generation=", "o": "text:contain"},
                                       {"a": "{{1.data.media_url}}", "b": "{{1.data.asset_sha256}}", "o": "text:contain"}]]}),
                  gate(F + 3, "")[1],
                  {"id": F + 5, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
                      {"flow": [dict(x, filter={"name": "gate said YES", "conditions": [gate_yes(F + 4)]}) if i == 0 else x
                                for i, x in enumerate(priv_router(F + 20, photo_post, F + 4))]},
                      {"flow": [blocked(F + 6, "GATE_NOT_ELIGIBLE: {{%d.reason}}" % (F + 4), gate_no(F + 4), "gate said NO / unexpected answer -> BLOCKED")]}]}]},
        {"flow": [blocked(F + 7, "ASSET_HASH_MISMATCH_OR_UNPINNED: bytes {{%d.bytes_sha256}} / registered {{ifempty(1.data.asset_sha256; \"NONE\")}}" % (F + 1),
                          [[HOSTING_OFF_BAD], [ne("{{%d.bytes_sha256}}" % (F + 1), "{{1.data.asset_sha256}}")], [eq("{{1.data.asset_sha256}}", "")], [{"a": "{{1.data.media_url}}", "b": "generation=", "o": "text:notcontain"}],
                           [{"a": "{{1.data.media_url}}", "b": "{{1.data.asset_sha256}}", "o": "text:notcontain"}]],
                          "hash mismatch / missing / unpinned -> BLOCKED")]}]}]}
DUE = {"name": "due, privacy level chosen by creator, aki:post id, caption JSON-safe", "conditions": [[
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "0", "o": "number:greater"},
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(now; \"X\")}}", "o": "number:lessorequal"},
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(addHours(now; -6); \"X\")}}", "o": "number:greater"},
    {"a": "{{1.data.gate_content_id}}", "b": "aki:post:", "o": "text:startwith"},
    {"a": "{{1.data.caption}}", "b": "\"", "o": "text:notcontain"}, {"a": "{{1.data.caption}}", "b": "\\", "o": "text:notcontain"}]]}
if TT_VIDEO_MODE == "INBOX":   # privacy + caption are set by the creator in the TikTok app; nothing of them is sent to the API
    DUE = {"name": "due, aki:post id (inbox draft: privacy and caption chosen in the TikTok app)",
           "conditions": [[c for c in DUE["conditions"][0] if "tiktok_privacy_level" not in c["a"] and "caption" not in c["a"]]]}
flow = [
 {"id": 1, "mapper": {"filter": [[{"a": "campaign_id", "b": "aakhri-ishq", "o": "text:equal"}, {"a": "platform_api", "b": "tiktok", "o": "text:equal"},
     {"a": "tiktok_route_enabled", "b": "TRUE", "o": "text:equal"}, {"a": "status", "b": "READY", "o": "text:equal"},
     {"a": "publishable", "b": "TRUE", "o": "text:equal"}, {"a": "approval_status", "b": "APPROVED", "o": "text:equal"}, {"a": "platform_post_id", "o": "notexist"}]]},
  "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": DS}},
 {"id": 49, "filter": DUE, "mapper": {"variables": [{"name": "owner", "value": "{{uuid}}"}]}, "module": "util:SetVariables", "version": 1},
 {"id": 51, "mapper": {"key": "plock:{{1.key}}:a{{1.data.attempt_count + 1}}", "overwrite": False,
   "data": {"campaign_id": "P3_LOCK", "placement_id": "{{1.key}}", "attempt_count": "{{1.data.attempt_count + 1}}", "claim_token": "{{49.owner}}", "updated_at": "{{now}}"}},
  "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": DS}, "onerror": [{"id": 48, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
 logged(upd(50, {"status": "PUBLISHING", "lock_until": "{{addMinutes(now; 45)}}", "attempt_count": "{{1.data.attempt_count + 1}}", "last_error": "", "claim_token": "{{49.owner}}", "attempt_started_at": "{{now}}"}),
        52, "CLAIM_WRITE_FAIL lock=plock:{{1.key}}:a{{1.data.attempt_count + 1}}"),
 {"id": 63, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [video, photo,
   {"flow": [blocked(64, "CHANNEL_VARIANT_MISMATCH: {{1.data.channel}} / {{1.data.format_variant}}",
                     [[{"a": '{{split("tiktok:9x16,tiktok_photo:9x16jpg"; ",")}}', "b": "{{1.data.channel}}:{{1.data.format_variant}}", "o": "array:notcontain"}]],
                     "channel/format variant not an allowed pair -> BLOCKED")]}]}]
bp = {"name": "P3: AKI TikTok %s (route flag per placement; photos BLOCKED) — INACTIVE" % ("Inbox Draft" if TT_VIDEO_MODE == "INBOX" else "Direct Post"), "flow": flow,
      "metadata": {"instant": False, "version": 1, "designer": {"orphans": []}, "scenario": {"dlq": False, "dataloss": False, "maxErrors": 3, "autoCommit": True,
                   "roundtrips": 1, "sequential": True, "confidential": False, "freshVariables": False, "autoCommitTriggerLast": True}}}
from make_error_refs import bind_error_refs
from make_fence import fence_flow
bp['flow'] = fence_flow(bp['flow'], DS, skip_ids=(50,), is_publish=lambda m: m['module'] == 'http:MakeRequest' and '/post/publish/' in m['mapper'].get('url', ''))
bind_error_refs(bp['flow'])   # T2 v3: bare error.* is empty inside handlers
if __name__ == '__main__':
    json.dump(bp, open('P3_blueprint.json', 'w'), ensure_ascii=False)
    print(json.dumps(bp, ensure_ascii=False, separators=(',', ':')))
