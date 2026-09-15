import sys, os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
from control_plane import events as E
from control_plane.reducer import reduce
from control_plane.human_auth import content_fingerprint
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n)))
    print("PASS" if c else "FAIL", n)

def keypair():
    priv=Ed25519PrivateKey.generate()
    pub=priv.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    return priv,pub
def keyring(pub,kid="nitin-key-1",revoked=None): return {"keys":{kid:{"public_key_hex":pub,"owner":"nitin"}},"revoked":revoked or []}
def sign(priv,payload): return priv.sign(E.canonical(payload).encode()).hex()
def payload(gate,task,fp,aid="a1",nonce="n1",issued="2026-01-01T00:00:00Z",exp="2026-01-01T01:00:00Z",kid="nitin-key-1"):
    return {"approval_id":aid,"gate":gate,"task_id":task,"content_fingerprint":fp,"nonce":nonce,
            "issued_at":issued,"expires_at":exp,"key_id":kid}
def gate_req(task,gate,fp,i=20):
    return E.make_event("r%03d"%i,"HUMAN_GATE_REQUEST","2026-01-01T00:00:05Z","claude",task_id=task,gate=gate,inputs={"content_fingerprint":fp})
def gate_grant(pl,priv,agent="claude",ts="2026-01-01T00:30:00Z",sig=None,i=21):
    e=E.make_event("g%03d"%i,"HUMAN_GATE_GRANTED",ts,agent,task_id=pl["task_id"],gate=pl["gate"])
    e["approval"]={"payload":pl,"signature":sig if sig is not None else sign(priv,pl)}
    return e
arch=E.make_event("e001","ARCH_DECISION","2026-01-01T00:00:01Z","chatgpt",
     decision={"selected_control_plane":"TEMPORAL","winner":"TEMPORAL","production_deployment_authorized":False})
CT={"content_id":"POST-1","asset_sha256":"aaaa","platform":"instagram","packaging_sha256":"bbbb","schedule_version":"v1"}
FP=content_fingerprint(CT)
priv,pub=keypair(); KR=keyring(pub)

# POSITIVE: valid signed approval grants
s=reduce([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP),priv)],keyring=KR)
ok("valid_signed_approval_grants", s["approvals"].get("NITIN_PUBLISH_APPROVAL",{}).get("authority")=="ed25519_verified")

def rejected(events, kr=KR):
    st=reduce(events,keyring=kr); return ("NITIN_PUBLISH_APPROVAL" not in st["approvals"]), st

# 1. agent="nitin" but NO authority evidence (bare metadata)
bare=E.make_event("b1","HUMAN_GATE_GRANTED","2026-01-01T00:30:00Z","nitin",task_id="P",gate="NITIN_PUBLISH_APPROVAL")
r,st=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),bare]); ok("reject_agent_nitin_no_evidence", r)
ok("metadata_reason_malformed", any(x["reason"]=="human_gate_MALFORMED_APPROVAL" for x in st["_rejected_events"]))

# 2. forged signature (valid structure, wrong sig)
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP),priv,sig="00"*64)]); ok("reject_forged_signature", r)

# 3. approval for wrong content (fingerprint mismatch)
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P","WRONG_FP"),priv)]); ok("reject_wrong_content", r)

# 4. approval for wrong gate (signed for CREATIVE, used at PUBLISH request)
wg=payload("NITIN_CREATIVE_APPROVAL","P",FP); e=gate_grant(wg,priv); e["gate"]="NITIN_PUBLISH_APPROVAL"; e["task_id"]="P"
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),e]); ok("reject_wrong_gate", r)

# 5. stale / expired approval
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP,exp="2026-01-01T00:00:10Z"),priv,ts="2026-01-01T00:30:00Z")]); ok("reject_expired", r)

# 6. revoked approval (approval_id in keyring.revoked)
KRrev=keyring(pub,revoked=["a1"])
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP),priv)],kr=KRrev); ok("reject_revoked", r)

# 7. duplicate approval (same approval_id/nonce reused for a second task)
dupev=[arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP),priv),
       gate_req("P2","NITIN_PUBLISH_APPROVAL",FP,i=30),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P2",FP),priv,i=31)]
st=reduce(dupev,keyring=KR)
ok("reject_duplicate_nonce", any(x["reason"]=="human_gate_DUPLICATE" for x in st["_rejected_events"]))

# 8. malformed approval payload (missing fields)
mal=E.make_event("m1","HUMAN_GATE_GRANTED","2026-01-01T00:30:00Z","nitin",task_id="P",gate="NITIN_PUBLISH_APPROVAL")
mal["approval"]={"payload":{"gate":"NITIN_PUBLISH_APPROVAL"},"signature":"00"}
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),mal]); ok("reject_malformed_payload", r)

# 9. AI-originated impersonation (agent=claude, self-made unsigned payload)
imp=E.make_event("i1","HUMAN_GATE_GRANTED","2026-01-01T00:30:00Z","claude",task_id="P",gate="NITIN_PUBLISH_APPROVAL")
imp["approval"]={"payload":payload("NITIN_PUBLISH_APPROVAL","P",FP),"signature":"ab"*64}
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),imp]); ok("reject_ai_impersonation", r)

# 10. empty keyring (no provisioned Nitin key) => fail-closed even with a structurally valid, correctly-signed-by-someone approval
r,_=rejected([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),gate_grant(payload("NITIN_PUBLISH_APPROVAL","P",FP),priv)],kr={"keys":{},"revoked":[]}); ok("failclosed_no_provisioned_key", r)

# hardened invariants
AI_CREATE = not reduce([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),bare],keyring=KR)["approvals"]
ok("AI_CAN_CREATE_NITIN_APPROVAL_false", "NITIN_PUBLISH_APPROVAL" not in reduce([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),bare],keyring=KR)["approvals"])
ok("AI_CAN_IMPERSONATE_BY_METADATA_false", "NITIN_PUBLISH_APPROVAL" not in reduce([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP),imp],keyring=KR)["approvals"])
ok("PUBLISH_WITHOUT_NITIN_APPROVAL_false", "NITIN_PUBLISH_APPROVAL" not in reduce([arch,gate_req("P","NITIN_PUBLISH_APPROVAL",FP)],keyring=KR)["approvals"])

print("\nHA_TOTAL=%d HA_PASSED=%d HA_FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
