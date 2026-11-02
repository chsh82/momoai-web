"""Disposable repositories exercise production release orchestration."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]

def load():
    p=ROOT/'scripts/deploy_scoped_makeup.py'
    assert p.exists(), 'scoped deployment implementation missing'
    spec=importlib.util.spec_from_file_location('scoped_makeup_deploy',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

@pytest.mark.parametrize('failure',[None,'install','receipt','receipt_write','final_receipt_write','health','rollback'])
def test_transaction_and_rollback(tmp_path,monkeypatch,failure):
    m=load(); repo=tmp_path/'repo';repo.mkdir()
    def git(*a):return subprocess.check_output(['git',*a],cwd=repo,text=True).strip()
    git('init');git('config','user.email','fixture@invalid');git('config','user.name','fixture');git('config','core.autocrlf','false')
    name='app/admin/routes.py';p=repo/name;p.parent.mkdir(parents=True);p.write_text('# old\n')
    other=repo/'other.txt';other.write_text('baseline')
    git('add','.');git('commit','-m','baseline');old=git('rev-parse','HEAD')
    p.write_text('# new\n');addition=repo/'app/utils/notification_transaction.py';addition.parent.mkdir();addition.write_text('# added\n')
    git('add','.');git('commit','-m','release');new=git('rev-parse','HEAD')
    plan={n:m.sha(repo/n) for n in [name,'app/utils/notification_transaction.py']}
    git('read-tree',old);git('update-ref','HEAD',old,new);p.write_text('# old\n');addition.unlink()
    other.write_text('dirty live overlay');(repo/'untracked.txt').write_text('untracked overlay')
    db=repo/'instance/momoai.db';db.parent.mkdir()
    with sqlite3.connect(db) as c:c.execute('CREATE TABLE preserved(id INTEGER PRIMARY KEY,value TEXT)');c.execute("INSERT INTO preserved VALUES(1,'unchanged')")
    events=[]
    def service(action):
        events.append(action)
        if failure=='rollback' and action=='start' and events.count('start')==2:raise RuntimeError('rollback service failure')
    def health():
        if failure in ('health','rollback') and events.count('start')==1:raise RuntimeError('injected health')
    def hook(point):
        if point==failure and failure in ('install','receipt'):raise RuntimeError('injected '+point)
    if failure in ('receipt_write','final_receipt_write'):
        write=Path.write_text
        target_status='files_verified' if failure=='receipt_write' else 'deployed'
        def broken_write(path,text,*a,**kw):
            if path.name=='receipt.tmp' and json.loads(text)['status']==target_status:
                raise RuntimeError('injected actual receipt write')
            return write(path,text,*a,**kw)
        monkeypatch.setattr(Path,'write_text',broken_write)
    args=(repo,old,new,plan,tmp_path/'backups',service,health,lambda:None,lambda:None)
    if failure:
        with pytest.raises(RuntimeError):m.deploy(*args,inject=hook)
    else:m.deploy(*args,inject=hook)
    receipt=json.loads(next((tmp_path/'backups').glob('*/receipt.json')).read_text())
    assert receipt['status']==('deployed' if not failure else 'rollback_failed' if failure=='rollback' else 'rolled_back')
    assert git('rev-parse','HEAD')==(new if not failure else old)
    assert p.read_text()==('# new\n' if not failure else '# old\n')
    assert addition.exists()==(not failure)
    assert other.read_text()=='dirty live overlay'
    assert (repo/'untracked.txt').read_text()=='untracked overlay'
    with sqlite3.connect(db) as c:assert c.execute('SELECT * FROM preserved').fetchall()==[(1,'unchanged')]
    assert events[0]=='stop'
    assert (Path(receipt['backup_directory'])/'database-before.sqlite').exists()


def test_preserves_file_hashes_including_untracked(tmp_path):
    m=load();subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    (tmp_path/'overlay.py').write_text('untracked')
    assert m.inventory(tmp_path,[])=={'overlay.py':m.sha(tmp_path/'overlay.py')}
