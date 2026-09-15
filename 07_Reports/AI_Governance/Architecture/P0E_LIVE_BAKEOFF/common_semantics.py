"""Shared, engine-agnostic workload for the P0-E live bake-off.
Both the Temporal and Hatchet workers import THIS module, so only the engine differs (fair test).
Implements the addendum corrections: explicit idempotency + side-effect dedup (NO exactly-once
assumption), model/prompt/policy provenance, asset-ref-only (no binaries), artifact staleness binding,
DLQ, Gemini cache lifecycle. Disposable MOCK asset only — never the Aakhri Ishq master.
Authored from docs; validate on a Docker-capable host."""
import json, hashlib, os, time, random

SIDE_EFFECTS = os.environ.get("SE_STORE", "/tmp/bakeoff_side_effects.json")

def sha(x): return hashlib.sha256(x if isinstance(x, bytes) else json.dumps(x, sort_keys=True).encode()).hexdigest()

# ---- disposable mock asset (NOT real) ----
MOCK_ASSET_BYTES = b"MOCK-DISPOSABLE-POSTER-v1"
MOCK_ASSET_SHA = sha(MOCK_ASSET_BYTES)
MOCK_ASSET_REF = "ref://mock/poster_disposable_01"

def resolve_model(profile="gemini_creative"):
    # never hard-code a model id; resolve at runtime and record it
    return {"model_profile": profile,
            "resolved_model_id": os.environ.get("GEMINI_MODEL_ID", "RESOLVED_AT_RUNTIME"),
            "model_api_version": os.environ.get("GEMINI_API_VERSION", "v1"),
            "prompt_version": "pv3", "policy_version": "gov1"}

def guard_no_binary_in_history(payload: dict):
    blob = json.dumps(payload)
    assert "base64," not in blob and len(blob) < 4096, "BINARY_OR_OVERSIZE_BLOCKED"
    return True

def _load(): return json.load(open(SIDE_EFFECTS)) if os.path.exists(SIDE_EFFECTS) else {}
def _save(o): open(SIDE_EFFECTS, "w").write(json.dumps(o))

def side_effect_once(idempotency_key: str, do):
    """Perform an external side effect AT MOST once per idempotency key (dedup across retries/replays)."""
    store = _load()
    if idempotency_key in store:
        return store[idempotency_key], True   # already done -> do NOT repeat
    result = do()
    store[idempotency_key] = {"result_hash": sha(result), "at": time.time()}
    _save(store)
    return store[idempotency_key], False

# ---- mock agents return REAL proposed schemas; asset passed by ref+sha only ----
def claude_build(task_id, sleep=0.0):
    if sleep: time.sleep(sleep)
    return {"schema": "TASK_RESULT_V1", "task_id": task_id, "produced_by": "claude",
            "status": "SUCCEEDED", "idempotency_key": f"{task_id}:claude",
            "evidence_refs": [f"ev://build/{task_id}"], "asset_ref": MOCK_ASSET_REF, "asset_sha256": MOCK_ASSET_SHA}

def gemini_creative(task_id, asset_sha, sleep=0.0):
    if sleep: time.sleep(sleep)  # used for the 2-5 min long-activity crash test
    prov = resolve_model()
    binding = {"asset_sha256": asset_sha, "analysis_scope": "poster_full",
               "resolved_model_id": prov["resolved_model_id"], "prompt_version": prov["prompt_version"],
               "policy_version": prov["policy_version"]}
    return {"schema": "GEMINI_CREATIVE_INTELLIGENCE_V1", "task_id": task_id, "produced_by": "gemini",
            "idempotency_key": f"{task_id}:gemini:{asset_sha}:{prov['prompt_version']}:{prov['policy_version']}",
            "asset_ref": MOCK_ASSET_REF, "binding": binding,
            "analysis": {"captions": ["c"], "hashtags": ["#x"], "hooks": ["h"], "ctas": ["cta"], "platform_packaging": {}}}

def chatgpt_arch(task_id):
    return {"schema": "ARCH_DECISION_V1", "task_id": task_id, "produced_by": "chatgpt",
            "idempotency_key": f"{task_id}:arch", "decision": "PROCEED",
            "human_gate_required": True, "required_gate": "NITIN_PUBLISH_APPROVAL"}

def is_stale(binding, current_asset_sha): return binding["asset_sha256"] != current_asset_sha

# ---- DLQ helper ----
def dlq_transition(attempts, max_attempts=3):
    if attempts >= max_attempts: return "DLQ"           # RETRYING -> RETRY_EXHAUSTED -> DLQ/MANUAL_REVIEW
    return "RETRYING"

# ---- Gemini cache lifecycle ----
class GeminiCache:
    def __init__(self, ttl=0.01): self.state="CREATED"; self.exp=time.time()+ttl
    def activate(self): self.state="ACTIVE"; return self
    def reuse(self): self.state="REUSABLE"; return self
    def maybe_expire(self):
        if time.time()>self.exp: self.state="EXPIRED"
        return self.state
    def clean(self): self.state="CLEANED"; return self.state

# ---- safe sink (NO real publish; fail-closed: cannot mint a grant) ----
def safe_sink_publish(task_id):
    def do(): return {"sink": "SAFE", "task_id": task_id, "published": False, "reason": "safe_sink_no_grant"}
    return side_effect_once(f"sink:{task_id}", do)
