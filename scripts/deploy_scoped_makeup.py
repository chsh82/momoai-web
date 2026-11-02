"""Approved no-migration file release; preserve every unrelated Git overlay.
No factory import, reset --hard, automatic master deploy, or database restore.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

RUNTIME={
    'app/admin/routes.py','app/models/makeup_request.py','app/models/notification.py',
    'app/utils/course_utils.py','app/utils/notification_transaction.py',
    'templates/admin/makeup_requests.html','static/css/tailwind.min.css',
}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo)


def inventory(repo,exclude):
    names=set(x.decode() for x in git(repo,'ls-files','--cached','--others','--exclude-standard','-z').split(b'\0') if x)
    if (repo/'.env').is_file():names.add('.env')
    result={}
    for name in sorted(names-set(exclude)):
        target=repo/name
        assert not target.is_symlink(), 'Unexpected source symlink '+name
        if target.is_file():result[name]=sha(target)
        else:result[name]=None
    return result


def rows_signature(c):
    result={}
    for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        q='"'+table.replace('"','""')+'"'
        cols=c.execute('PRAGMA table_info('+q+')').fetchall()
        h=hashlib.sha256();count=0
        for row in c.execute('SELECT * FROM '+q+' ORDER BY '+','.join(str(i+1) for i in range(len(cols)))):
            h.update(repr(row).encode());h.update(b'\n');count+=1
        result[table]={'rows':count,'sha256':h.hexdigest()}
    return result


def database_snapshot(repo,backup=None):
    with sqlite3.connect('file:'+str(repo/'instance/momoai.db')+'?mode=ro',uri=True) as c:
        assert c.execute('PRAGMA quick_check').fetchone()==('ok',)
        if backup:
            with sqlite3.connect(backup) as b:
                c.backup(b)
                assert b.execute('PRAGMA quick_check').fetchone()==('ok',)
        return rows_signature(c)


def deploy(repo,old,new,plan,backup_root,service,health,stopped,active_check,inject=lambda point:None):
    assert len(old)==len(new)==40 and all(x in '0123456789abcdef' for x in old+new)
    assert all(n in RUNTIME or n.startswith(('tests/makeup_direct_approval/','tests/scoped_makeup_release/','reports/makeup-approval-search/')) or n=='scripts/deploy_scoped_makeup.py' for n in plan)
    assert git(repo,'rev-parse','HEAD').decode().strip()==old
    assert git(repo,'merge-base',old,new).decode().strip()==old
    assert not git(repo,'diff','--cached','--name-only').strip(), 'Preserve unrelated staging: abort'
    changed=set(git(repo,'diff','--name-only',old,new).decode().splitlines())
    assert changed==set(plan)
    for n in changed:
        assert n in RUNTIME or n.startswith(('tests/makeup_direct_approval/','tests/scoped_makeup_release/','reports/makeup-approval-search/')) or n=='scripts/deploy_scoped_makeup.py', 'Out-of-scope commit '+n
    guards=inventory(repo,plan)
    for name in plan:
        p=repo/name;assert not p.is_symlink()
        before=subprocess.run(['git','show',old+':'+name],cwd=repo,capture_output=True)
        assert (p.exists() and p.read_bytes()==before.stdout) if before.returncode==0 else not p.exists(), 'Live target collision '+name
    backup_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    release=Path(tempfile.mkdtemp(prefix='makeup-'+new[:12]+'-',dir=backup_root));release.chmod(0o700)
    stage=release/'stage';before_dir=release/'before';stage.mkdir();before_dir.mkdir()
    existed={}
    for name,expected in plan.items():
        p=stage/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(git(repo,'show',new+':'+name));assert sha(p)==expected
        if p.suffix=='.py':compile(p.read_bytes(),name,'exec')
        existed[name]=(repo/name).exists()
        if existed[name]:
            target=before_dir/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    receipt={'status':'prepared','old_commit':old,'new_commit':new,'backup_directory':str(release),'runtime_manifest':plan,'unrelated_before':guards,'migration':'none','upstream_sync_required':True}
    receipt_path=release/'receipt.json'
    def save():
        p=release/'receipt.tmp';p.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));os.replace(p,receipt_path)
    save();installed=[];was_stopped=False
    try:
        active_check();health()
        service('stop');was_stopped=True;stopped();active_check()
        assert inventory(repo,plan)==guards, 'Overlay changed during preflight'
        receipt['database_before']=database_snapshot(repo,release/'database-before.sqlite');save()
        for name in plan:
            target=repo/name;target.parent.mkdir(parents=True,exist_ok=True)
            os.replace(stage/name,target);installed.append(name);inject('install')
        receipt['database_after_stopped']=database_snapshot(repo)
        assert receipt['database_after_stopped']==receipt['database_before']
        assert inventory(repo,plan)==guards
        assert all(sha(repo/n)==v for n,v in plan.items())
        receipt['status']='files_verified';inject('receipt');save()
        # Explicit HEAD/index only; the unrelated working overlay remains untouched.
        subprocess.run(['git','read-tree',new],cwd=repo,check=True)
        subprocess.run(['git','update-ref','HEAD',new,old],cwd=repo,check=True)
        service('start');inject('health');health()
        assert inventory(repo,plan)==guards
        receipt.update(status='deployed',unrelated_after=inventory(repo,plan),database_after_start=database_snapshot(repo),records_unchanged_while_stopped=True)
        assert all(sha(repo/n)==v for n,v in plan.items())
        save()
    except BaseException as error:
        receipt['error_type']=type(error).__name__;receipt['error']=str(error)
        try:
            if was_stopped:
                service('stop');stopped()
                for name in reversed(installed):
                    target=repo/name
                    if existed[name]:shutil.copy2(before_dir/name,target)
                    else:target.unlink(missing_ok=True)
                current=git(repo,'rev-parse','HEAD').decode().strip()
                if current==new:
                    subprocess.run(['git','read-tree',old],cwd=repo,check=True)
                    subprocess.run(['git','update-ref','HEAD',old,new],cwd=repo,check=True)
                assert inventory(repo,plan)==guards
                service('start');health()
            receipt['status']='rolled_back' if was_stopped else 'aborted_before_stop';save()
        except BaseException as rollback_error:
            receipt.update(status='rollback_failed',rollback_error=str(rollback_error));save()
            raise RuntimeError('ROLLBACK FAILED: '+str(rollback_error)) from error
        raise
    return receipt


def main():
    import fcntl
    from datetime import datetime, timezone
    repo=Path('/home/chsh82/momoai_web');old,new,plan_file=sys.argv[1:]
    plan=json.loads(Path(plan_file).read_text())
    root=Path('/home/chsh82/momoai-release-backups');root.mkdir(exist_ok=True,mode=0o700)
    lock=(root/'.scoped-release.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def service(action):subprocess.run(['sudo','-n','systemctl',action,'momoai'],check=True)
    def stopped():
        assert subprocess.check_output(['systemctl','show','momoai','-p','MainPID','--value'],text=True).strip()=='0'
        cgroup=Path('/sys/fs/cgroup/system.slice/momoai.service/cgroup.procs')
        assert not cgroup.exists() or not cgroup.read_text().strip(), 'Old worker cgroup not empty'
    pid=subprocess.check_output(['systemctl','show','momoai','-p','MainPID','--value'],text=True).strip()
    started=subprocess.check_output(['ps','-p',pid,'-o','lstart='],text=True).strip()
    boot=datetime.fromtimestamp(datetime.strptime(started,'%a %b %d %H:%M:%S %Y').timestamp(),timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    def active_check():
        with sqlite3.connect('file:'+str(repo/'instance/momoai.db')+'?mode=ro',uri=True) as c:
            assert c.execute("SELECT count(*) FROM essay_correction_jobs WHERE state IN ('prepared','dispatched','running')").fetchone()==(0,), 'Active correction jobs; retry later'
            for table in ('essays','ocr_history'):
                assert c.execute('SELECT count(*) FROM '+table+" WHERE status='processing' AND created_at>=?",(boot,)).fetchone()==(0,), 'Active '+table+' work; retry later'
    def health():
        for attempt in range(30):
            try:
                req=urllib.request.Request('http://127.0.0.1:8000/auth/login',headers={'Host':'momoai.kr'})
                with urllib.request.urlopen(req,timeout=5) as response:assert response.status==200
                subprocess.run(['systemctl','is-active','--quiet','momoai'],check=True)
                return
            except Exception:
                if attempt==29:raise
                time.sleep(1)
    result=deploy(repo,old,new,plan,root,service,health,stopped,active_check)
    print(json.dumps({'status':result['status'],'receipt':result['backup_directory']+'/receipt.json','new_commit':new,'runtime_files':len(plan)},sort_keys=True))

if __name__=='__main__':main()
