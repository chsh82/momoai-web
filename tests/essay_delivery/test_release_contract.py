"""Release contract: standalone implementation must not publish student-hub prerequisites."""
from pathlib import Path
import ast
import importlib.util
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def test_delivery_is_standalone_and_preserves_unrelated_features():
    assert (ROOT / 'app/services/essay_scope.py').exists(), 'standalone essay scope missing'
    assert (ROOT / 'migrations/versions/aa31b9d8e620_standalone_essay_delivery.py').exists(), 'standalone migration missing'
    for name in ['app/essays/routes.py','app/services/essay_delivery.py','app/services/correction_jobs.py']:
        source=(ROOT/name).read_text(encoding='utf-8-sig')
        assert 'student_hub' not in source, name + ' still depends on unpublished student hub'
    for name in ['config.py','app/models/notification.py','app/models/ace_evaluation.py','app/models/consultation.py','.github/workflows/deploy.yml','app/news/__init__.py','templates/news/hub.html']:
        expected=subprocess.check_output(['git','show','de9ff0d0fc5399dffabbb4d7d2a48d263c942d14:'+name],cwd=ROOT)
        assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n') == expected.replace(b'\r\n',b'\n'), name


def test_standalone_migration_adds_only_two_tables_and_preserves_all_rows(kernel):
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.models import db
    app, db, root = kernel
    path=ROOT/'migrations/versions/aa31b9d8e620_standalone_essay_delivery.py'
    assert path.exists(), 'release migration must follow live head, not unpublished hub'
    spec=importlib.util.spec_from_file_location('scoped_essay_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.down_revision == '0548f00b2524'
    legacy=sa.MetaData()
    for table in db.metadata.tables.values():
        if table.name not in ('essay_teacher_grants','essay_correction_jobs'): table.to_metadata(legacy)
    with db.engine.begin() as connection:
        legacy.create_all(connection)
        t=legacy.tables
        connection.execute(t['users'].insert().values(user_id='u',email='u@example.invalid',password_hash='synthetic',name='synthetic'))
        connection.execute(t['students'].insert().values(student_id='s',teacher_id='u',name='synthetic',grade='초5'))
        connection.execute(t['essays'].insert().values(essay_id='e',student_id='s',user_id='u',original_text='preserved',grade='초5'))
        before={n:connection.execute(sa.select(t)).all() for n,t in legacy.tables.items()}
        module.op=Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert set(sa.inspect(connection).get_table_names()) == set(legacy.tables)|{'essay_teacher_grants','essay_correction_jobs'}
        for n,t in legacy.tables.items(): assert connection.execute(sa.select(t)).all() == before[n]
        assert connection.exec_driver_sql('PRAGMA integrity_check').scalar() == 'ok'
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        module.downgrade()
        for n,t in legacy.tables.items(): assert connection.execute(sa.select(t)).all() == before[n]
