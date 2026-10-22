"""Generate exact changed-source manifest and review patch without staging/commits."""
from pathlib import Path
import subprocess,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/exploration-story-v3'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
    # Only task-created transient copies are removed. No source or other worktree touched.
    cache=OUT/'pytest-tmp'
    if cache.exists():shutil.rmtree(cache)
    for name in ['source-sanitized.txt']:
        p=OUT/name
        if p.exists():p.unlink()
    tracked=git('diff','--name-only','HEAD').decode().splitlines()
    untracked=git('ls-files','--others','--exclude-standard').decode().splitlines()
    added=sorted(p for p in untracked if p.startswith(('app/interest_quest/protected/','scripts/','tests/exploration_launch/')))
    paths=sorted(set(tracked+added))
    allowed=('app/interest_quest/protected/','scripts/','tests/exploration_launch/')
    assert all(p.startswith(allowed) for p in paths),paths
    payload=git('diff','--binary','HEAD','--',*tracked)
    for relative in added:
        r=subprocess.run(['git','diff','--no-index','--binary','--','/dev/null',relative],cwd=ROOT,capture_output=True)
        assert r.returncode==1,(relative,r.returncode,r.stderr)
        assert b'new file mode' in r.stdout,(relative,r.stdout[:300])
        payload+=r.stdout
    (OUT/'changes.patch').write_bytes(payload)
    check=subprocess.run(['git','apply','--reverse','--check',str(OUT/'changes.patch')],cwd=ROOT,capture_output=True)
    assert check.returncode==0,check.stderr.decode(errors='replace')
    rows=[]
    for p in paths:
        raw=(ROOT/p).read_bytes()
        rows.append({'path':p,'absolute_path':str((ROOT/p).resolve()),'change':'modified' if p in tracked else 'added','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    manifest={'root':str(ROOT),'baseline':git('rev-parse','HEAD').decode().strip(),'branch':git('branch','--show-current').decode().strip(),'source_file_count':len(rows),'patch_bytes':len(payload),'patch_sha256':hashlib.sha256(payload).hexdigest(),'reverse_apply_check':'passed; dry run only','staged_files':git('diff','--cached','--name-only').decode().splitlines(),'files':rows}
    (OUT/'changed-source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name not in ['evidence-sha256.json']:
            raw=p.read_bytes();evidence.append({'path':str(p.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    (OUT/'evidence-sha256.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['source_file_count','patch_bytes','patch_sha256','reverse_apply_check','staged_files']},indent=2))
if __name__=='__main__':main()
