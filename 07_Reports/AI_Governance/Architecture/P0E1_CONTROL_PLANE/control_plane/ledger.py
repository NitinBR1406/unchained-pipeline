"""Append-only, hash-chained Event Ledger (JSONL). Immutable after append; tamper-evident on read."""
import os, json
from .events import canonical, sha256, is_wellformed
GENESIS = "0"*64
class LedgerError(Exception): pass
class EventLedger:
    def __init__(self, path): self.path=path
    def _last_hash(self):
        h=GENESIS
        if os.path.exists(self.path):
            for ln in open(self.path):
                ln=ln.strip()
                if ln: h=json.loads(ln)["ledger_hash"]
        return h
    def _seq(self):
        n=0
        if os.path.exists(self.path):
            for ln in open(self.path):
                if ln.strip(): n+=1
        return n
    def append(self, event):
        if not is_wellformed(event): raise LedgerError("malformed event rejected at append")
        prev=self._last_hash(); seq=self._seq()
        rec=dict(event); rec["ledger_seq"]=seq; rec["prev_ledger_hash"]=prev
        rec["ledger_hash"]=sha256(prev + canonical(event))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path,"a") as f: f.write(canonical(rec)+"\n")
        return rec
    def read_all(self):
        out=[]
        if os.path.exists(self.path):
            for ln in open(self.path):
                ln=ln.strip()
                if ln: out.append(json.loads(ln))
        return out
    def verify_chain(self):
        prev=GENESIS
        for i,rec in enumerate(self.read_all()):
            base={k:v for k,v in rec.items() if k not in ("ledger_seq","prev_ledger_hash","ledger_hash")}
            if rec.get("prev_ledger_hash")!=prev: raise LedgerError("chain break (prev) at seq %d"%i)
            if rec.get("ledger_hash")!=sha256(prev+canonical(base)): raise LedgerError("tamper detected at seq %d"%i)
            prev=rec["ledger_hash"]
        return True
