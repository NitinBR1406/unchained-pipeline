"""P3L: TikTok post-settings link mailer (INACTIVE, on-demand). Built 2026-10-15 at Nitin's request (TikTok audit, option A).

For every approved TikTok placement due within the next 72 h that has no settings link yet:
  token (data store 168757) -> TikTok creator_info/query (read-only) -> privacy options + nickname
  -> POST /v/tiktok-link on the approval server (same x-publish-apikey keychain as the publish gate)
  -> mail the signed, single-use link to Nitin -> mark the placement tiktok_settings_link_sent_at.
It never posts, never touches status/claim/lock fields and never creates or changes an approval: the page only
stores the creator's choice on an EXISTING publish grant (unpipe.tiktok_settings). Any error is logged to Error_Log
and the placement is simply retried on the next run (no field written).
Text values (caption, nickname, options) go through json:TransformToJSON so quotes/newlines/emoji stay valid JSON."""
import json
import os
from make_error_refs import bind_error_refs

DS, ERR, TOK, KEYCHAIN = 196442, 168812, 168757, 217337
SERVER = "https://unchained-approval.onrender.com"
NOTIFY_TO = os.environ.get("AKI_NOTIFY_EMAIL", "")      # not committed (public repo)
TT = "https://open.tiktokapis.com/v2"


def log(mid, label):
    return {"id": mid, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ERR},
            "mapper": {"overwrite": False, "data": {"post_id": "{{1.key}}", "platform": "{{1.data.channel}}", "scenario": "P3L",
                       "raw_error": "{{ifempty(error.type; \"NO_TYPE\")}}: {{ifempty(error.message; \"NO_DETAIL\")}}", "timestamp": "{{now}}",
                       "error_type": label, "status_code": "{{ifempty(error.statusCode; \"\")}}",
                       "error_message": "{{ifempty(error.message; \"NO_DETAIL\")}}"}}}


def note(mid, label, flt):
    return {"id": mid, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ERR}, "filter": flt,
            "mapper": {"overwrite": False, "data": {"post_id": "{{1.key}}", "platform": "{{1.data.channel}}", "scenario": "P3L", "raw_error": "",
                       "timestamp": "{{now}}", "error_type": label, "status_code": "", "error_message": ""}}}


def to_json(mid, value):
    return {"id": mid, "module": "json:TransformToJSON", "version": 1, "parameters": {}, "mapper": {"object": value}}


ok = lambda a, b: {"a": a, "b": b, "o": "text:equal"}
BODY = ('{"content_id":"{{1.data.gate_content_id}}","platform":"{{1.data.channel}}","caption":{{5.json}},'
        '"privacy_options":{{6.json}},"creator_nickname":{{7.json}}}')
flow = [
    {"id": 1, "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": DS},
     "mapper": {"filter": [[{"a": "campaign_id", "b": "aakhri-ishq", "o": "text:equal"}, {"a": "platform_api", "b": "tiktok", "o": "text:equal"},
                            {"a": "approval_status", "b": "APPROVED", "o": "text:equal"}, {"a": "platform_post_id", "o": "notexist"},
                            {"a": "tiktok_settings_link_sent_at", "o": "notexist"}]],
                "sort": [{"key": "scheduled_at_epoch", "order": 1}]}},
    {"id": 2, "module": "datastore:GetRecord", "version": 1, "parameters": {"datastore": TOK}, "mapper": {"key": "main", "returnWrapped": False},
     "filter": {"name": "due within the next 72 h, aki:post id", "conditions": [[
         {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(now; \"X\")}}", "o": "number:greater"},
         {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(addHours(now; 72); \"X\")}}", "o": "number:lessorequal"},
         {"a": "{{1.data.gate_content_id}}", "b": "aki:post:", "o": "text:startwith"}]]},
     "onerror": [log(92, "TT_TOKEN_READ_FAIL"), {"id": 93, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
    {"id": 3, "module": "http:MakeRequest", "version": 4, "parameters": {"authenticationType": "noAuth"},
     "mapper": {"url": TT + "/post/publish/creator_info/query/", "method": "post", "headers": [
         {"name": "Authorization", "value": "Bearer {{2.access_token}}"}, {"name": "Content-Type", "value": "application/json; charset=UTF-8"}],
         "contentType": "json", "inputMethod": "jsonString", "jsonStringBodyContent": "{}", "parseResponse": True, "shareCookies": False,
         "allowRedirects": False, "stopOnHttpError": True, "requestCompressedContent": False, "timeout": 60},
     "onerror": [log(94, "TT_CREATOR_INFO_FAIL"), {"id": 95, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
    {"id": 4, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [
        {"flow": [
            dict(to_json(5, "{{1.data.caption}}"), filter={"name": "creator_info ok", "conditions": [[ok("{{3.data.error.code}}", "ok")]]}),
            to_json(6, "{{3.data.data.privacy_level_options}}"),
            to_json(7, "{{ifempty(3.data.data.creator_nickname; \"\")}}"),
            {"id": 8, "module": "http:ActionSendDataAPIKeyAuth", "version": 3, "parameters": {"auth": KEYCHAIN, "handleErrors": True},
             "mapper": {"qs": [], "url": SERVER + "/v/tiktok-link", "data": BODY, "gzip": True, "method": "post", "headers": [], "useMtls": False,
                        "bodyType": "raw", "contentType": "application/json", "serializeUrl": False, "shareCookies": False, "parseResponse": False,
                        "followRedirect": False, "useQuerystring": False, "followAllRedirects": False, "rejectUnauthorized": True},
             "onerror": [log(96, "TT_LINK_HTTP_FAIL"), {"id": 97, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
            {"id": 9, "module": "json:ParseJSON", "version": 1, "mapper": {"json": "{{toString(8.data)}}"},
             "onerror": [log(98, "TT_LINK_PARSE_FAIL"), {"id": 99, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
            {"id": 10, "module": "builtin:BasicRouter", "version": 1, "mapper": {}, "routes": [
                {"flow": ([{"id": 11, "module": "email:ActionSendMeEmail", "version": 7, "parameters": {},
                            "filter": {"name": "link created", "conditions": [[ok("{{if(9.ok = true; \"YES\"; \"NO\")}}", "YES"), {"a": "{{9.path}}", "b": "/v/tiktok?token=", "o": "text:startwith"}]]},
                            "mapper": {"to": NOTIFY_TO, "subject": "TikTok-instellingen kiezen: {{1.key}}",
                                       "html": "<p>Kies voor <b>{{1.key}}</b> (gepland {{formatDate(parseDate(1.data.scheduled_at_epoch; \"X\"); \"DD-MM-YYYY HH:mm\"; \"Europe/Amsterdam\")}}) "
                                               "wie de video mag zien, of reacties/Duet/Stitch aan mogen, en geef toestemming.</p>"
                                               "<p><a href=\"" + SERVER + "{{9.path}}&approver=nitin\">Instellingen kiezen</a> (eenmalig, 24 uur geldig)</p>"
                                               "<p>Zonder keuze wordt deze TikTok-post niet direct geplaatst.</p>"},
                            "onerror": [log(100, "TT_LINK_MAIL_FAIL"), {"id": 101, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
                           {"id": 12, "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS},
                            "mapper": {"key": "{{1.key}}", "data": {"tiktok_settings_link_sent_at": "{{now}}"}, "upsert": False, "overwriteArrays": False},
                            "onerror": [log(102, "TT_LINK_MARK_FAIL")]}]) if NOTIFY_TO else
                         [note(11, "TT_LINK_NOT_SENT_NO_NOTIFY_ADDRESS", {"name": "link created", "conditions": [[ok("{{if(9.ok = true; \"YES\"; \"NO\")}}", "YES")]]})]},
                {"flow": [note(13, "TT_LINK_REFUSED reason={{ifempty(9.reason; \"NONE\")}}",
                               {"name": "link refused", "conditions": [[{"a": "{{if(9.ok = true; \"YES\"; \"NO\")}}", "b": "YES", "o": "text:notequal"}]]})]}]}]},
        {"flow": [note(14, "TT_CREATOR_INFO_NOT_OK code={{ifempty(3.data.error.code; \"NONE\")}}",
                       {"name": "creator_info not ok", "conditions": [[{"a": "{{3.data.error.code}}", "b": "ok", "o": "text:notequal"}]]})]}]},
]
bp = {"name": "P3L: AKI TikTok settings link mailer (creator_info -> signed link -> mail) — INACTIVE", "flow": bind_error_refs(flow),
      "metadata": {"instant": False, "version": 1, "designer": {"orphans": []},
                   "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True, "autoCommitTriggerLast": True, "sequential": True,
                                "confidential": False, "dataloss": False, "dlq": False, "freshVariables": False}}}
json.dump(bp, open("P3L_blueprint.json", "w"), ensure_ascii=False)
print(json.dumps(bp, separators=(",", ":")))
