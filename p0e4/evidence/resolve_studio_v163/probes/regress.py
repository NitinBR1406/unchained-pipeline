import json,subprocess,os,sys,hashlib
from pathlib import Path
root=Path.cwd();out=root/'.local/resolve-v163/REGRESSION_FIXED.json';old=json.loads((root/'.local/resolve-v163/REGRESSION.json').read_text())
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(root)+':/private/tmp/unchained-v163-deps:/private/tmp/unchained-p0e4-v09-venv/lib/python3.12/site-packages',PYTHONWARNINGS='ignore::ResourceWarning')
results=[]
for row in [{'file':x} for x in sorted({r['file'] for r in old['suites']} | {str(p.relative_to(root)) for p in (root/'p0e4/tests').glob('test_*.py')})]:
 p=subprocess.run([sys.executable,row['file']],env=env,text=True,capture_output=True,timeout=120)
 results.append(dict(file=row['file'],exit_code=p.returncode,output=p.stdout+p.stderr))
 if p.returncode:print(row['file'],(p.stdout+p.stderr)[-1200:],flush=True)
checks=[]
for manifest in sorted((root/'p0e4/evidence').rglob('SHA256SUMS.txt')):
 if 'resolve_studio_v163' in str(manifest):continue
 for line in manifest.read_text().splitlines():
  if not line.strip():continue
  expected,path=line.split(maxsplit=1);p=manifest.parent/path.lstrip('*')
  checks.append(dict(manifest=str(manifest.relative_to(root)),path=path,**{'pass':p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected}))
r=dict(tested_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tracked_worktree_clean=subprocess.run(['git','diff','--quiet','HEAD']).returncode==0,passed=sum(x['exit_code']==0 for x in results),total=len(results),suites=results,prior_manifests=checks,runtime=sys.version,dependency_path='/private/tmp/unchained-p0e4-v09-venv/lib/python3.12/site-packages',new_authoritative_live_runs=0)
out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print({k:r[k] for k in ['tested_sha','passed','total']});print('manifests',len(checks),'failed',sum(not x['pass'] for x in checks))
