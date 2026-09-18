"""Run existing offline suites plus additive tests; exact clean commit evidence.

No live workflow dispatch. Excludes the historical explicit live NB001 suite.
Outputs must go to disposable staging or a new evidence directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def run(output):
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    prior=json.loads((ROOT/'p0e4/evidence/human_binding/REGRESSION.json').read_text())
    suites=sorted(set(x['file'] for x in prior['suites']) |
                  {str(p.relative_to(ROOT)) for p in (ROOT/'p0e4/tests').glob('test_*.py')})
    results=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),PYTHONWARNINGS='ignore::ResourceWarning')
    for name in suites:
        proc=subprocess.run([sys.executable,name],cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
        results.append({'file':name,'exit_code':proc.returncode,'output':proc.stdout+proc.stderr})
    manifests=[]
    for dirname in ('p0e4/evidence','p0e4/evidence/resume','p0e4/evidence/review','p0e4/evidence/human_binding'):
        manifest=ROOT/dirname/'SHA256SUMS.txt'
        for line in manifest.read_text().splitlines():
            expected,path=line.split(maxsplit=1)
            target=manifest.parent/path.lstrip('*')
            ok=target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==expected
            manifests.append({'manifest':str(manifest.relative_to(ROOT)),'path':path,'pass':ok})
    clean=subprocess.run(['git','diff','--quiet','HEAD'],cwd=ROOT).returncode==0
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','p0e4/integration','p0e4/tests'],cwd=ROOT,text=True).splitlines()
    report={'tested_sha':sha,'tracked_worktree_clean':clean,'untracked_runtime_files':untracked,'python_version':sys.version,'suites':results,'prior_manifests':manifests,
            'passed':sum(x['exit_code']==0 for x in results),'total':len(results),
            'new_authoritative_live_runs':0}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('tested_sha','passed','total')}))
    for row in results:
        if row['exit_code']:print(row['file'],row['output'][-1500:])
    for row in manifests:
        if not row['pass']:print('MANIFEST_MISMATCH',row)
    return all(x['exit_code']==0 for x in results) and all(x['pass'] for x in manifests)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args()
    sys.exit(0 if run(a.output) else 1)
