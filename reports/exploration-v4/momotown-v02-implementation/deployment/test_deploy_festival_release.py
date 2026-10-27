"""Local-only tests: no SSH, network, systemctl or production application import."""
import importlib.util
from pathlib import Path
import unittest
import os

HERE = Path(__file__).parent
# Explicit scratch avoids Windows tempfile choosing system/vendor TEMP first.
TEMP_ROOT = Path(os.environ.get('HERMES_TEST_SCRATCH',
    str(Path.home() / 'AppData/Local/hermes/profiles/momo/cache/scratch')
    if os.name == 'nt' else str(HERE / '.test-scratch')))
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
SPEC = importlib.util.spec_from_file_location('festival_deploy', HERE / 'deploy_festival_release.py')
D = importlib.util.module_from_spec(SPEC) if SPEC and SPEC.loader and SPEC.origin and Path(SPEC.origin).exists() else None
if D:
    SPEC.loader.exec_module(D)


class ManifestTests(unittest.TestCase):
    def test_manifest_rejects_unapproved_files(self):
        self.assertIsNotNone(D, 'deployment helper is not implemented')
        for name in ('config.py', 'app/__init__.py', 'app/models/user.py', '../escape',
                     '/absolute', 'app/interest_quest/protected/anything.js',
                     'tests/momotown_backend/../../config.py', 'migrations/new.py',
                     '.github/workflows/deploy.yml'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                D.validate_manifest('1'*40, '2'*40, {name: 'a'*64})


    def test_malformed_commits_hashes_and_empty_manifest_rejected(self):
        for old, new, plan in [
            ('1'*39, '2'*40, {'app/interest_quest/backend.py': 'a'*64}),
            ('1'*40, '1'*40, {'app/interest_quest/backend.py': 'a'*64}),
            ('A'*40, '2'*40, {'app/interest_quest/backend.py': 'a'*64}),
            ('1'*40, '2'*40, {}),
            ('1'*40, '2'*40, {'app/interest_quest/backend.py': 'z'*64}),
            ('1'*40, '2'*40, {'tests/momotown_backend//test.py': 'a'*64}),
        ]:
            with self.subTest(old=old, plan=plan), self.assertRaises(ValueError):
                D.validate_manifest(old, new, plan)

    def test_approved_exact_and_prefix_paths_accepted(self):
        names = list(D.EXACT_ALLOWED) + ['tests/momotown_backend/test_real.py',
            'tests/momotown_frontend/test_browser.py', 'tests/momotown_integration/test_real_blueprint.py',
            'tests/exploration_launch/test_browser.py', D.DEPLOY_DIR + 'README.md']
        plan = {name: 'a'*64 for name in names}
        self.assertEqual(D.validate_manifest('1'*40, '2'*40, plan), plan)

    def test_duplicate_json_keys_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='festival-plan-', dir=TEMP_ROOT) as directory:
            path = Path(directory) / 'plan.json'
            path.write_text('{"same":"a","same":"b"}')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                D.load_plan(path)

    def test_ancestor_symlink_rejected(self):
        from unittest.mock import patch
        path = Path.cwd() / 'fake-symlink-parent' / 'file.py'
        with patch.object(Path, 'is_symlink', lambda p: p.name == 'fake-symlink-parent'):
            with self.assertRaisesRegex(RuntimeError, 'Symlink'):
                D.safe_path(path)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import subprocess
        import hashlib
        import contextlib
        self.assertTrue(hasattr(D, 'Release'), 'transaction and rollback engine not implemented')
        self.tmp = tempfile.TemporaryDirectory(prefix='festival-unit-', dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-c', 'core.autocrlf=false', *args], cwd=self.repo, stderr=subprocess.PIPE).decode().strip()
        self.git = git
        git('init', '-q')
        git('config', 'user.name', 'Local Test')
        git('config', 'user.email', 'test@example.invalid')
        self.original = {
            'config.py': 'class Config:\n    STUDENT_INTEREST_QUEST_ENABLED = False\n    STUDENT_INTEREST_MID_ENABLED = False\n',
            'app/__init__.py': '# factory must never be imported\nraise RuntimeError("Do not import")\n',
            'app/utils/student_launch.py': '# launch\n',
            'app/interest_mid/routes.py': '# mid\n',
            'app/models/user.py': '# models\n',
            '.github/workflows/deploy.yml': '# workflow\n',
            'app/interest_quest/routes.py': '# old routes\n',
        }
        for name, text in self.original.items():
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode())
        git('add', '.')
        git('commit', '-qm', 'old')
        self.old = git('rev-parse', 'HEAD')
        changes = {'app/interest_quest/routes.py': '# new routes\n', 'app/interest_quest/backend.py': 'VALUE = 2\n'}
        self.plan = {}
        for name, text in changes.items():
            (self.repo / name).write_bytes(text.encode())
            self.plan[name] = hashlib.sha256(text.encode()).hexdigest()
        git('add', '.')
        git('commit', '-qm', 'new')
        self.new = git('rev-parse', 'HEAD')
        git('checkout', '-q', self.old)
        outer = self
        class FakeRelease(D.Release):
            def lock(self):
                return contextlib.nullcontext()
            def fetch(self):
                pass
            def active(self):
                return 'active'
            def pid(self):
                return '123'
            def restart_ready(self, phase):
                self.receipt['restarts'].append({'phase': phase, 'command': ['sudo', '-n', 'systemctl', 'restart', 'momoai'], 'active': 'active', 'root_http_status': 200})
                if phase == 'new' and outer.fail_ready:
                    raise RuntimeError('injected readiness failure')
        self.fail_ready = False
        self.release = FakeRelease(self.repo, Path(self.tmp.name) / 'backups', self.old, self.new, self.plan, 'http://127.0.0.1/')

    def test_deploy_hashes_and_restart_receipt(self):
        result = self.release.run()
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.new)
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), '')
        self.assertEqual([r['phase'] for r in result['restarts']], ['new'])
        self.assertEqual(result['direct_private_database_operations'], False)
        self.assertIn('db.create_all', result['startup_database_caveat'])

    def test_failed_readiness_restores_files_head_and_restarts_old(self):
        self.fail_ready = True
        with self.assertRaisesRegex(RuntimeError, 'injected readiness'):
            self.release.run()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertFalse((self.repo / 'app/interest_quest/backend.py').exists())
        self.assertEqual((self.repo / 'app/interest_quest/routes.py').read_bytes(), self.original['app/interest_quest/routes.py'].encode())
        self.assertEqual(self.release.receipt['status'], 'rolled_back')
        self.assertEqual([r['phase'] for r in self.release.receipt['restarts']], ['new', 'old'])

    def test_dirty_tracked_file_rejected(self):
        (self.repo / 'app/interest_quest/routes.py').write_text('# dirty')
        with self.assertRaisesRegex(RuntimeError, 'Dirty tracked'):
            self.release.run()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_untracked_addition_collision_rejected(self):
        (self.repo / 'app/interest_quest/backend.py').write_text('# private collision')
        with self.assertRaisesRegex(RuntimeError, 'collision'):
            self.release.run()

    def test_hash_mismatch_rejected_before_install(self):
        self.release.plan['app/interest_quest/backend.py'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'hash'):
            self.release.run()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_exact_diff_set_required(self):
        del self.release.plan['app/interest_quest/backend.py']
        with self.assertRaisesRegex(RuntimeError, 'diff set'):
            self.release.run()

    def test_false_flags_required_without_import(self):
        (self.repo / 'config.py').write_text('class Config:\n STUDENT_INTEREST_QUEST_ENABLED = True\n STUDENT_INTEREST_MID_ENABLED = False\n')
        with self.assertRaises(RuntimeError):
            self.release.run()

    def test_receipt_io_failure_still_restores_and_restarts_old(self):
        from unittest.mock import patch
        real_write = Path.write_text
        def disk_full(path, *args, **kwargs):
            if path.name == 'receipt.tmp' and self.release.installed:
                raise OSError('injected receipt disk full')
            return real_write(path, *args, **kwargs)
        with patch.object(Path, 'write_text', disk_full):
            with self.assertRaisesRegex(OSError, 'injected receipt disk full'):
                self.release.run()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertFalse((self.repo / 'app/interest_quest/backend.py').exists())
        self.assertEqual([r['phase'] for r in self.release.receipt['restarts']], ['old'])
        self.assertIn('receipt_write_errors', self.release.receipt)

    def test_git_metadata_symlink_rejected(self):
        from unittest.mock import patch
        original = D.safe_path
        def reject_git(path):
            if Path(path).name == '.git':
                raise RuntimeError('Symlink Git metadata')
            return original(path)
        with patch.object(D, 'safe_path', side_effect=reject_git):
            with self.assertRaisesRegex(RuntimeError, 'Symlink Git'):
                self.release.run()

    def test_partial_install_failure_restores_old_and_restarts(self):
        from unittest.mock import patch
        real_replace = D.os.replace
        failed = False
        def fail_one_stage(source, target):
            nonlocal failed
            if '/stage/' in Path(source).as_posix() and Path(target).name == 'routes.py' and not failed:
                failed = True
                raise OSError('injected install failure')
            return real_replace(source, target)
        with patch.object(D.os, 'replace', side_effect=fail_one_stage):
            with self.assertRaisesRegex(OSError, 'injected install'):
                self.release.run()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertFalse((self.repo / 'app/interest_quest/backend.py').exists())
        self.assertEqual(self.release.receipt['status'], 'rolled_back')
        self.assertEqual([r['phase'] for r in self.release.receipt['restarts']], ['old'])

    def test_readiness_rejects_nonroot_or_authenticated_urls(self):
        for url in ('http://127.0.0.1/api/feedback', 'http://user:secret@127.0.0.1/',
                    'https://example.com/', 'http://127.0.0.1/?fake=1'):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                D.Release(self.repo, Path(self.tmp.name)/'backups', self.old, self.new, self.plan, url)

    def test_real_restart_method_records_command_and_http_200(self):
        from unittest.mock import MagicMock, patch
        import subprocess
        self.release.prepare()
        response = MagicMock()
        response.__enter__.return_value.status = 200
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(D.subprocess, 'run', return_value=subprocess.CompletedProcess(D.RESTART, 0)) as command, \
                patch.object(D.urllib.request, 'build_opener', return_value=opener):
            D.Release.restart_ready(self.release, 'new')
        self.assertEqual(command.call_args.args[0], ['sudo', '-n', 'systemctl', 'restart', 'momoai'])
        self.assertEqual(opener.open.call_args.args, ('http://127.0.0.1/',))
        self.assertEqual(self.release.receipt['restarts'][-1]['root_http_status'], 200)
        self.assertTrue(self.release.receipt['restarts'][-1]['success'])

    def test_real_restart_failure_records_returncode(self):
        from unittest.mock import patch
        import subprocess
        self.release.prepare()
        with patch.object(D.subprocess, 'run', return_value=subprocess.CompletedProcess(D.RESTART, 1)):
            with self.assertRaisesRegex(RuntimeError, 'restart failed'):
                D.Release.restart_ready(self.release, 'new')
        self.assertEqual(self.release.receipt['restarts'][-1]['returncode'], 1)
        self.assertFalse(self.release.receipt['restarts'][-1]['success'])

    def test_http_probe_failure_is_bounded(self):
        from unittest.mock import MagicMock, patch
        import subprocess
        self.release.prepare()
        opener = MagicMock()
        opener.open.side_effect = OSError('offline')
        with patch.object(D.subprocess, 'run', return_value=subprocess.CompletedProcess(D.RESTART, 0)), \
                patch.object(D.urllib.request, 'build_opener', return_value=opener), \
                patch.object(D.time, 'monotonic', side_effect=[0, 0, 0, 46, 46]), \
                patch.object(D.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'Bounded readiness'):
                D.Release.restart_ready(self.release, 'new')
        self.assertFalse(self.release.receipt['restarts'][-1]['success'])

    def test_rollback_failure_is_explicit(self):
        from unittest.mock import patch
        self.fail_ready = True
        with patch.object(self.release, 'rollback', side_effect=RuntimeError('rollback blocked')):
            with self.assertRaisesRegex(RuntimeError, 'Automatic rollback incomplete'):
                self.release.run()
        self.assertEqual(self.release.receipt['status'], 'rollback_failed')
        self.assertIn('rollback blocked', self.release.receipt['rollback_error'])

    def test_syntax_compile_does_not_import_factory(self):
        result = self.release.run()
        self.assertEqual(sorted(result['compiled_python']), sorted(self.plan))


if __name__ == '__main__':
    unittest.main()
