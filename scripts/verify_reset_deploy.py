"""Read-only fail-closed guard before reset-based production deployment.
Never changes Git refs/index/files, runs migrations, starts the app or reads DBs.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path

def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo)
def verify(repo,target):
    repo=Path(repo)
    target=git(repo,'rev-parse','--verify',target+'^{commit}').decode().strip()
    head=git(repo,'rev-parse','HEAD').decode().strip()
    history=subprocess.run(['git','merge-base','--is-ancestor',head,target],cwd=repo,capture_output=True)
    if history.returncode!=0:raise RuntimeError('Unpublished/divergent live commits: '+head+' is not an ancestor of '+target)
    # -v lowercases assume-unchanged entries; S/s marks skip-worktree.
    # Reject before diff: either flag can hide divergent on-disk source bytes.
    hidden=[entry[2:].decode() for entry in git(repo,'ls-files','-v','-z').split(b'\0')
            if entry and (entry[:1]==b'S' or entry[:1].islower())]
    if hidden:raise RuntimeError('Unsafe Git index flags (assume-unchanged/skip-worktree): '+', '.join(sorted(hidden)))
    if git(repo,'diff','--cached','--name-only','-z'):raise RuntimeError('Existing staged production changes')
    tracked=set(x.decode() for x in git(repo,'ls-tree','-r','--name-only','-z',target).split(b'\0') if x)
    changed=set(x.decode() for x in git(repo,'diff','--name-only','-z','HEAD','--').split(b'\0') if x)
    untracked=set(x.decode() for x in git(repo,'ls-files','--others','--exclude-standard','-z').split(b'\0') if x)
    cached=set(x.decode() for x in git(repo,'ls-files','--cached','-z').split(b'\0') if x)
    # Include ignored collisions without enumerating private uploads or databases.
    collisions={name for name in tracked-cached if (repo/name).exists() or (repo/name).is_symlink()}
    # A reset may also remove an untracked file/symlink blocking a new directory.
    blocked_parents=set()
    for name in tracked:
        for parent in (repo/name).parents:
            if parent==repo:break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                blocked_parents.add(parent.relative_to(repo).as_posix())
    if blocked_parents:raise RuntimeError('Live parent paths would be overwritten: '+', '.join(sorted(blocked_parents)))
    candidates=changed|collisions;rejected=[]
    for name in sorted(candidates):
        path=repo/name
        if any(parent.is_symlink() for parent in [path,*path.parents] if parent.is_relative_to(repo)):
            rejected.append(name);continue
        blob=subprocess.run(['git','show',target+':'+name],cwd=repo,capture_output=True)
        if blob.returncode:
            if path.exists():rejected.append(name)
        elif not path.is_file() or hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(blob.stdout).digest():rejected.append(name)
    if rejected:raise RuntimeError('Unsynced live source would be overwritten: '+', '.join(rejected))
    return {'status':'safe_to_reset','head':head,'target':target,'adopted_exact_live_paths':sorted(candidates),'unrelated_untracked_paths_preserved':len(untracked-tracked)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--target',required=True)
    args=parser.parse_args()
    try:result=verify(args.repo,args.target)
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        print(json.dumps({'status':'blocked_before_reset','reason':str(exc)},ensure_ascii=False));return 1
    print(json.dumps(result,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
