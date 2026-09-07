#!/usr/bin/env python3
"""Hardened mobile approval server (V1.1.3) — stdlib http.server, no web framework.

Renders a phone-friendly APPROVE/REJECT page for a signed link and records the authoritative
approval (which auto-dispatches for creative). Secrets stay server-side; the client only holds the
opaque signed token.

Hardening: /healthz (no state), request-size cap, per-IP rate limit, security headers, secret-safe
logging, constant-time signature check (in service), single-use nonce persisted to disk (survives
restart when the disk is persistent).

Env:
  APPROVAL_SIGNING_SECRET   HMAC secret for links (server-side)          [required]
  APPROVERS                 comma-separated approver ids (default "nitin")
  GH_OWNER / GH_REPO        repo for dispatch (default NitinBR1406/unchained-pipeline)
  GITHUB_DISPATCH_TOKEN     least-privilege PAT (Actions:write)          [required for live dispatch]
  PIPELINE_DISPATCH_DRY=1   use safe DryDispatcher (no GitHub/Shotstack) — for smoke tests
  PORT                      listen port (cloud hosts set this)
  CONSUMED_STORE            path for the single-use nonce store (put on a persistent disk)
Run: python3 approval_server.py <campaigns_root> [host] [port]
"""
import os
import sys
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unpipe.orchestrator import Campaign
from unpipe.dispatcher import GitHubDispatcher, DryDispatcher
from unpipe.approval_service import ApprovalService, ApprovalError

CAMPAIGNS_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("campaigns")
OWNER = os.environ.get("GH_OWNER", "NitinBR1406")
REPO = os.environ.get("GH_REPO", "unchained-pipeline")
DRY = os.environ.get("PIPELINE_DISPATCH_DRY") == "1"
MAX_BODY = 16 * 1024
RATE_MAX, RATE_WINDOW = 30, 60.0   # 30 requests / minute / IP
_hits = defaultdict(deque)


def campaign_factory(cid):
    mani = CAMPAIGNS_ROOT / cid / "campaign.json"
    work = CAMPAIGNS_ROOT / cid / "state"
    if DRY:
        disp = DryDispatcher(str(CAMPAIGNS_ROOT / "_dry_dispatch.log"))
    else:
        disp = GitHubDispatcher(owner=OWNER, repo=REPO)   # reads GITHUB_DISPATCH_TOKEN server-side
    return Campaign(work, mani, dispatcher=disp)


SVC = None


def build_service():
    return ApprovalService(
        signing_secret=os.environ.get("APPROVAL_SIGNING_SECRET", ""),
        campaign_factory=campaign_factory,
        approvers=[a.strip() for a in os.environ.get("APPROVERS", "nitin").split(",")],
        consumed_path=os.environ.get("CONSUMED_STORE", str(CAMPAIGNS_ROOT / "_approvals_consumed.json")),
    )


PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Approval</title><style>body{{font-family:-apple-system,system-ui,sans-serif;background:#0d0d0d;
color:#F0EAD6;margin:0;padding:24px}}.card{{max-width:420px;margin:8vh auto;background:#151515;
border:1px solid #2a2a2a;border-radius:16px;padding:24px}}h1{{color:#D4AF37;font-size:20px;margin:0 0 4px}}
.k{{color:#8a8a8a;font-size:13px;margin-top:14px}}.v{{font-size:17px}}form{{display:flex;gap:12px;margin-top:28px}}
button{{flex:1;padding:16px;border:0;border-radius:12px;font-size:17px;font-weight:600}}
.ok{{background:#1f6f43;color:#fff}}.no{{background:#6f1f1f;color:#fff}}</style></head>
<body><div class=card><h1>{artist}</h1><div class=v>{campaign}</div>
<div class=k>Asset</div><div class=v>{asset}</div>
<div class=k>Version</div><div class=v>{version}</div>
<div class=k>Status</div><div class=v>{status}</div>
<form method=POST action="/decision">
<input type=hidden name=token value="{token}"><input type=hidden name=approver value="{approver}">
<button class=ok name=decision value=APPROVE>APPROVE</button>
<button class=no name=decision value=REJECT>REJECT</button></form></div></body></html>"""


def _rate_ok(ip):
    now = time.time()
    dq = _hits[ip]
    while dq and now - dq[0] > RATE_WINDOW:
        dq.popleft()
    if len(dq) >= RATE_MAX:
        return False
    dq.append(now)
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "unpipe-approval"

    def _send(self, code, body, ctype="text/html"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _ip(self):
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            return self._send(200, "ok", "text/plain")   # no sensitive state
        if not _rate_ok(self._ip()):
            return self._send(429, "<p>Too many requests.</p>")
        q = parse_qs(urlparse(self.path).query)
        token = (q.get("token") or [""])[0]
        approver = (q.get("approver") or ["nitin"])[0]
        try:
            d = SVC.render_request(token)
            self._send(200, PAGE.format(token=token, approver=approver, **d))
        except ApprovalError as e:
            self._send(400, f"<p>Invalid or expired link: {e}</p>")

    def do_POST(self):
        if not _rate_ok(self._ip()):
            return self._send(429, "<p>Too many requests.</p>")
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, "<p>Bad request.</p>")
        if n <= 0 or n > MAX_BODY:
            return self._send(413, "<p>Request too large.</p>")
        form = parse_qs(self.rfile.read(n).decode(errors="ignore"))
        token = (form.get("token") or [""])[0]
        decision = (form.get("decision") or [""])[0]
        approver = (form.get("approver") or [""])[0]
        reason = (form.get("reason") or [""])[0]
        try:
            res = SVC.decide(token, decision, approver, reason)
            msg = ("Approved — production is starting. You'll be notified when the master is ready."
                   if res.get("dispatched")
                   else f"Recorded: {res.get('decision', res.get('status'))}.")
            self._send(200, f"<div style='font-family:system-ui;color:#F0EAD6;background:#0d0d0d;"
                            f"padding:40px'><h2 style='color:#D4AF37'>{msg}</h2></div>")
        except ApprovalError as e:
            self._send(400, f"<p>{e}</p>")

    def log_message(self, fmt, *args):   # secret-safe: log method+path+code only, never query/body
        try:
            sys.stderr.write("%s - %s\n" % (self._ip(), (self.requestline.split("?")[0]
                                                          if self.requestline else "")))
        except Exception:
            pass


if __name__ == "__main__":
    SVC = build_service()   # requires APPROVAL_SIGNING_SECRET
    host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("PORT", "8787"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()
