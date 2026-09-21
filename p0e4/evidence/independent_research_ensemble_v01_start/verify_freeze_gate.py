"""Read-only fail-closed ensemble freeze gate. Does not infer research validity."""
import hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parent
tracks=[('A','track_a_gemini','GEMINI_INDEPENDENT_REPORT_V01'),('B','track_b_claude','CLAUDE_INDEPENDENT_REPORT_V01'),('C','track_c_chatgpt','CHATGPT_INDEPENDENT_REPORT_V01')]
results=[]
for key,folder,name in tracks:
 d=root/folder;receipt=d/'FREEZE_RECEIPT.json';issues=[]
 if not receipt.exists():issues.append('MISSING_FREEZE_RECEIPT')
 else:
  r=json.loads(receipt.read_text())
  if r.get('report_id')!=name:issues.append('REPORT_ID_MISMATCH')
  if r.get('status')!='FROZEN_V01':issues.append('NOT_FROZEN')
  for required in ['raw_report','dataset','sources','methodology','confidence']:
   ref=r.get('artifacts',{}).get(required)
   if not ref:issues.append('MISSING_'+required.upper());continue
   f=(d/ref['path']).resolve()
   if not f.is_relative_to(d.resolve()):issues.append('INVALID_PATH');continue
   if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=ref['sha256']:issues.append('HASH_MISMATCH_'+required.upper())
  if r.get('other_track_results_supplied') is not False:issues.append('INDEPENDENCE_NOT_DECLARED')
 results.append({'track':key,'issues':issues,'frozen_artifact_set_verified':not issues})
print(json.dumps({'synthesis_allowed':all(x['frozen_artifact_set_verified'] for x in results),'tracks':results,'caveat':'A frozen report is not validation of its claims; cross-validation is a separate downstream step.'},indent=2))
