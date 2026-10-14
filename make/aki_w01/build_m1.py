"""M1 v2: AKI Metrics Collector (INACTIVE, on-demand) — 24h / 72h / 7d per PUBLISHED placement, restart-safe.

Windows are anchored on the REAL published_at written by P2 (never on the planned time) and processed strictly in order.
For the first window that is not finished:
  age <  planned                      -> NOT_DUE (nothing happens)
  planned <= age <= planned + tol     -> ON_TIME  : platform values fetched, rows written
  planned + tol < age < next window   -> DELAYED  : lifetime values at the ACTUAL elapsed time; labelled DELAYED, never as the window value
  age >= next window planned          -> MISSED   : one MISSED row, no value; the next window is handled on a later run
  (tol: 24h +2h, 72h +6h, 7d +12h). All supported sources are lifetime counters; no platform history is used.
Dedup / restart: deterministic observation_id = <placement>:<window>:<metric>. Before writing, M1 reads column A of the ledger
once and only appends ids that are not there yet. A crashed or partial run is resumed by the next run after the 45-min
metrics lock expires: only the missing rows are added. Window status is written to the placement (m24h_status/...).
API error -> one ERROR row (unique id per run), window status ERROR (retried while still ON_TIME/DELAYED, later MISSED).
Unsupported metrics -> UNAVAILABLE + reason, never 0. Account growth is never attributed to a post."""
import json
import os
FBC = 14363628
# ledger spreadsheet id is not committed (public repo): export AKI_M1_SHEET_ID before building the deployable blueprint
SS = os.environ.get('AKI_M1_SHEET_ID', 'SET_AKI_M1_SHEET_ID')
DS, TAB, GS, IG, YT = 196442, 'Untitled', 14383319, 14369479, 14374103
DONE = 'DONE_ON_TIME,DONE_DELAYED,DONE_UNAVAILABLE,MISSED'
ISO = '"YYYY-MM-DDTHH:mm:ss[Z]"'

def done(f):  # true if window field finished
    return 'contains(split("%s"; ","); ifempty(1.data.%s; "NONE"))' % (DONE, f)

def mark(mid, status_expr, extra=None):
    d = {f: '{{if(2.window = "%s"; %s; 1.data.%s)}}' % (w, status_expr, f) for w, f in (('24h', 'm24h_status'), ('72h', 'm72h_status'), ('7d', 'm7d_status'))}
    d.update({f: '{{if(2.window = "%s"; now; 1.data.%s)}}' % (w, f) for w, f in (('24h', 'm24h_at'), ('72h', 'm72h_at'), ('7d', 'm7d_at'))})
    d['metrics_lock_until'] = ''
    if extra: d.update(extra)
    return {"id": mid, "mapper": {"key": "{{1.key}}", "data": d, "upsert": False, "overwriteArrays": False},
            "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS}}

def row(mid, obs, metric, definition, value, unit, avail, reason, period, source, err='', dedupe=True):
    v = {"0": obs, "1": "{{1.key}}", "2": "{{1.data.post_id}}", "3": "{{1.data.channel}}", "4": "{{1.data.platform_post_id}}",
         "5": "{{2.window}}", "6": "{{3.wstatus}}", "7": "{{formatDate(3.planned_at; %s)}}" % ISO, "8": "{{formatDate(now; %s)}}" % ISO,
         "9": "{{round(2.age_h * 10) / 10}}", "10": metric, "11": definition, "12": value, "13": unit, "14": avail, "15": reason, "16": period,
         "17": "{{formatDate(1.data.published_at; %s)}}" % ISO, "18": "{{formatDate(now; %s)}}" % ISO, "19": source, "20": "{{2.run}}", "21": err}
    m = {"id": mid, "mapper": {"from": "drive", "mode": "select", "values": v, "sheetId": TAB, "spreadsheetId": SS, "includesHeaders": True,
         "insertDataOption": "INSERT_ROWS", "valueInputOption": "RAW", "insertUnformatted": False, "useColumnHeaders": False},
         "module": "google-sheets:addRow", "version": 2, "parameters": {"__IMTCONN__": GS}}
    if dedupe:
        m["filter"] = {"name": "observation_id not yet in ledger (dedupe on resume)",
                       "conditions": [[{"a": "{{flatten(6.body.values)}}", "b": obs, "o": "array:notcontain"}]]}
    return m

OBS = "{{1.key}}:{{2.window}}:"
def write_then_mark(rid, row_mod, mark_mod):
    return {"id": rid, "mapper": {}, "module": "builtin:BasicRouter", "version": 1,
            "routes": [{"flow": [row_mod]}, {"flow": [mark_mod]}]}
COLLECT = [{"a": "{{3.wstatus}}", "b": "MISSED", "o": "text:notequal"}]
def chf(name, *chs):
    return {"name": name, "conditions": [[{"a": "{{1.data.channel}}", "b": c, "o": "text:equal"}] + COLLECT for c in chs]}
def on_err(mid, label, source):
    return [row(mid, OBS + "ALL:ERROR:{{2.run}}", "ALL", label, "", "", "ERROR", "", "", source, "{{error.message}}", dedupe=False),
            mark(mid + 1, '"ERROR"')]
DEF_DELAYED = ' — lifetime cumulative value at observed_at; if window_status=DELAYED this is NOT the {{2.window}} value'

def ig_route(mid, ch, metrics):
    return {"flow": [
        {"id": mid, "filter": chf(ch + ": IG media insights", ch), "mapper": {"id": "{{1.data.platform_post_id}}", "metrics": metrics},
         "module": "instagram-business:GetMediaInsights", "version": 1, "parameters": {"__IMTCONN__": IG},
         "onerror": on_err(mid + 100, "IG media insights call failed", "instagram-business:GetMediaInsights")},
        write_then_mark(mid + 3,
            row(mid + 1, OBS + "{{%d.name}}" % mid, "{{%d.name}}" % mid, "{{%d.title}}: {{%d.description}}" % (mid, mid) + DEF_DELAYED,
                "{{get(%d.values; 1).value}}" % mid, "count (watch_time metrics: ms)", "OBSERVED", "", "{{%d.period}}" % mid, "instagram-business:GetMediaInsights (IG Graph API)"),
            mark(mid + 2, 'if(3.wstatus = "ON_TIME"; "DONE_ON_TIME"; "DONE_DELAYED")'))]}

YT_NAMES = "views,likes,comments,watch_time,avg_view_duration,retention,subscribers_gained"
yt_val = '{{switch(41.value; "views"; 40.statistics.viewCount; "likes"; 40.statistics.likeCount; "comments"; 40.statistics.commentCount; "")}}'
yt_av = '{{if(contains(split("views,likes,comments"; ","); 41.value); "OBSERVED"; "UNAVAILABLE")}}'
yt_reason = '{{if(contains(split("views,likes,comments"; ","); 41.value); ""; "yt-analytics.readonly scope not granted (YouTube Analytics API)")}}'

routes = [
 {"flow": [{"id": 14, "filter": {"name": "window MISSED", "conditions": [[{"a": "{{3.wstatus}}", "b": "MISSED", "o": "text:equal"}]]},
            "mapper": {"variables": [{"name": "missed", "value": "{{2.window}}"}]}, "module": "util:SetVariables", "version": 1},
           write_then_mark(17,
               row(15, OBS + "ALL:MISSED", "ALL", "Window {{2.window}} not collected in time (collector ran at {{round(2.age_h)}}h, after the next window). No value is claimed.",
                   "", "", "MISSED", "collector did not run inside the window", "", "M1 window logic"),
               mark(16, '"MISSED"'))]},
 ig_route(20, "instagram_reels", ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]),
 ig_route(30, "instagram_feed", ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "follows", "profile_visits"]),
 {"flow": [
    {"id": 40, "filter": chf("youtube_shorts / youtube_hero: Data API statistics", "youtube_shorts", "youtube_hero"), "mapper": {"id": "{{1.data.platform_post_id}}"},
     "module": "youtube:ActionGetVideo", "version": 3, "parameters": {"account": YT}, "onerror": on_err(90, "YouTube video statistics call failed", "youtube:ActionGetVideo")},
    {"id": 41, "mapper": {"array": '{{split("%s"; ",")}}' % YT_NAMES}, "module": "builtin:BasicFeeder", "version": 1},
    write_then_mark(44,
        row(42, OBS + "{{41.value}}", "{{41.value}}", "YouTube Data API v3 video statistics" + DEF_DELAYED, yt_val, "count", yt_av, yt_reason, "lifetime", "youtube:ActionGetVideo (YouTube Data API v3)"),
        mark(43, 'if(3.wstatus = "ON_TIME"; "DONE_ON_TIME"; "DONE_DELAYED")'))]},
 # Facebook: engagement counts that the existing connection (pages_read_engagement) and Make modules support.
 # Views / reach / watch time have no Make module -> UNAVAILABLE (never 0). Each sub-route is independent: an API error
 # writes an ERROR row for that metric only and skips that sub-route; the window mark always runs last.
 {"flow": [
    {"id": 140, "filter": chf("facebook_reels / facebook_feed: engagement", "facebook_reels", "facebook_feed"),
     "mapper": {"variables": [{"name": "fb", "value": "{{1.data.platform_post_id}}"}]}, "module": "util:SetVariables", "version": 1},
    {"id": 141, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": [
      {"flow": [
        {"id": 142, "mapper": {"page_id": "839373332878305", "id": "{{1.data.platform_post_id}}", "type": ""},
         "module": "facebook-pages:GetPostReactions", "version": 6, "parameters": {"__IMTCONN__": FBC},
         "onerror": [row(143, OBS + "reactions:ERROR:{{2.run}}", "reactions", "Facebook reactions call failed", "", "", "ERROR", "", "", "facebook-pages:GetPostReactions",
                         "{{error.message}}", dedupe=False), {"id": 144, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
        row(145, OBS + "reactions", "reactions", "Total reactions on the post/reel (all types) — lifetime count at observed_at" + DEF_DELAYED,
            "{{142.totalCount}}", "count", "OBSERVED", "", "lifetime", "facebook-pages:GetPostReactions (Graph /{id}/reactions summary)")]},
      {"flow": [
        {"id": 146, "filter": {"name": "photo posts only (reel uploads return a video id, not the page post id)", "conditions": [[{"a": "{{1.data.channel}}", "b": "facebook_feed", "o": "text:equal"}]]},
         "mapper": {"page_id": "839373332878305", "id": "{{1.data.platform_post_id}}"}, "module": "facebook-pages:GetPost", "version": 6, "parameters": {"__IMTCONN__": FBC},
         "onerror": [row(147, OBS + "shares:ERROR:{{2.run}}", "shares", "Facebook post call failed", "", "", "ERROR", "", "", "facebook-pages:GetPost",
                         "{{error.message}}", dedupe=False), {"id": 148, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
        row(149, OBS + "shares", "shares", "Post shares count (Graph omits the field when not returned; then NOT_RETURNED, not 0)" + DEF_DELAYED,
            "{{ifempty(146.shares.count; \"\")}}", "count", '{{if(146.shares.count; "OBSERVED"; "NOT_RETURNED")}}',
            '{{if(146.shares.count; ""; "shares field not returned by Graph API")}}', "lifetime", "facebook-pages:GetPost")]},
      {"flow": [
        {"id": 150, "filter": {"name": "reels: shares not reachable", "conditions": [[{"a": "{{1.data.channel}}", "b": "facebook_reels", "o": "text:equal"}]]},
         "mapper": {"variables": [{"name": "na", "value": "shares"}]}, "module": "util:SetVariables", "version": 1},
        row(151, OBS + "shares", "shares", "Reel shares", "", "", "UNAVAILABLE", "reel upload returns only a video id; shares live on the page post (id not returned)", "", "—")]},
      {"flow": [
        {"id": 152, "mapper": {"page_id": "839373332878305", "id": "{{1.data.platform_post_id}}", "filter": "stream", "order": "", "limit": 500},
         "module": "facebook-pages:ListComments", "version": 6, "parameters": {"__IMTCONN__": FBC},
         "onerror": [row(153, OBS + "comments:ERROR:{{2.run}}", "comments", "Facebook comments call failed", "", "", "ERROR", "", "", "facebook-pages:ListComments",
                         "{{error.message}}", dedupe=False), {"id": 154, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
        {"id": 155, "mapper": {"id": "{{152.id}}"}, "module": "builtin:BasicAggregator", "version": 1, "parameters": {"feeder": 152}},
        row(156, OBS + "comments", "comments", "Comments incl. replies (stream), counted from List Comments, max 500" + DEF_DELAYED,
            "{{length(155.array)}}", "count", "OBSERVED", "", "lifetime", "facebook-pages:ListComments + aggregator")]},
      {"flow": [
        {"id": 60, "mapper": {"array": '{{split("views,reach,watch_time"; ",")}}'}, "module": "builtin:BasicFeeder", "version": 1},
        row(61, OBS + "{{60.value}}", "{{60.value}}", "Facebook video/post insights", "", "", "UNAVAILABLE",
            "no Make module for Graph insights; custom API call + permission check required", "", "—")]},
      {"flow": [mark(62, 'if(3.wstatus = "ON_TIME"; "DONE_ON_TIME"; "DONE_DELAYED")')]}]}]},
 {"flow": [
    {"id": 70, "filter": chf("tiktok / tiktok_photo: not available", "tiktok", "tiktok_photo"),
     "mapper": {"array": '{{split("views,likes,comments,shares"; ",")}}'}, "module": "builtin:BasicFeeder", "version": 1},
    write_then_mark(73,
        row(71, OBS + "{{70.value}}", "{{70.value}}", "TikTok video/photo metrics", "", "", "UNAVAILABLE", "no audited TikTok app / no video.list scope", "", "—"),
        mark(72, '"DONE_UNAVAILABLE"'))]},
]
age = '(formatDate(now; "X") - formatDate(1.data.published_at; "X")) / 3600'
flow = [
 {"id": 1, "mapper": {"filter": [[{"a": "campaign_id", "b": "aakhri-ishq", "o": "text:equal"}, {"a": "status", "b": "PUBLISHED", "o": "text:equal"},
                                  {"a": "platform_post_id", "o": "exist"}, {"a": "published_at", "o": "exist"}]]},
  "module": "datastore:SearchRecord", "version": 1, "parameters": {"datastore": DS}},
 {"id": 2, "mapper": {"variables": [
    {"name": "age_h", "value": "{{%s}}" % age},
    {"name": "gen", "value": "{{ifempty(1.data.metrics_lock_gen; 0) + 1}}"},
    {"name": "run", "value": "{{uuid}}"},   # per-bundle run id; {{var.execution.id}} is EMPTY in Make runs (T-lock v1, 2026-10-14)
    {"name": "window", "value": '{{if(%s; if(%s; if(%s; ""; "7d"); "72h"); "24h")}}' % (done('m24h_status'), done('m72h_status'), done('m7d_status'))}]},
  "module": "util:SetVariables", "version": 1},
 {"id": 3, "mapper": {"variables": [
    {"name": "planned_at", "value": '{{addHours(1.data.published_at; switch(2.window; "24h"; 24; "72h"; 72; 168))}}'},
    {"name": "wstatus", "value": ('{{if(2.window = ""; "NONE"; if(2.age_h < switch(2.window; "24h"; 24; "72h"; 72; 168); "NOT_DUE"; '
                                  'if(2.age_h <= switch(2.window; "24h"; 26; "72h"; 78; 180); "ON_TIME"; '
                                  'if(2.age_h >= switch(2.window; "24h"; 72; "72h"; 168; 99999); "MISSED"; "DELAYED"))))}}')}]},
  "module": "util:SetVariables", "version": 1},
 {"id": 5, "filter": {"name": "a window is due/late/missed and not locked by another run", "conditions": [[
     {"a": "{{3.wstatus}}", "b": "NONE", "o": "text:notequal"}, {"a": "{{3.wstatus}}", "b": "NOT_DUE", "o": "text:notequal"},
     {"a": '{{if(1.data.metrics_lock_until; formatDate(1.data.metrics_lock_until; "X"); 0)}}', "b": '{{formatDate(now; "X")}}', "o": "number:lessorequal"}]]},
  "mapper": {"key": "{{1.key}}", "data": {"metrics_lock_until": "{{addMinutes(now; 45)}}", "metrics_lock_gen": "{{2.gen}}"}, "upsert": False, "overwriteArrays": False},
  "module": "datastore:UpdateRecord", "version": 1, "parameters": {"datastore": DS}},
 # EXCLUSIVE CLAIM (insert-only key, unique in Make data stores). Generation is raised BEFORE the insert, so a run
 # that crashed after raising it never blocks the next generation; two runs that read the same generation race for
 # the same key and only one inserts it — the other bundle is skipped before any ledger write.
 {"id": 7, "mapper": {"key": "mlock:{{1.key}}:g{{2.gen}}", "overwrite": False,
   "data": {"campaign_id": "M1_LOCK", "placement_id": "{{1.key}}", "claim_token": "{{2.run}}", "updated_at": "{{now}}"}},
  "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": DS},
  "onerror": [{"id": 8, "module": "builtin:Ignore", "version": 1, "mapper": None}]},
 {"id": 6, "mapper": {"url": "spreadsheets/%s/values/%s!A:A" % (SS, TAB), "method": "GET"}, "module": "google-sheets:makeAPICall", "version": 2,
  "parameters": {"__IMTCONN__": GS}},
 {"id": 10, "mapper": {}, "module": "builtin:BasicRouter", "version": 1, "routes": routes}]
bp = {"name": "M1: AKI Metrics Collector (24h/72h/7d per placement) — INACTIVE", "flow": flow,
      "metadata": {"instant": False, "version": 1, "designer": {"orphans": []}, "scenario": {"dlq": False, "dataloss": False, "maxErrors": 3, "autoCommit": True,
                   "roundtrips": 1, "sequential": True, "confidential": False, "freshVariables": False, "autoCommitTriggerLast": True}}}
from make_error_refs import bind_error_refs
bind_error_refs(bp['flow'])   # T2 v3: bare error.* is empty inside handlers
if __name__ == '__main__':
    json.dump(bp, open('M1_blueprint.json', 'w'), ensure_ascii=False)
    print(len(json.dumps(bp)))
