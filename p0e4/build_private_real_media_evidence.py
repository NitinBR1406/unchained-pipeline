import hashlib,json,subprocess
from pathlib import Path
from integration.private_real_media import authorize_private_real_media
from prompt_templates import template
from prompt_governance import lint,candidate,equivalence,validate_context
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'p0e4/evidence/private_real_media_v01'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
 p=OUT/name;p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');return p
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rec_path=ROOT/'p0e4/evidence/post_ready_v01/RAW_INGEST_RECONCILIATION_V01.json';event_path=OUT/'NITIN_AUTHORIZATION.json';master=ROOT/'p0e4/MASTER_STATE_LATEST.json'
 rec=json.loads(rec_path.read_text());event=json.loads(event_path.read_text());contract=authorize_private_real_media(rec,event)
 write('PRIVATE_REAL_MEDIA_ACCEPTANCE_V01.json',contract)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 refs=[{'uri':str(master.relative_to(ROOT)),'sha256':sha(master)},{'uri':str(rec_path.relative_to(ROOT)),'sha256':sha(rec_path)},{'uri':str(event_path.relative_to(ROOT)),'sha256':sha(event_path)}]
 context={'schema':'EXECUTION_CONTEXT_GOVERNANCE_V01','schema_version':1,'context_id':'aki-private-real-media-v01','repository':'NitinBR1406/unchained-pipeline','branch':'p0e4/slice1-production-handoff','tested_sha':head,'master_state_ref':refs[0],'task_state_refs':refs[1:],'authority':{'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'},'allowed_operations':['READ_BOUND_MEDIA','WRITE_PRIVATE_LOCAL_STAGING','CREATE_NEW_PRIVATE_RESOLVE_PROJECT','PRIVATE_RENDER','WRITE_REPO_EVIDENCE','PRIVATE_GEMINI_QC','PRIVATE_CLAUDE_TRANSLATION'],'forbidden_operations':['PUBLISH','PRODUCTION_DEPLOYMENT','LIVE_MAKE_CUTOVER','SHARED_DRIVE_MUTATION','INFER_NITIN_APPROVAL'],'budgets':{'max_input_tokens':12000,'max_output_tokens':6000,'max_retries':1,'max_latency_ms':900000}}
 validate_context(context);write('EXECUTION_CONTEXT_GOVERNANCE_V01.json',context)
 prompt_results={}
 for actor,objective in [('CODEX','Execute the hash-bound Aakhri Ishq private real-media render and technical acceptance.'),('GEMINI','Independently inspect the private rendered candidate and return bounded QC observations.'),('CLAUDE','Translate the private bound-media contract into production-oriented edit/QC guidance without deployment.')]:
  p=template('TASK_PROMPT',actor,'aki-private-v01:'+actor.lower(),objective,refs);c=candidate(p);prompt_results[actor]={'source':p,'candidate':c,'lint':lint(p),'equivalence':equivalence(p,c)}
 write('GOVERNED_PROMPTS.json',prompt_results)
 write('CONTRACT_ACCEPTANCE.json',{'schema':'PRIVATE_REAL_MEDIA_CONTRACT_ACCEPTANCE_V01','schema_version':1,'tested_sha':head,'contract_status':contract['status'],'prompt_lint_green':all(x['lint']['status']=='PASS' for x in prompt_results.values()),'semantic_equivalence_green':all(x['equivalence']['status']=='PASS' for x in prompt_results.values()),'private_authority_distinct_from_production':True,'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN'})
 files=sorted(x for x in OUT.iterdir() if x.name!='SHA256SUMS.txt');(OUT/'SHA256SUMS.txt').write_text(''.join(sha(x)+'  '+x.name+'\n' for x in files))
if __name__=='__main__':main()
