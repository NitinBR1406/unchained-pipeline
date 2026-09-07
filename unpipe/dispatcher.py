"""Secure production-workflow dispatcher (V1.1.1).

Fires a GitHub `repository_dispatch` (event_type=production-render) so a valid CREATIVE_APPROVAL
starts the autonomous render on GitHub Actions — Nitin never opens the Actions UI.

Auth: a LEAST-PRIVILEGE fine-grained token from env var GITHUB_DISPATCH_TOKEN (scope: Actions:write
on the single repo only). Never logged, never returned, never stored in files/manifests. Do NOT embed
this token in any client-side approval UI; keep it server-side / in the environment that runs approvals.
"""
import json
import os
import urllib.request
import urllib.error

DISPATCH_TOKEN_ENV = "GITHUB_DISPATCH_TOKEN"
DEFAULT_EVENT = "production-render"


class DispatchTransient(Exception):
    """Retryable dispatch failure (429/5xx/timeout/network)."""


class DispatchAuthError(Exception):
    """Material dispatch failure (missing/invalid token, 401/403/404) -> HOLD, no retry."""


class GitHubDispatcher:
    def __init__(self, owner, repo, event_type=DEFAULT_EVENT, token_env=DISPATCH_TOKEN_ENV):
        self.owner = owner
        self.repo = repo
        self.event_type = event_type
        self.token_env = token_env

    def _token(self):
        t = os.environ.get(self.token_env)
        if not t:
            raise DispatchAuthError(f"{self.token_env} not set")
        return t

    def dispatch(self, campaign_id):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/dispatches"
        body = json.dumps({"event_type": self.event_type,
                           "client_payload": {"campaign_id": campaign_id}}).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status in (200, 201, 202, 204)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise DispatchAuthError(f"HTTP {e.code}")
            if e.code == 429 or 500 <= e.code < 600:
                raise DispatchTransient(f"HTTP {e.code}")
            raise DispatchAuthError(f"HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError) as e:
            raise DispatchTransient(f"network: {e}")


class DryDispatcher:
    """Safe non-network dispatcher for infra smoke tests. Appends the call to a file; never hits
    GitHub or Shotstack, never consumes credits. Use via PIPELINE_DISPATCH_DRY=1."""
    def __init__(self, log_path):
        self.log_path = log_path

    def dispatch(self, campaign_id):
        import json as _j
        from .util import now_iso
        with open(self.log_path, "a") as f:
            f.write(_j.dumps({"campaign_id": campaign_id, "at": now_iso(), "mode": "dry"}) + "\n")
        return True


class FakeDispatcher:
    """Test dispatcher — no network. Records calls; can simulate transient/auth failure."""
    def __init__(self, transient_before_success=0, auth_fail=False):
        self.transient_before_success = transient_before_success
        self.auth_fail = auth_fail
        self.calls = []
        self._n = 0

    def dispatch(self, campaign_id):
        self.calls.append(campaign_id)
        if self.auth_fail:
            raise DispatchAuthError("simulated auth failure")
        if self._n < self.transient_before_success:
            self._n += 1
            raise DispatchTransient("simulated 5xx")
        return True
