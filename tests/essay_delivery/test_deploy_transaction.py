"""Exercise file-switch transaction before a production deployment."""
import importlib.util
from pathlib import Path
import pytest


def module():
    path=Path(__file__).parents[2]/'scripts/deploy_scoped_essay.py'
    assert path.exists(), 'transactional deployment module missing'
    spec=importlib.util.spec_from_file_location('essay_deploy',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('failure', ['install','receipt','health'])
def test_failure_restores_bytes_additions_and_restart_intent(tmp_path, failure):
    m=module()
    repo=tmp_path/'repo';stage=tmp_path/'stage';backup=tmp_path/'backup'
    repo.mkdir();stage.mkdir();backup.mkdir()
    (repo/'existing.py').write_text('old')
    (stage/'existing.py').write_text('new')
    (stage/'addition.py').write_text('addition')
    events=[]
    def hook(point):
        events.append(point)
        if point==failure: raise RuntimeError('injected '+point)
    with pytest.raises(RuntimeError, match='injected'):
        m.switch_files(repo,stage,backup,['existing.py','addition.py'],hook)
    assert (repo/'existing.py').read_text()=='old'
    assert not (repo/'addition.py').exists()
    assert events[-1]=='rollback'


def test_partial_rollback_failure_is_not_reported_as_success(tmp_path):
    m=module();repo=tmp_path/'repo';stage=tmp_path/'stage';backup=tmp_path/'backup'
    repo.mkdir();stage.mkdir();backup.mkdir()
    (repo/'existing.py').write_text('old');(stage/'existing.py').write_text('new')
    def hook(point):
        if point=='receipt':
            (backup/'existing.py').unlink()
            raise RuntimeError('injected receipt')
    with pytest.raises(RuntimeError, match='ROLLBACK FAILED'):
        m.switch_files(repo,stage,backup,['existing.py'],hook)


def test_migration_transaction_preserves_existing_records_and_rolls_back_ddl(tmp_path):
    import sqlite3
    m=module()
    path=tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as c:
        c.executescript("CREATE TABLE users(user_id TEXT PRIMARY KEY); CREATE TABLE students(student_id TEXT PRIMARY KEY); CREATE TABLE essays(essay_id TEXT PRIMARY KEY); CREATE TABLE preserved(id INTEGER PRIMARY KEY,value TEXT); INSERT INTO preserved VALUES(1,'unchanged'); CREATE TABLE alembic_version(version_num TEXT PRIMARY KEY); INSERT INTO alembic_version VALUES('0548f00b2524');")
    migration=Path(__file__).parents[2]/'migrations/versions/aa31b9d8e620_standalone_essay_delivery.py'
    info=m.migrate_database(path,migration,tmp_path/'backup.sqlite')
    assert info['existing_table_signatures']['preserved']['rows']==1
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT * FROM preserved').fetchall()==[(1,'unchanged')]
        assert c.execute('SELECT version_num FROM alembic_version').fetchall()==[('aa31b9d8e620',)]
    # Roll back a migration that fails after its first DDL statement.
    failed=tmp_path/'failed.sqlite'
    with sqlite3.connect(tmp_path/'backup.sqlite') as a, sqlite3.connect(failed) as b: a.backup(b)
    broken=tmp_path/'broken.py'
    broken.write_text("revision='aa31b9d8e620'\ndown_revision='0548f00b2524'\ndef upgrade():\n    import sqlalchemy as sa\n    op.create_table('partial',sa.Column('id',sa.Integer))\n    raise RuntimeError('injected migration')\n")
    with pytest.raises(RuntimeError,match='injected migration'):
        m.migrate_database(failed,broken,tmp_path/'failed-backup.sqlite')
    with sqlite3.connect(failed) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchall()==[]
        assert c.execute('SELECT * FROM preserved').fetchall()==[(1,'unchanged')]
        assert c.execute('SELECT version_num FROM alembic_version').fetchall()==[('0548f00b2524',)]
