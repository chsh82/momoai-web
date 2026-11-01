"""Scoped essay release with stopped-worker migration, backups and file rollback.

Run only after explicit release approval. Does not import the production factory.
"""
import hashlib
import importlib.util
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def switch_files(repo, stage, backup, files, hook):
    before={}; installed=[]
    for name in files:
        target=repo/name
        assert not target.is_symlink()
        before[name]=target.exists()
        if target.exists():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,saved)
    try:
        for name in files:
            target=repo/name;target.parent.mkdir(parents=True,exist_ok=True)
            os.replace(stage/name,target);installed.append(name)
            hook('install')
        hook('receipt')
        hook('health')
    except BaseException as original:
        try:
            hook('before_rollback')
            for name in reversed(installed):
                target=repo/name
                if before[name]:
                    restore=backup/name
                    assert restore.is_file(), 'Missing rollback file '+name
                    shutil.copy2(restore,target)
                else:
                    target.unlink(missing_ok=True)
            hook('rollback')
        except BaseException as failure:
            raise RuntimeError('ROLLBACK FAILED: '+str(failure)) from original
        raise


def rows_signature(connection, tables):
    signatures={}
    for table in sorted(tables):
        quoted='"'+table.replace('"','""')+'"'
        columns=[r[1] for r in connection.execute('PRAGMA table_info('+quoted+')')]
        h=hashlib.sha256();count=0
        for row in connection.execute('SELECT * FROM '+quoted+' ORDER BY '+','.join(str(i+1) for i in range(len(columns)))):
            h.update(repr(row).encode('utf-8'));h.update(b'\n');count+=1
        signatures[table]={'rows':count,'sha256':h.hexdigest()}
    return signatures


def migrate_database(db_path, migration_path, backup_path):
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
        assert target.execute('PRAGMA integrity_check').fetchone()==('ok',)
        names={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        baseline=rows_signature(source,names-{'alembic_version','sqlite_sequence'})
        old_fk=source.execute('PRAGMA foreign_key_check').fetchall()
        assert source.execute('SELECT version_num FROM alembic_version').fetchall()==[('0548f00b2524',)]
        assert not names & {'essay_teacher_grants','essay_correction_jobs'}
    spec=importlib.util.spec_from_file_location('scoped_essay_migration',migration_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.down_revision=='0548f00b2524' and module.revision=='aa31b9d8e620'
    engine=sa.create_engine('sqlite:///'+str(db_path))
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                module.op=Operations(MigrationContext.configure(connection))
                module.upgrade()
                changed=connection.exec_driver_sql("UPDATE alembic_version SET version_num='aa31b9d8e620' WHERE version_num='0548f00b2524'").rowcount
                assert changed==1
                raw=connection.connection.driver_connection
                assert rows_signature(raw,names-{'alembic_version','sqlite_sequence'})==baseline
                assert raw.execute('PRAGMA foreign_key_check').fetchall()==old_fk
                assert raw.execute('PRAGMA integrity_check').fetchone()==('ok',)
                assert raw.execute('SELECT count(*) FROM essay_teacher_grants').fetchone()==(0,)
                assert raw.execute('SELECT count(*) FROM essay_correction_jobs').fetchone()==(0,)
                connection.commit()
            except BaseException:
                connection.rollback();raise
    finally:
        engine.dispose()
    return {'existing_table_signatures':baseline,'preexisting_fk_findings':len(old_fk),'migration':'aa31b9d8e620'}


def main():
    import fcntl
    repo=Path.home()/'momoai_web'
    old,new,plan_path=sys.argv[1:]
    assert len(old)==len(new)==40 and all(x in '0123456789abcdef' for x in old+new)
    plan=json.loads(Path(plan_path).read_text())
    def git(*args): return subprocess.check_output(['git',*args],cwd=repo).decode().strip()
    def service(action): subprocess.run(['sudo','-n','systemctl',action,'momoai'],check=True)
    def confirm_health():
        for attempt in range(20):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/auth/login',timeout=5) as response:
                    assert response.status==200
                break
            except Exception:
                if attempt==19: raise
                time.sleep(1)
        subprocess.run(['systemctl','is-active','--quiet','momoai'],check=True)
    assert git('rev-parse','HEAD')==old
    assert git('merge-base',old,new)==old
    assert set(git('diff','--name-only',old,new).splitlines())==set(plan)
    assert not git('diff','--name-only','--diff-filter=D',old,new)
    protected=['config.py','.github/workflows/deploy.yml','app/news/__init__.py','templates/news/hub.html']
    guards={n:sha(repo/n) for n in protected}
    for name in plan:
        p=Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        assert name.startswith(('app/essays/','app/services/essay_','app/services/correction_jobs.','templates/essays/','tests/essay_delivery/','reports/essay-release/')) or name in ('app/__init__.py','app/models/essay.py','app/teacher/routes.py','app/parent_portal/routes.py','app/student_portal/routes.py','app/library/routes.py','templates/parent/essay_submit.html','templates/student/submit_essay.html','templates/teacher/assignments.html','templates/teacher/attendance_list.html','templates/library/admin/hall_of_fame_form.html','templates/library/admission_info_detail.html','templates/library/hall_of_fame_detail.html','static/css/tailwind.min.css','static/css/style.min.css','migrations/versions/aa31b9d8e620_standalone_essay_delivery.py','scripts/deploy_scoped_essay.py')
        target=repo/name
        previous=subprocess.run(['git','show',old+':'+name],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        assert (target.exists() and target.read_bytes()==previous.stdout) if previous.returncode==0 else not target.exists(), 'Live scoped collision: '+name
    root=Path.home()/'momoai-release-backups';root.mkdir(mode=0o700,exist_ok=True)
    lock=(root/'.essay-release.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    release=Path(tempfile.mkdtemp(prefix='essay-'+new[:12]+'-',dir=root))
    stage=release/'stage';stage.mkdir();backup=release/'before';backup.mkdir()
    for name,expected in plan.items():
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','show',new+':'+name],cwd=repo))
        assert sha(target)==expected
        if target.suffix=='.py': compile(target.read_bytes(),name,'exec')
    receipt={'old_commit':old,'new_commit':new,'plan':plan,'backup_directory':str(release),'protected_before':guards,'status':'prepared'}
    receipt_path=release/'receipt.json'
    def save(): receipt_path.write_text(json.dumps(receipt,indent=2))
    save()
    assert git('rev-parse','HEAD')==old
    assert {n:sha(repo/n) for n in protected}==guards
    migration_name='migrations/versions/aa31b9d8e620_standalone_essay_delivery.py'
    migrated=False;started=False
    def hook(point):
        nonlocal migrated,started
        if point=='install':
            receipt['status']='installing'
        elif point=='receipt':
            receipt['status']='files_installed';save()
        elif point=='health':
            receipt.update(migrate_database(repo/'instance/momoai.db',repo/migration_name,release/'database-before.sqlite'))
            migrated=True
            assert all(sha(repo/n)==value for n,value in plan.items())
            assert {n:sha(repo/n) for n in protected}==guards
            receipt['status']='schema_verified';save()
            started=True;service('start')
            confirm_health()
            subprocess.run(['git','reset','--mixed',new],cwd=repo,check=True,stdout=subprocess.DEVNULL)
            assert git('rev-parse','HEAD')==new
            receipt['status']='deployed';receipt['service_pid']=subprocess.check_output(['systemctl','show','momoai','-p','MainPID','--value'],text=True).strip();save()
        elif point=='before_rollback':
            service('stop')
        elif point=='rollback':
            # Never restore the database after the service may have accepted writes.
            # The two new tables are additive; retain their migration file on rollback.
            if migrated:
                (repo/migration_name).write_bytes(subprocess.check_output(['git','show',new+':'+migration_name],cwd=repo))
            if git('rev-parse','HEAD')==new: subprocess.run(['git','reset','--mixed',old],cwd=repo,check=True,stdout=subprocess.DEVNULL)
            service('start');confirm_health()
            receipt.update(status='rolled_back',additive_schema_retained=migrated)
            try:
                save()
            except BaseException:
                receipt['status']='rollback_failed'
                raise
    try:
        service('stop')
        assert subprocess.check_output(['systemctl','show','momoai','-p','MainPID','--value'],text=True).strip()=='0', 'Old workers not stopped'
        switch_files(repo,stage,backup,list(plan),hook)
    except BaseException as error:
        receipt.update(error_type=type(error).__name__)
        if receipt.get('status')=='prepared':
            service('start')
            receipt['status']='aborted_before_install'
        elif receipt.get('status')!='rolled_back':
            receipt['status']='rollback_failed'
        save();raise
    print(json.dumps({'status':receipt['status'],'old_commit':old,'new_commit':new,'backup_directory':str(release),'service_pid':receipt.get('service_pid'),'migration':receipt.get('migration'),'files_verified':len(plan),'records_preserved':True,'protected_unchanged':guards},sort_keys=True))


if __name__=='__main__': main()
