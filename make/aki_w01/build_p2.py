"""P2: AKI Campaign Publisher (placement-level, gated). INACTIVE. Version f2 (2026-10-14; e + error refs, ownership fences, IG hosting register).
One record = one channel placement (AKI_Placements 196442). Selection: campaign_id=aakhri-ishq AND publishable=TRUE AND
approval_status=APPROVED AND no platform_post_id AND (READY, or FAILED with attempt_count<3); due (<=now, <6h old); not locked.

Order per placement (fail-closed at every step):
 1. EXCLUSIVE LOCK first: insert-only record plock:<placement>:a<attempt+1> (Make data-store keys are unique; a duplicate
    insert errors -> builtin:Ignore drops the bundle). Only the lock winner continues; a stale bundle can no longer
    overwrite a record that another execution already moved on.
 2. CLAIM: status PUBLISHING, attempt+1, claim_token = per-bundle {{uuid}} owner token (module 49), attempt_started_at, lock_until +45 min. Never re-selected
    (selection is READY/FAILED only). The lock duration is NOT the safety mechanism: every later status write and the upload
    itself are fenced on ownership (claim_token + attempt + PUBLISHING re-read, see guarded()/wb()).
 3. FETCH the exact bytes that will be published: Drive download (FB/YT) or GET of the hosted media_url (Instagram).
 4. HASH: Make computes sha256 over the fetched bytes. Required: computed == registered asset_sha256; Drive routes also
    require Drive's sha256Checksum == registered; Instagram requires media_url to be exactly the signed URL of the object
    version in the placement's hosting_register (host, bucket, object path, one generation, V4 signature, not expiring).
    Any mismatch / missing hash -> BLOCKED (no gate call, no upload). If Make cannot hash binary data correctly, the
    computed value differs (or the hash step errors -> BLOCKED + log): no placement can pass by accident.
 5. GATE with the COMPUTED hash (not the record value): a different file invalidates the approval.
 6. UPLOAD the same fetched buffer (FB/YT) / the same pinned URL (IG). Errors -> OUTCOME_UNKNOWN unless definitely rejected.
TikTok: no API call (BLOCKED)."""
import json
DS, ERR, KEYCHAIN = 196442, 168812, 217337
IG, FB, YT = 14369479, 14363628, 14374103
GDRIVE = 14383570   # google-restricted Drive connection (Shared Drive 'Unchained Nitin — Master')
VARIANT = {'instagram_reels': '9x16', 'facebook_reels': '9x16', 'youtube_shorts': '9x16', 'youtube_hero': '9x16',
           'instagram_feed': '4x5', 'facebook_feed': '4x5'}
API = {'instagram_reels': 'instagram', 'instagram_feed': 'instagram', 'facebook_reels': 'facebook', 'facebook_feed': 'facebook',
       'youtube_shorts': 'youtube', 'youtube_hero': 'youtube'}


def upd(mid, data, flt=None):
    m = {"id": mid, "mapper": {"key": "{{1.key}}", "data": data, "upsert": False, "overwriteArrays": False},
         "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS}}
    if flt: m["filter"] = flt
    return m
# OWNERSHIP FENCE (f2): every status write after the claim first re-reads the record and only writes when this execution
# still owns the claim (claim_token = own owner token, same attempt, status PUBLISHING). A stale execution (e.g. one that
# outlived its lock while a human/R1 already moved the placement on) can therefore not overwrite another attempt's state.
# Lock records are insert-only per attempt and never deleted, so no execution can release another execution's lock.
# Residual: Make data stores have no compare-and-swap; between the re-read and the write there is a short window.
OWN = "{{49.owner}}"   # per-bundle owner token ({{uuid}}, module 49); {{var.execution.id}} is EMPTY in Make runs (T-lock v1)
GUARD = 1000
def mine(g):
    return [eq("{{%d.claim_token}}" % g, OWN), eq("{{%d.status}}" % g, "PUBLISHING"),
            {"a": "{{%d.attempt_count}}" % g, "b": "{{1.data.attempt_count + 1}}", "o": "number:equal"}]
def not_mine(g):
    return [[ne("{{%d.claim_token}}" % g, OWN)], [ne("{{%d.status}}" % g, "PUBLISHING")],
            [{"a": "{{%d.attempt_count}}" % g, "b": "{{1.data.attempt_count + 1}}", "o": "number:notequal"}]]
def getrec(mid, flt=None):
    m = {"id": mid, "mapper": {"key": "{{1.key}}", "returnWrapped": False}, "module": "datastore:GetRecord", "version": 1, "parameters": {"datastore": DS}}
    if flt: m["filter"] = flt
    return m
def guarded(u):
    """[GetRecord, UpdateRecord only if this execution still owns the claim]. The update's routing filter moves to the read."""
    g = u["id"] + GUARD
    u = dict(u); flt = u.pop("filter", None)
    return [getrec(g, flt), dict(u, filter={"name": "this execution still owns the claim (token, attempt, PUBLISHING)", "conditions": [mine(g)]})]
def errdata(label):
    # bare error.* is rewritten to <failed module>.error.* by bind_error_refs; ifempty keeps a missing detail from breaking the handler
    return {"post_id": "{{1.key}}", "platform": "{{1.data.channel}}", "scenario": "P2",
            "raw_error": "{{ifempty(error.type; \"NO_TYPE\")}}: {{ifempty(error.message; \"NO_DETAIL\")}}",
            "timestamp": "{{now}}", "error_type": label, "status_code": "{{ifempty(error.statusCode; \"\")}}",
            "error_message": "{{ifempty(error.message; \"NO_DETAIL\")}}"}
def log(mid, label):
    return {"id": mid, "mapper": {"data": errdata(label), "overwrite": False}, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ERR}}
def note(mid, label, flt=None):   # non-error event (no error object): logged without error references
    m = {"id": mid, "mapper": {"data": {"post_id": "{{1.key}}", "platform": "{{1.data.channel}}", "scenario": "P2", "raw_error": "",
         "timestamp": "{{now}}", "error_type": label, "status_code": "", "error_message": ""}, "overwrite": False},
         "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ERR}}
    if flt: m["filter"] = flt
    return m
ATT = "a={{1.data.attempt_count + 1}}"
def fail(mid, label):   # nothing was published: FAILED (retryable, max 3)
    return [log(mid + 1, label + " " + ATT)] + guarded(upd(mid, {"status": "FAILED", "last_error": label + ": {{ifempty(error.message; \"NO_DETAIL\")}}",
                                                              "last_error_at": "{{now}}", "lock_until": ""}))
# T2 v3 (2026-10-14): Make reports DNS failure (request never sent) AND HTTP 404 (request sent, answered) both as DataError,
# so DataError at a publish call does not prove "nothing was published" -> it stays OUTCOME_UNKNOWN (R1 + human).
DEFINITE = "InvalidAccessTokenError,InvalidConfigurationError,AccountValidationError"
CLASSIFY = '{{if(contains(split("' + DEFINITE + '"; ","); ifempty(error.type; "UNKNOWN")); "FAILED"; "OUTCOME_UNKNOWN")}}'
def uncertain(mid, label):
    # Error AT the platform publish call. Exactly-named definite rejections (auth / config) -> FAILED.
    # Everything else MAY have published -> OUTCOME_UNKNOWN: never auto-retried, lock kept; R1 reconciles.
    # The log is written first and unconditionally; the status write is fenced.
    return [log(mid - 2, label + "/" + CLASSIFY + " " + ATT)] + guarded(
        upd(mid, {"status": CLASSIFY, "last_error": label + ": {{ifempty(error.type; \"NO_TYPE\")}} {{ifempty(error.message; \"NO_DETAIL\")}}",
                  "last_error_at": "{{now}}"}))
def ok(mid, pid_expr, url_expr, log_id):
    # Upload succeeded. Written back only while this execution owns the claim (see wb()). If writing the id back fails,
    # the record stays PUBLISHING (never re-selected, never re-uploaded) and the platform id + attempt are logged;
    # R1 verifies that id on the platform (proven match).
    m = upd(mid, {"status": "PUBLISHED", "platform_post_id": pid_expr, "platform_url": url_expr, "published_at": "{{now}}", "lock_until": "", "last_error": "",
                  "published_via": "AUTO_P2", "m24h_status": "PENDING", "m72h_status": "PENDING", "m7d_status": "PENDING"})
    if log_id is not None:
        m["onerror"] = [dict(log(log_id, "WRITEBACK_FAIL_AFTER_UPLOAD " + ATT + " id=" + pid_expr), id=log_id)]
    return m
def wb(b, okm, pid_expr, extra=()):
    """Write-back fence: re-read; own claim -> ok (+extra); claim lost -> log the platform id, never overwrite."""
    g = b + 26
    return [getrec(g), {"id": b + 27, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
        {"flow": [dict(okm, filter={"name": "this execution still owns the claim", "conditions": [mine(g)]})] + list(extra)},
        {"flow": [note(b + 28, "WRITEBACK_SKIPPED_CLAIM_LOST " + ATT + " id=" + pid_expr + " owner={{ifempty(%d.claim_token; \"NONE\")}}" % g,
                       {"name": "claim lost", "conditions": not_mine(g)})]}]}]
def blocked_on_error(mid, label):   # deterministic failure (e.g. hash function error): BLOCKED + log, never a silent stop
    return [log(mid, label + " " + ATT)] + guarded(upd(mid + 1, {"status": "BLOCKED", "last_error": label + ": {{ifempty(error.message; \"NO_DETAIL\")}}",
                                                                  "last_error_at": "{{now}}", "lock_until": ""}))
def eq(a, b): return {"a": a, "b": b, "o": "text:equal"}
def ne(a, b): return {"a": a, "b": b, "o": "text:notequal"}

GATE_URL = "https://unchained-approval.onrender.com/v/publish-eligibility"
def gate(mid, sha_expr, flt):
    body = ('{"content_id":"{{1.data.gate_content_id}}","platform":"{{1.data.channel}}","target_account":"{{1.data.target_account}}",'
            '"asset_sha256":"' + sha_expr + '","packaging_sha256":"{{1.data.packaging_sha256}}","schedule_version":"{{1.data.schedule_version}}",'
            '"scheduled_at_epoch":{{1.data.scheduled_at_epoch}}}')
    return [{"id": mid, "filter": flt, "mapper": {"qs": [], "url": GATE_URL, "data": body, "gzip": True, "method": "post", "headers": [], "useMtls": False,
             "bodyType": "raw", "contentType": "application/json", "serializeUrl": False, "shareCookies": False, "parseResponse": False,
             "followRedirect": True, "useQuerystring": False, "followAllRedirects": False, "rejectUnauthorized": True},
             "module": "http:ActionSendDataAPIKeyAuth", "version": 3, "parameters": {"auth": KEYCHAIN, "handleErrors": True},
             "onerror": fail(mid + 30, "GATE_HTTP_FAIL")},
            {"id": mid + 1, "mapper": {"json": "{{toString(%d.data)}}" % mid}, "module": "json:ParseJSON", "version": 1,
             "onerror": fail(mid + 32, "GATE_PARSE_FAIL")}]
def eligible(p): return [eq("{{%d.reason}}" % p, "VALID_PUBLISH_APPROVAL"), eq('{{if(%d.eligible = true; "EOK"; "ENO")}}' % p, "EOK")]
def not_eligible(p): return [[ne("{{%d.reason}}" % p, "VALID_PUBLISH_APPROVAL")], [ne('{{if(%d.eligible = true; "EOK"; "ENO")}}' % p, "EOK")]]

# INSTAGRAM HOSTING (f2): Meta fetches the media itself, so P2 only accepts a media_url that is exactly the signed URL of the
# object version recorded in the placement's hosting register (field hosting_register, JSON written by ig_stage.py):
#   {"bucket","object","generation","sha256","expires_epoch"}.  No free-text checks on the URL: host, bucket, object path,
#   one unambiguous generation equal to the register, a V4 signature, no fragment/userinfo, not expiring within 15 min.
# IG_BUCKET stays UNCONFIGURED until Nitin approves hosting and names the private bucket -> until then every IG route BLOCKS.
IG_BUCKET = "UNCONFIGURED"
IG_HOST = "https://storage.googleapis.com/"
EXT = {'instagram_reels': 'mp4', 'instagram_feed': 'jpg'}
def pat(a, b): return {"a": a, "b": b, "o": "text:pattern"}
def npat(a, b): return {"a": a, "b": b, "o": "text:notpattern"}
def hosting_checks(ch, r):
    obj = "aki-ig-staging/{{1.data.asset_sha256}}.%s" % EXT[ch]
    url = "{{1.data.media_url}}"
    ok_ = [ne(IG_BUCKET, "UNCONFIGURED"), eq("{{%d.bucket}}" % r, IG_BUCKET), eq("{{%d.object}}" % r, obj),
           ne("{{1.data.asset_sha256}}", ""), eq("{{%d.sha256}}" % r, "{{1.data.asset_sha256}}"),
           pat("{{%d.generation}}" % r, "^[0-9]{1,20}$"),
           {"a": url, "b": IG_HOST + IG_BUCKET + "/" + obj + "?", "o": "text:startwith"},
           pat(url, "[?&]generation={{%d.generation}}(&|$)" % r), npat(url, "generation=.*generation="),
           pat(url, "[?&]X-Goog-Algorithm=GOOG4-RSA-SHA256(&|$)"), pat(url, "[?&]X-Goog-Signature=[0-9a-f]{64,}(&|$)"),
           pat(url, "[?&]X-Goog-Credential=[^&]+"), pat(url, "[?&]X-Goog-Expires=[0-9]+(&|$)"), npat(url, "[#@\\s]"),
           {"a": "{{%d.expires_epoch}}" % r, "b": "{{formatDate(addMinutes(now; 15); \"X\")}}", "o": "number:greater"}]
    inverse = {"text:equal": "text:notequal", "text:notequal": "text:equal", "text:pattern": "text:notpattern", "text:notpattern": "text:pattern",
               "text:startwith": "text:notstartwith", "number:greater": "number:lessorequal"}
    bad = [[dict(c, o=inverse[c["o"]])] for c in ok_]
    return ok_, bad

def media_route(b, ch, kind, upload, done):
    """b..b+39 ids (+1000 for ownership re-reads). kind 'drive' (FB/YT: private Drive download) or 'url' (IG: registered hosted object)."""
    sel = {"name": "%s (api %s, variant %s)" % (ch, API[ch], VARIANT[ch]), "conditions": [[eq("{{1.data.platform_api}}", API[ch]), eq("{{1.data.channel}}", ch),
                                                                                          eq("{{1.data.format_variant}}", VARIANT[ch])]]}
    if kind == 'drive':
        fetch = {"id": b, "filter": sel, "mapper": {"select": "map", "file": "{{1.data.drive_file_id}}", "formatDocuments": "application/pdf",
                 "formatSpreadsheets": "text/csv", "formatPresentations": "application/pdf", "formatDrawings": "image/jpeg"},
                 "module": "google-drive:getAFile", "version": 4, "parameters": {"__IMTCONN__": GDRIVE}, "onerror": fail(b + 37, "DRIVE_DOWNLOAD_FAIL")}
        meta = "{{%d.sha256Checksum}}" % b
    else:
        fetch = {"id": b, "mapper": {"url": "{{1.data.media_url}}", "method": "get", "timeout": 300, "shareCookies": False,
                 "parseResponse": False, "allowRedirects": False, "stopOnHttpError": True, "requestCompressedContent": False},
                 "module": "http:MakeRequest", "version": 4, "parameters": {"authenticationType": "noAuth"}, "onerror": fail(b + 37, "MEDIA_URL_FETCH_FAIL")}
        meta = "URL"
    hashv = {"id": b + 1, "mapper": {"variables": [{"name": "bytes_sha256", "value": "{{sha256(%d.data)}}" % b},
                                                    {"name": "source_meta", "value": meta}]}, "module": "util:SetVariables", "version": 1,
             "onerror": blocked_on_error(b + 20, "HASH_COMPUTE_FAIL")}
    v = "{{%d.bytes_sha256}}" % (b + 1)
    good = [ne("{{1.data.asset_sha256}}", ""), eq(v, "{{1.data.asset_sha256}}")]
    bad = [[ne(v, "{{1.data.asset_sha256}}")], [eq("{{1.data.asset_sha256}}", "")]]
    if kind == 'drive':
        good.append(eq("{{%d.sha256Checksum}}" % b, "{{1.data.asset_sha256}}"))
        bad.insert(1, [ne("{{ifempty(%d.sha256Checksum; \"NONE\")}}" % b, "{{1.data.asset_sha256}}")])
        name = "computed bytes sha256 == registered AND Drive sha256Checksum == registered"
    else:
        name = "computed sha256 of the bytes served by the registered object version == registered"
    g = gate(b + 3, v, {"name": name, "conditions": [good]})
    fence = getrec(b + 23, {"name": "gate: eligible and VALID_PUBLISH_APPROVAL", "conditions": [eligible(b + 4)]})
    up = dict(upload, filter={"name": "this execution still owns the claim -> upload", "conditions": [mine(b + 23)]})
    lost = note(b + 25, "CLAIM_LOST_BEFORE_UPLOAD " + ATT + " owner={{ifempty(%d.claim_token; \"NONE\")}}" % (b + 23),
                {"name": "claim lost -> no upload", "conditions": not_mine(b + 23)})
    blocked_gate = guarded(upd(b + 9, {"status": "BLOCKED", "last_error": "GATE_NOT_ELIGIBLE: {{%d.reason}}" % (b + 4), "last_error_at": "{{now}}", "lock_until": ""},
                               flt={"name": "gate said NO / unexpected answer -> BLOCKED", "conditions": not_eligible(b + 4)}))
    blocked_hash = guarded(upd(b + 11, {"status": "BLOCKED", "last_error": "ASSET_HASH_MISMATCH: bytes " + v + " / source " + "{{%d.source_meta}}" % (b + 1)
                                + " / registered {{ifempty(1.data.asset_sha256; \"NONE\")}}", "last_error_at": "{{now}}", "lock_until": ""},
                               flt={"name": "hash mismatch / missing -> BLOCKED, no gate, no upload", "conditions": bad}))
    body = [fetch, hashv, {"id": b + 2, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
        {"flow": g + [{"id": b + 5, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
            {"flow": [fence, {"id": b + 24, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
                {"flow": [up] + done}, {"flow": [lost]}]}]},
            {"flow": blocked_gate}]}]},
        {"flow": blocked_hash}]}]
    if kind == 'drive':
        return {"flow": body}
    reg = {"id": b + 15, "filter": sel, "mapper": {"json": "{{ifempty(1.data.hosting_register; \"NO_REGISTER\")}}"}, "module": "json:ParseJSON",
           "version": 1, "onerror": blocked_on_error(b + 16, "HOSTING_REGISTER_MISSING_OR_INVALID")}
    okc, badc = hosting_checks(ch, b + 15)
    body[0] = dict(fetch, filter={"name": "media_url is exactly the signed URL of the registered object version", "conditions": [okc]})
    blocked_url = guarded(upd(b + 18, {"status": "BLOCKED", "last_error": "HOSTING_URL_NOT_REGISTERED_OBJECT_VERSION (host/bucket/object/generation/signature/expiry)",
                                       "last_error_at": "{{now}}", "lock_until": ""},
                              flt={"name": "media_url does not match the hosting register -> BLOCKED, no fetch", "conditions": badc}))
    return {"flow": [reg, {"id": b + 19, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [{"flow": body}, {"flow": blocked_url}]}]}

IGR, IGF, FBR, FBF, YTS, YTH = 300, 340, 380, 420, 460, 500
def ig_done(b):
    pid = "{{%d.id}}" % (b + 6)
    return wb(b, ok(b + 8, pid, "", b + 22), pid,
              [{"id": b + 7, "mapper": {"id": pid}, "module": "instagram-business:GetMedia", "version": 1, "parameters": {"__IMTCONN__": IG},
                "onerror": [{"id": b + 14, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
               upd(b + 29, {"platform_url": "{{%d.permalink}}" % (b + 7)},
                   {"name": "still own claim (same read as the write-back)", "conditions": [mine(b + 26)]})])
routes = [
 media_route(IGR, "instagram_reels", "url",
   {"id": IGR + 6, "mapper": {"caption": "{{1.data.caption}}", "accountId": "17841457677776171", "video_url": "{{1.data.media_url}}", "share_to_feed": True},
    "module": "instagram-business:CreateAReelPost", "version": 1, "parameters": {"__IMTCONN__": IG}, "onerror": uncertain(IGR + 12, "IG_REEL_FAIL")},
   ig_done(IGR)),
 media_route(IGF, "instagram_feed", "url",
   {"id": IGF + 6, "mapper": {"caption": "{{1.data.caption}}", "accountId": "17841457677776171", "image_url": "{{1.data.media_url}}"},
    "module": "instagram-business:CreatePostPhoto", "version": 1, "parameters": {"__IMTCONN__": IG}, "onerror": uncertain(IGF + 12, "IG_PHOTO_FAIL")},
   ig_done(IGF)),
 media_route(FBR, "facebook_reels", "drive",
   {"id": FBR + 6, "mapper": {"data": "{{%d.data}}" % FBR, "fileName": "{{1.data.file_name}}", "page_id": "839373332878305", "description": "{{1.data.caption}}",
    "uploadMethod": "data"}, "module": "facebook-pages:uploadAReel", "version": 6, "parameters": {"__IMTCONN__": FB}, "onerror": uncertain(FBR + 12, "FB_REEL_FAIL")},
   wb(FBR, ok(FBR + 8, "{{%d.video_id}}" % (FBR + 6), "https://www.facebook.com/reel/{{%d.video_id}}" % (FBR + 6), FBR + 22), "{{%d.video_id}}" % (FBR + 6))),
 media_route(FBF, "facebook_feed", "drive",
   {"id": FBF + 6, "mapper": {"data": "{{%d.data}}" % FBF, "message": "{{1.data.caption}}", "page_id": "839373332878305", "fileName": "{{1.data.file_name}}"},
    "module": "facebook-pages:UploadPhoto", "version": 6, "parameters": {"__IMTCONN__": FB}, "onerror": uncertain(FBF + 12, "FB_PHOTO_FAIL")},
   wb(FBF, ok(FBF + 8, "{{ifempty(%d.post_id; %d.id)}}" % (FBF + 6, FBF + 6), "https://www.facebook.com/{{ifempty(%d.post_id; %d.id)}}" % (FBF + 6, FBF + 6), FBF + 22),
      "{{ifempty(%d.post_id; %d.id)}}" % (FBF + 6, FBF + 6))),
 media_route(YTS, "youtube_shorts", "drive",
   {"id": YTS + 6, "mapper": {"data": "{{%d.data}}" % YTS, "title": "{{1.data.title}}", "fileName": "{{1.data.file_name}}", "categoryId": "10",
    "description": "{{1.data.caption}}", "privacyStatus": "public"}, "module": "youtube:ActionUploadVideo", "version": 3, "parameters": {"account": YT},
    "onerror": uncertain(YTS + 12, "YT_SHORT_FAIL")},
   wb(YTS, ok(YTS + 8, "{{%d.id}}" % (YTS + 6), "https://youtube.com/shorts/{{%d.id}}" % (YTS + 6), YTS + 22), "{{%d.id}}" % (YTS + 6))),
 media_route(YTH, "youtube_hero", "drive",
   {"id": YTH + 6, "mapper": {"data": "{{%d.data}}" % YTH, "title": "{{1.data.title}}", "fileName": "{{1.data.file_name}}", "categoryId": "10",
    "description": "{{1.data.caption}}", "privacyStatus": "public"}, "module": "youtube:ActionUploadVideo", "version": 3, "parameters": {"account": YT},
    "onerror": uncertain(YTH + 12, "YT_FULL_FAIL")},
   wb(YTH, ok(YTH + 8, "{{%d.id}}" % (YTH + 6), "https://www.youtube.com/watch?v={{%d.id}}" % (YTH + 6), YTH + 22), "{{%d.id}}" % (YTH + 6))),
 {"flow": guarded(upd(160, {"status": "BLOCKED", "last_error": "TIKTOK_DIRECT_POST_UNAVAILABLE: app not audited / sandbox token expired; no API call made",
                     "last_error_at": "{{now}}", "lock_until": ""},
               flt={"name": "platform_api tiktok (video + photo) -> blocked (no call)", "conditions": [[eq("{{1.data.platform_api}}", "tiktok")]]}))},
 {"flow": guarded(upd(170, {"status": "BLOCKED", "last_error": "CHANNEL_VARIANT_MISMATCH: api {{1.data.platform_api}} / channel {{1.data.channel}} / variant {{1.data.format_variant}}",
                     "last_error_at": "{{now}}", "lock_until": ""},
               flt={"name": "api/channel/format variant not an allowed triple -> BLOCKED", "conditions": [[
                   ne("{{1.data.platform_api}}", "tiktok"),
                   {"a": '{{split("' + ",".join("%s:%s:%s" % (API[c], c, v) for c, v in VARIANT.items()) + '"; ",")}}', "b": "{{1.data.platform_api}}:{{1.data.channel}}:{{1.data.format_variant}}", "o": "array:notcontain"}]]}))},
]
DUE = {"name": "due now (<=now, not >6h stale), IG has media URL (others: Drive binary), not locked, aki:post: id", "conditions": [[
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "0", "o": "number:greater"},
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(now; \"X\")}}", "o": "number:lessorequal"},
    {"a": "{{1.data.scheduled_at_epoch}}", "b": "{{formatDate(addHours(now; -6); \"X\")}}", "o": "number:greater"},
    {"a": "{{if(1.data.platform_api = \"instagram\"; ifempty(1.data.media_url; \"EMPTY\"); \"DRIVE_BINARY\")}}", "b": "EMPTY", "o": "text:notequal"},
    {"a": "{{if(1.data.lock_until; formatDate(1.data.lock_until; \"X\"); 0)}}", "b": "{{formatDate(now; \"X\")}}", "o": "number:lessorequal"},
    {"a": "{{1.data.gate_content_id}}", "b": "aki:post:", "o": "text:startwith"}]]}
flow = [
 {"id": 1, "mapper": {"sort": [{"key": "scheduled_at_epoch", "order": 1}], "filter": [
    [eq("campaign_id", "aakhri-ishq"), eq("status", "READY"), eq("publishable", "TRUE"), eq("approval_status", "APPROVED"), {"a": "platform_post_id", "o": "notexist"}],
    [eq("campaign_id", "aakhri-ishq"), eq("status", "FAILED"), eq("publishable", "TRUE"), eq("approval_status", "APPROVED"), {"a": "platform_post_id", "o": "notexist"},
     {"a": "attempt_count", "b": "3", "o": "number:less"}]]},
  "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": DS}},
 # 0. OWNER TOKEN for this bundle (unique; written into lock + claim; every later write/upload is fenced on it)
 {"id": 49, "filter": DUE, "mapper": {"variables": [{"name": "owner", "value": "{{uuid}}"}]}, "module": "util:SetVariables", "version": 1},
 # 1. EXCLUSIVE LOCK (insert-only key, unique in Make data stores; duplicate -> Ignore drops this bundle)
 {"id": 51, "mapper": {"key": "plock:{{1.key}}:a{{1.data.attempt_count + 1}}", "overwrite": False,
   "data": {"campaign_id": "P2_LOCK", "placement_id": "{{1.key}}", "attempt_count": "{{1.data.attempt_count + 1}}",
            "claim_token": OWN, "updated_at": "{{now}}"}},
  "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": DS},
  "onerror": [{"id": 48, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
 # 2. CLAIM (only the lock winner reaches this)
 upd(50, {"status": "PUBLISHING", "lock_until": "{{addMinutes(now; 45)}}", "attempt_count": "{{1.data.attempt_count + 1}}", "last_error": "",
          "claim_token": OWN, "attempt_started_at": "{{now}}"}) | {"onerror": [dict(log(52, "CLAIM_WRITE_FAIL lock=plock:{{1.key}}:a{{1.data.attempt_count + 1}}"), id=52)]},
 {"id": 70, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": routes}]
bp = {"name": "P2: AKI Campaign Publisher (placement-level, gated) — INACTIVE", "flow": flow,
      "metadata": {"instant": False, "version": 1, "designer": {"orphans": []}, "scenario": {"dlq": False, "dataloss": False, "maxErrors": 3, "autoCommit": True,
                   "roundtrips": 1, "sequential": True, "confidential": False, "freshVariables": False, "autoCommitTriggerLast": True}}}
from make_error_refs import bind_error_refs
bind_error_refs(bp['flow'])   # T2 v3: bare error.* is empty inside handlers
if __name__ == '__main__':
    json.dump(bp, open('P2_blueprint.json', 'w'), ensure_ascii=False)
    print(len(json.dumps(bp)))
