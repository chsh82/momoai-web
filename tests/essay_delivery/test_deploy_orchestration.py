"""Run real main/file/Git orchestration; never contact a service or network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    path = Path(__file__).parents[2] / 'scripts/deploy_scoped_essay.py'
    spec = importlib.util.spec_from_file_location('essay_deploy_main', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    repo = tmp_path / 'momoai_web'
    repo.mkdir()
    run = subprocess.run
    def git(*args):
        return run(['git', *args], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    git('init')
    git('config', 'core.autocrlf', 'false')
    git('config', 'user.email', 'fixture@example.invalid')
    git('config', 'user.name', 'Disposable fixture')
    protected = ['config.py', '.github/workflows/deploy.yml', 'app/news/__init__.py', 'templates/news/hub.html']
    existing = 'app/essays/existing.py'
    addition = 'app/essays/addition.py'
    migration = 'migrations/versions/aa31b9d8e620_standalone_essay_delivery.py'
    for name in protected + [existing]:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# old ' + name + '\n')
    git('add', '.')
    git('commit', '-m', 'old fixture')
    old = git('rev-parse', 'HEAD')
    for name in [existing, addition, migration]:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# new ' + name + '\n')
    git('add', '.')
    git('commit', '-m', 'new fixture')
    new = git('rev-parse', 'HEAD')
    plan = {n: hashlib.sha256((repo / n).read_bytes()).hexdigest() for n in [existing, addition, migration]}
    new_migration = (repo / migration).read_bytes()
    git('reset', '--hard', old)
    # Unrelated live changes must survive both installation and rollback.
    (repo / protected[-1]).write_text('dirty live news')
    guards = {n: (repo / n).read_bytes() for n in protected}
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text(json.dumps(plan))
    monkeypatch.setattr(m.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(sys, 'argv', ['deploy', old, new, str(plan_path)])
    monkeypatch.setitem(sys.modules, 'fcntl', types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *a: None))
    events = []
    state = {'starts': 0, 'rollback_restart_failure': False, 'rollback_http_failure': False}
    def fake_run(args, **kwargs):
        if args[0] == 'git':
            return run(args, **kwargs)
        assert args[0] in ('sudo', 'systemctl'), args
        if args[0] == 'sudo':
            action = args[-2]
            events.append(action)
            if action == 'start':
                state['starts'] += 1
                if state['starts'] == 2 and state['rollback_restart_failure']:
                    raise RuntimeError('injected rollback restart')
        else:
            assert args == ['systemctl', 'is-active', '--quiet', 'momoai']
            events.append('active')
        return subprocess.CompletedProcess(args, 0)
    check_output = subprocess.check_output
    def fake_output(args, **kwargs):
        if args[0] == 'git':
            return check_output(args, **kwargs)
        assert args == ['systemctl', 'show', 'momoai', '-p', 'MainPID', '--value']
        return '0\n'
    monkeypatch.setattr(m.subprocess, 'run', fake_run)
    monkeypatch.setattr(m.subprocess, 'check_output', fake_output)
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: None)
    db = repo / 'instance/momoai.db'
    db.parent.mkdir()
    db.write_bytes(b'original records')
    def migrate(db_path, migration_path, backup_path):
        events.append('migration')
        assert migration_path.read_bytes() == new_migration
        backup_path.write_bytes(db_path.read_bytes())
        db_path.write_bytes(b'committed additive schema and preserved records')
        return {'migration': 'aa31b9d8e620'}
    monkeypatch.setattr(m, 'migrate_database', migrate)
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    def urlopen(url, timeout):
        assert url == 'http://127.0.0.1:8000/auth/login' and timeout == 5
        events.append('http')
        if state['starts'] == 1 or state['rollback_http_failure']:
            raise RuntimeError('injected HTTP health')
        assert git('rev-parse', 'HEAD') == old
        assert (repo / existing).read_text() == '# old ' + existing + '\n'
        assert not (repo / addition).exists()
        return Response()
    monkeypatch.setattr(m.urllib.request, 'urlopen', urlopen)
    def receipt():
        paths = list((tmp_path / 'momoai-release-backups').glob('essay-*/receipt.json'))
        assert len(paths) == 1
        return json.loads(paths[0].read_text())
    def preserved():
        assert git('rev-parse', 'HEAD') == old
        assert (repo / existing).read_text() == '# old ' + existing + '\n'
        assert not (repo / addition).exists()
        assert (repo / migration).read_bytes() == new_migration
        assert {n: (repo / n).read_bytes() for n in protected} == guards
        assert db.read_bytes() == b'committed additive schema and preserved records'
        assert Path(receipt()['backup_directory'], 'database-before.sqlite').read_bytes() == b'original records'
    return types.SimpleNamespace(m=m, events=events, state=state, receipt=receipt, preserved=preserved)


def test_postmigration_health_failure_confirms_old_service_before_rollback_receipt(deployment):
    d = deployment
    with pytest.raises(RuntimeError, match='injected HTTP health'):
        d.m.main()
    assert d.receipt()['status'] == 'rolled_back'
    assert d.receipt()['additive_schema_retained'] is True
    assert d.events[-3:] == ['start', 'http', 'active']
    d.preserved()


@pytest.mark.parametrize('failure', ['restart', 'http', 'active', 'receipt'])
def test_rollback_failure_is_explicit_not_reported_as_rolled_back(deployment, monkeypatch, failure):
    d = deployment
    d.state['rollback_restart_failure'] = failure == 'restart'
    d.state['rollback_http_failure'] = failure == 'http'
    if failure == 'active':
        run = d.m.subprocess.run
        def inactive(args, **kwargs):
            if args[0] == 'systemctl' and args[1] == 'is-active':
                raise RuntimeError('injected inactive rollback')
            return run(args, **kwargs)
        monkeypatch.setattr(d.m.subprocess, 'run', inactive)
    if failure == 'receipt':
        write_text = Path.write_text
        failed = False
        def fail_receipt_once(path, text, *args, **kwargs):
            nonlocal failed
            if path.name == 'receipt.json' and json.loads(text)['status'] == 'rolled_back' and not failed:
                failed = True
                raise OSError('injected rollback receipt')
            return write_text(path, text, *args, **kwargs)
        monkeypatch.setattr(Path, 'write_text', fail_receipt_once)
    with pytest.raises(RuntimeError, match='ROLLBACK FAILED'):
        d.m.main()
    assert d.receipt()['status'] == 'rollback_failed'
    assert d.receipt()['error_type'] == 'RuntimeError'
    d.preserved()
