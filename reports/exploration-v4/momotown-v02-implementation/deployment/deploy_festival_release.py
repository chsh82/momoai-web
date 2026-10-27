"""Scoped admin-preview release; importing this module has no side effects."""
import re
from pathlib import PurePosixPath

DEPLOY_DIR = 'reports/exploration-v4/momotown-v02-implementation/deployment/'
EXACT_ALLOWED = {
    'app/interest_quest/backend.py', 'app/interest_quest/store.py',
    'app/interest_quest/routes.py', 'templates/interest_quest/feedback.html',
    'app/interest_quest/protected/index.html',
    'app/interest_quest/protected/momotown-v02.js',
    'app/interest_quest/protected/momotown-v02.json',
    'app/interest_quest/protected/momotown-v02.css',
    'scripts/build_story_v3.py', 'scripts/qa_momotown_v02.py',
}
APPROVED_PREFIXES = ('tests/momotown_backend/', 'tests/momotown_frontend/',
                     'tests/momotown_integration/', 'tests/exploration_launch/', DEPLOY_DIR)


def validate_manifest(old, new, plan):
    if not all(isinstance(s, str) and re.fullmatch('[0-9a-f]{40}', s) for s in (old, new)) or old == new:
        raise ValueError('Require distinct full lowercase commit SHA-1 identifiers')
    if not isinstance(plan, dict) or not plan:
        raise ValueError('Manifest must be a nonempty path-to-SHA256 object')
    for name, digest in plan.items():
        if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
            raise ValueError('Invalid manifest path')
        p = PurePosixPath(name)
        if p.is_absolute() or str(p) != name or any(part in ('.', '..', '.git') for part in p.parts):
            raise ValueError('Noncanonical or unsafe path: ' + name)
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', name):
            raise ValueError('Unsafe path characters: ' + name)
        if name not in EXACT_ALLOWED and not name.startswith(APPROVED_PREFIXES):
            raise ValueError('Out of release scope: ' + name)
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid SHA256: ' + name)
    return dict(plan)


# Standard library only; never import Flask, config, factory, models or storage.
import argparse
import ast
from contextlib import contextmanager
import getpass
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.request
import urllib.parse

FLAGS = ('STUDENT_INTEREST_QUEST_ENABLED', 'STUDENT_INTEREST_MID_ENABLED')
REQUIRED_GUARDS = ('config.py', 'app/__init__.py', 'app/utils/student_launch.py',
                   'app/interest_mid/routes.py')
RESTART = ['sudo', '-n', 'systemctl', 'restart', 'momoai']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_path(path):
    """Reject symlinks including every existing ancestor, not just leaf."""
    path = Path(path).absolute()
    for part in reversed((path, *path.parents)):
        require(not part.is_symlink(), 'Symlink path forbidden: ' + str(part))
        if part != path and part.exists():
            require(part.is_dir(), 'Nondirectory ancestor: ' + str(part))
    return path


def read_flags(repo):
    tree = ast.parse(safe_path(repo / 'config.py').read_bytes())
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Config']
    require(len(classes) == 1, 'Expected one Config class')
    found = {}
    for node in ast.walk(classes[0]):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in FLAGS:
                    require(target.id not in found, 'Duplicate launch flag')
                    found[target.id] = ast.literal_eval(node.value)
    require(set(found) == set(FLAGS) and all(v is False for v in found.values()),
            'Both launch flags must be literal False')
    return found


def load_plan(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate manifest key: ' + key)
            result[key] = value
        return result
    return json.loads(safe_path(Path(path)).read_text(encoding='utf-8'), object_pairs_hook=unique)


class Release:
    def __init__(self, repo, backup_root, old, new, plan, root_url, readiness_seconds=45):
        self.repo = safe_path(repo)
        self.backup_root = safe_path(backup_root)
        self.old, self.new = old, new
        self.plan = validate_manifest(old, new, plan)
        u = urllib.parse.urlsplit(root_url)
        require(u.scheme in ('http', 'https') and u.hostname in ('localhost', '127.0.0.1')
                and u.path == '/' and not u.query and not u.fragment and not u.username and not u.password,
                'Readiness URL must be unauthenticated loopback HTTP(S) root /')
        require(1 <= readiness_seconds <= 120, 'Readiness timeout must be 1..120 seconds')
        self.root_url, self.readiness_seconds = root_url, readiness_seconds
        self.receipt = {}
        self.installed = []
        self.before = {}
        self.guards = {}
        self.release = None

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, timeout=60)

    def head(self):
        return self.git('rev-parse', 'HEAD').decode().strip()

    def tree(self, commit):
        result = {}
        for row in self.git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
            if row:
                meta, name = row.split(b'\t', 1)
                mode, kind, oid = meta.decode().split()
                result[name.decode()] = (mode, kind, oid)
        return result

    def fetch(self):
        self.git('fetch', 'origin', 'master')
        require(self.git('rev-parse', 'refs/remotes/origin/master').decode().strip() == self.new,
                'origin/master must equal exact new commit')

    def active(self):
        result = subprocess.run(['systemctl', 'is-active', 'momoai'], capture_output=True,
                                text=True, timeout=10)
        return result.stdout.strip()

    def pid(self):
        return subprocess.check_output(['systemctl', 'show', 'momoai', '-p', 'MainPID', '--value'],
                                       text=True, timeout=10).strip()

    @contextmanager
    def lock(self):
        import fcntl  # Linux deployment only; importing module remains safe on Windows.
        self.backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        safe_path(self.backup_root)
        path = safe_path(self.backup_root / '.admin-preview-deploy.lock')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def save(self):
        if self.release:
            try:
                target = safe_path(self.release / 'receipt.json')
                temporary = safe_path(self.release / 'receipt.tmp')
                temporary.write_text(json.dumps(self.receipt, indent=2, sort_keys=True), encoding='utf-8')
                os.replace(temporary, target)
            except OSError as error:
                if not getattr(self, 'recovering', False):
                    raise
                # A full disk must not prevent restoring/restarting the old release.
                self.receipt.setdefault('receipt_write_errors', []).append(str(error))
                import sys
                print('Recovery receipt write failed at ' + str(self.release) + ': ' + str(error), file=sys.stderr)

    def restart_ready(self, phase):
        event = {'phase': phase, 'command': RESTART, 'attempted': True,
                 'active': None, 'root_http_status': None, 'success': False}
        self.receipt['restarts'].append(event)
        self.save()  # Persist intent before invoking sudo/systemctl.
        try:
            result = subprocess.run(RESTART, capture_output=True, text=True, timeout=60)
            event['returncode'] = result.returncode
            require(result.returncode == 0, 'Service restart failed: ' + phase)
            # No redirects, proxies, credentials, cookies or authenticated API probes.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            deadline = time.monotonic() + self.readiness_seconds
            while time.monotonic() < deadline:
                event['active'] = self.active()
                if event['active'] == 'active':
                    try:
                        remaining = max(0.1, min(3.0, deadline - time.monotonic()))
                        with opener.open(self.root_url, timeout=remaining) as response:
                            event['root_http_status'] = response.status
                        if event['root_http_status'] == 200:
                            event.update(success=True, main_pid=self.pid())
                            require(event['main_pid'].isdigit() and int(event['main_pid']) > 0,
                                    'Active service has no MainPID')
                            return
                    except (OSError, ValueError) as error:
                        event['last_probe_error'] = type(error).__name__
                time.sleep(min(1.0, max(0, deadline - time.monotonic())))
            raise RuntimeError('Bounded readiness failed: ' + phase)
        finally:
            self.save()

    def clean(self):
        require(self.git('status', '--porcelain', '--untracked-files=no') == b'', 'Dirty tracked worktree/index')

    def guard_snapshot(self, tree):
        names = set(REQUIRED_GUARDS)
        names.update(n for n in tree if n.startswith(('app/models/', '.github/workflows/', 'migrations/'))
                     or (n.startswith('app/') and n.endswith('/models.py')))
        result = {}
        for name in sorted(names):
            require(name in tree and tree[name][1] == 'blob' and tree[name][0] in ('100644', '100755'),
                    'Missing/nonregular guard: ' + name)
            path = safe_path(self.repo / name)
            require(path.is_file(), 'Missing guard file: ' + name)
            value = digest(path)
            expected = hashlib.sha256(self.git('show', self.old + ':' + name)).hexdigest()
            require(value == expected, 'Guard differs from old commit: ' + name)
            result[name] = value
        return result

    def verify_guards(self):
        require({n: digest(safe_path(self.repo / n)) for n in self.guards} == self.guards,
                'Protected file digest changed')
        read_flags(self.repo)

    def prepare(self):
        metadata = safe_path(self.repo / '.git')
        require(metadata.is_dir(), 'Production Git metadata must be a local directory, not a worktree indirection')
        require(Path(self.git('rev-parse', '--show-toplevel').decode().strip()).resolve() == self.repo.resolve(),
                'Repository root mismatch')
        require(self.head() == self.old, 'HEAD must equal exact old commit')
        self.clean()
        require(self.active() == 'active', 'momoai must start active')
        read_flags(self.repo)
        self.fetch()
        require(self.git('merge-base', self.old, self.new).decode().strip() == self.old,
                'Release must fast-forward from exact old commit')
        changed = set(filter(None, self.git('diff', '--name-only', '-z', '--no-renames', self.old, self.new).decode().split('\0')))
        require(changed == set(self.plan), 'Exact commit diff set must match manifest')
        oldtree, newtree = self.tree(self.old), self.tree(self.new)
        self.guards = self.guard_snapshot(oldtree)
        self.backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        safe_path(self.backup_root)
        require(self.repo.stat().st_dev == self.backup_root.stat().st_dev,
                'Stage/backup must share worktree filesystem for atomic replace')
        self.release = Path(tempfile.mkdtemp(prefix='momotown-' + self.new[:12] + '-', dir=self.backup_root))
        (self.release / 'stage').mkdir()
        (self.release / 'before').mkdir()
        self.receipt = {
            'old_commit': self.old, 'new_commit': self.new, 'status': 'preparing',
            'scope': 'admin-preview only; both student gates False',
            'backup_directory': str(self.release), 'manifest': self.plan,
            'before': self.before, 'guards': self.guards, 'flags': read_flags(self.repo),
            'restarts': [], 'service_restart_required': True, 'service_pid_before': self.pid(),
            'direct_private_database_operations': False, 'custom_migrations': False,
            'startup_database_caveat': 'Service restart executes preexisting factory db.create_all; database untouched is NOT claimed.',
            'feedback_storage': 'Separate lazy SQLite is created on feedback API access; helper never calls that API.',
            'readiness_url': self.root_url, 'compiled_python': [],
        }
        self.save()
        for name, expected in sorted(self.plan.items()):
            require(name in newtree and newtree[name][0] in ('100644', '100755') and newtree[name][1] == 'blob',
                    'Deleted/symlink/submodule release entries forbidden: ' + name)
            target = safe_path(self.repo / name)
            entry = safe_path(self.release / 'stage' / name)
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_bytes(self.git('show', self.new + ':' + name))
            require(digest(entry) == expected, 'Staged hash mismatch: ' + name)
            if name in oldtree:
                require(oldtree[name][0] in ('100644', '100755') and target.is_file(),
                        'Old file missing/nonregular: ' + name)
                value = digest(target)
                require(value == hashlib.sha256(self.git('show', self.old + ':' + name)).hexdigest(),
                        'Old file differs from commit: ' + name)
                saved = safe_path(self.release / 'before' / name)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                self.before[name] = {'existed': True, 'sha256': value, 'mode': stat.S_IMODE(target.stat().st_mode)}
            else:
                require(not target.exists(), 'Untracked/ignored collision: ' + name)
                self.before[name] = {'existed': False}
            entry.chmod(0o755 if newtree[name][0] == '100755' else 0o644)
            if name.endswith('.py'):
                output = self.release / 'compiled' / (hashlib.sha256(name.encode()).hexdigest() + '.pyc')
                output.parent.mkdir(exist_ok=True)
                py_compile.compile(str(entry), cfile=str(output), doraise=True)
                self.receipt['compiled_python'].append(name)
        require(self.head() == self.old, 'Concurrent HEAD change')
        self.clean()
        self.verify_guards()
        self.receipt['status'] = 'prepared'
        self.save()

    def verify_release(self, commit):
        require(self.head() == commit, 'HEAD readback mismatch')
        self.clean()
        self.verify_guards()
        for name in self.plan:
            target = safe_path(self.repo / name)
            if commit == self.new:
                require(digest(target) == self.plan[name], 'Installed hash mismatch: ' + name)
            elif self.before[name]['existed']:
                require(digest(target) == self.before[name]['sha256'], 'Restored hash mismatch: ' + name)
                require(stat.S_IMODE(target.stat().st_mode) == self.before[name]['mode'], 'Restored mode mismatch')
            else:
                require(not target.exists(), 'Added file remains after rollback: ' + name)

    def rollback(self):
        require(self.head() in (self.old, self.new), 'Concurrent HEAD change prevents rollback')
        for name in reversed(self.installed):
            target = safe_path(self.repo / name)
            require(target.is_file() and digest(target) == self.plan[name],
                    'Concurrent file change prevents rollback: ' + name)
            state = self.before[name]
            if state['existed']:
                saved = safe_path(self.release / 'before' / name)
                require(digest(saved) == state['sha256'], 'Backup hash mismatch: ' + name)
                temporary = self.release / 'restore.tmp'
                shutil.copy2(saved, temporary)
                os.replace(temporary, target)
            else:
                target.unlink()
        self.git('reset', '--mixed', self.old)  # Never --hard or broad checkout.
        self.verify_release(self.old)
        self.restart_ready('old')
        self.verify_release(self.old)
        self.receipt.update(status='rolled_back', rollback_head=self.head())
        self.save()

    def run(self):
        with self.lock():
            try:
                self.prepare()
            except BaseException as error:
                if self.receipt:
                    self.receipt.update(status='preflight_failed', error_type=type(error).__name__, error=str(error))
                    self.save()
                raise
            try:
                ordered = sorted(self.plan, key=lambda n: (n == 'app/interest_quest/protected/index.html', n))
                for name in ordered:
                    target = safe_path(self.repo / name)
                    state = self.before[name]
                    require((target.is_file() and digest(target) == state['sha256']) if state['existed'] else not target.exists(),
                            'Concurrent target change: ' + name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(safe_path(self.release / 'stage' / name), target)
                    self.installed.append(name)
                    self.receipt['installed'] = self.installed
                    self.save()
                self.git('reset', '--mixed', self.new)
                self.verify_release(self.new)
                self.restart_ready('new')
                self.verify_release(self.new)
                self.receipt.update(status='deployed', verified_files=len(self.plan), service_pid_after=self.pid())
                self.save()
                return self.receipt
            except BaseException as error:
                self.recovering = True
                self.receipt.update(status='failed', error_type=type(error).__name__, error=str(error))
                self.save()
                try:
                    self.rollback()
                except BaseException as rollback_error:
                    self.receipt.update(status='rollback_failed', rollback_error_type=type(rollback_error).__name__,
                                        rollback_error=str(rollback_error))
                    self.save()
                    raise RuntimeError('Automatic rollback incomplete; inspect receipt: ' + str(self.release)) from rollback_error
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--plan', required=True, help='JSON file: exact commit changed path -> raw Git blob SHA256')
    parser.add_argument('--root-url', required=True, help='Unauthenticated loopback root URL, e.g. http://127.0.0.1/')
    parser.add_argument('--execute', action='store_true', help='Explicitly authorize local production deployment')
    args = parser.parse_args()
    require(args.execute, 'Refusing execution without --execute')
    require(os.name == 'posix' and getpass.getuser() == 'chsh82', 'Only production Linux account chsh82 is allowed')
    require(args.old == 'd31fcaf40ff8ed5904d965cddf026599a8b6ae9f', 'Unexpected production baseline')
    repo = Path('/home/chsh82/momoai_web')
    result = Release(repo, Path('/home/chsh82/momoai-release-backups'), args.old, args.new,
                     load_plan(args.plan), args.root_url).run()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
