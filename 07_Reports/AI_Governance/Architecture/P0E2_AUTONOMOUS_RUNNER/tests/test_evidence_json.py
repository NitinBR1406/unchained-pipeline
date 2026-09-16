import os, sys, json, tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,ROOT)
sys.path.insert(0, os.path.join(ROOT,"..","P0E1_CONTROL_PLANE"))
import evidence_json as EJ
import acceptance_gate as AG
P=F=0; FAILS=[]
def ok(n,c):
    global P,F
    (globals().__setitem__('P',P+1) if c else (globals().__setitem__('F',F+1),FAILS.append(n))); print("PASS" if c else "FAIL",n)
d=tempfile.mkdtemp()
# strings "true"/"false" (as they arrive from shell) must become real JSON booleans
fi=EJ.write_failure_injection(os.path.join(d,"fi.json"),
    {k:("true" if k!="postgres_restart_observed" else "false") for k in EJ.FI_BOOLS})
loaded=json.load(open(os.path.join(d,"fi.json")))
ok("failure_injection_parses", isinstance(loaded,dict))
ok("bools_are_python_bool", all(isinstance(loaded[k],bool) for k in EJ.FI_BOOLS))
ok("true_string_becomes_True", loaded["worker_kill_observed"] is True)
ok("false_string_becomes_False", loaded["postgres_restart_observed"] is False)
ok("no_string_true_false_values", all(loaded[k] in (True,False) for k in EJ.FI_BOOLS))
ok("accepted_by_gate_is_true", AG._is_true(loaded["worker_kill_observed"]))
ok("rejected_by_gate_is_true_when_false", not AG._is_true(loaded["postgres_restart_observed"]))
poc=EJ.write_poc(os.path.join(d,"poc.json"),"false")
lp=json.load(open(os.path.join(d,"poc.json")))
ok("poc_bool_type", isinstance(lp["POC_INFRA_REMAINING"],bool) and lp["POC_INFRA_REMAINING"] is False)
ok("poc_is_false_accepted", AG._is_false(lp["POC_INFRA_REMAINING"]))
ok("poc_true_string", EJ.write_poc(os.path.join(d,"poc2.json"),"true")["POC_INFRA_REMAINING"] is True)
# raw text must not contain a bare python NameError-style token issue: valid json only
raw=open(os.path.join(d,"fi.json")).read(); ok("valid_json_lowercase_bools", ("true" in raw or "false" in raw) and json.loads(raw) is not None)
print("\nEJ_TOTAL=%d PASSED=%d FAILED=%d"%(P+F,P,F))
if FAILS: print("FAILURES:",FAILS)
sys.exit(1 if F else 0)
