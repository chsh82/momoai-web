"""Fail-closed B-R01 isolation primitives; audit is not an OS sandbox."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
E = HERE.parent
REPO = Path('C:/Users/aproa/momoai_web')
SCRATCH = Path('C:/Users/aproa/AppData/Local/hermes/profiles/davinci/cache/scratch')

class AuditBoundary:
    def __init__(self, inventory):
        self.inventory = inventory
        gate_path = E / 'c2_br_exact_gate_manifest.json'
        self.gate = json.loads(gate_path.read_text(encoding='utf-8'))
        self.allowed = {os.path.normcase(os.path.abspath(p)) for p in [*inventory['libraries'], *inventory['runtime'], str(gate_path), str(E / 'c2_br_library_read_manifest.json'), str(E / 'c2_br_executable_source_slices.json')]}
        self.allowed.update(os.path.normcase(os.path.abspath(REPO / p)) for p in self.gate['models'])
        self.allowed.update(os.path.normcase(os.path.abspath(p)) for p in self.gate['create_only_external'])
        self.allowed.add(os.path.normcase(os.path.abspath(REPO / 'app/services/p3_assignment_schema.py')))
        self.denials = []
        self.owners = []
        self.connecting = None
        self._creating = None
        self.expected = False
        self.__readbacks = {}
        self.__spawn = None
        self.__junction_cleanup = None

    def owner_path(self, path, writing=False):
        p = Path(os.path.abspath(os.fsdecode(path)))
        for owner in self.owners:
            if p in {owner.root, owner.path, owner.sentinel, Path(str(owner.path) + '-journal')}:
                ancestors_safe(p)
                if writing and (self._creating is not owner or p not in {owner.path, owner.sentinel}):
                    return False
                return True
        return False

    def install(self):
        sys.addaudithook(self.audit)

    def audit(self, event, args):
        if event == 'subprocess.Popen' and self.__spawn is not None:
            entry = self.__spawn
            if (args[0] == sys.executable and args[1] == entry['commandline'] and
                    args[2] == str(REPO) and args[3] == entry['env'] and not entry['spawned']):
                entry['spawned'] = True
                return
        if event == 'open' and isinstance(args[0], int) and self.__spawn is not None:
            # Only CPython subprocess's direct wrapping of its own new pipe FDs.
            frame = sys._getframe(1)
            if frame.f_globals.get('__name__') == 'subprocess' and frame.f_code.co_name == '__init__':
                return
        if event == 'open':
            path, mode, flags = args
            if isinstance(path, int):
                self.denials.append({'event': event, 'path': str(path), 'reason': 'untracked file descriptor'})
                raise PermissionError('Untracked file descriptor')
            if self.owner_path(path, writing=bool((isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
                return
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                self.denials.append({'event': event, 'path': str(path), 'reason': 'no issued writer'})
                raise PermissionError('No issued writer: ' + str(path))
            self.check_read(path)
        elif event.startswith('sqlite3.connect') and self.connecting is not None:
            self.connecting.check()
            if event == 'sqlite3.connect' and args[0] != str(self.connecting.path):
                raise PermissionError('wrong issued sqlite path')
            return
        elif event.startswith(('socket.', 'subprocess.', 'os.system', 'os.spawn', 'os.exec', 'sqlite3.connect')):
            frame = sys._getframe(1)
            frames = []
            while frame is not None:
                frames.append({'file': frame.f_code.co_filename,
                               'function': frame.f_code.co_name,
                               'line': frame.f_lineno})
                frame = frame.f_back
            self.denials.append({'event': event, 'reason': 'external capability absent',
                                 'frames': frames})
            raise PermissionError('External capability absent: ' + event)
        elif event == 'os.rmdir' and self.__junction_cleanup is not None and Path(args[0]) == self.__junction_cleanup:
            return
        elif event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.link', 'os.symlink', 'os.truncate', 'os.chmod'}:
            if event == 'os.mkdir' and any(self._creating is o and Path(os.path.abspath(args[0])) == o.root for o in self.owners):
                ancestors_safe(args[0])
                return
            self.denials.append({'event': event, 'reason': 'no issued writer'})
            raise PermissionError('Filesystem mutation forbidden: ' + event)
        elif event == 'import' and args[0].split('.')[0] in {'app', 'config', 'testing_safety'}:
            self.denials.append({'event': event, 'module': args[0]})
            raise PermissionError('Normal app import forbidden: ' + args[0])

    def fixed_junction_probe(self):
        import _winapi
        import stat
        victim, target = Owner(self), Owner(self)
        junction = victim.root / 'junction-probe'
        if junction.exists():
            raise PermissionError('junction must be NEW')
        _winapi.CreateJunction(str(target.root), str(junction))
        created = bool(junction.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        denied = False
        try:
            ancestors_safe(junction / 'synthetic.sqlite')
        except PermissionError:
            denied = True
        finally:
            self.__junction_cleanup = junction
            try:
                os.rmdir(junction)
            finally:
                self.__junction_cleanup = None
        victim.check()
        target.check()
        return {'created_reparse_point': created, 'ancestor_denied': denied, 'cleaned': not junction.exists(),
                'mechanism': '_winapi.CreateJunction actual Windows reparse point', 'owner': str(victim.root)}

    def _consume_readback(self, nonce, process, challenge):
        entry = self.__readbacks.get(nonce)
        if entry is None or entry['consumed'] or entry.get('process') is not process:
            raise PermissionError('unissued or reused readback capability')
        if challenge.get('child_pid') != process.pid or challenge.get('parent_pid') != os.getpid():
            raise PermissionError('readback pipe child identity mismatch')
        if len(challenge.get('challenge', '')) != 64:
            raise PermissionError('invalid child challenge')
        entry['consumed'] = True
        return dict(entry['payload'], child_pid=process.pid, challenge=challenge['challenge'])

    def fresh_readback(self, owner):
        import subprocess
        import secrets
        if owner not in self.owners or getattr(owner, '_readback_finished', False):
            raise PermissionError('owner not live or already handed off')
        owner.engine.dispose()
        if any(not c._closed for c in owner._live_connections):
            raise PermissionError('writer connections must close before readback')
        raw = {'__file__': str(HERE / 'readback.py'), '__name__': '_br_parent_raw'}
        exec(compile(Path(raw['__file__']).read_bytes(), raw['__file__'], 'exec'), raw)
        c = owner.connect()
        try:
            expected = raw['snapshot'](c)
        finally:
            c.close()
        proof = owner.handoff()
        owner._readback_frozen = True
        paths = [HERE / (n + '.py') for n in ('run_br_assignment','isolation_kernel','source_loader','test_assignment_real_route','readback')]
        paths.append(REPO / 'app/services/p3_assignment_schema.py')
        sources = {str(p): digest(p) for p in paths}
        nonce = secrets.token_hex(32)
        payload = {'run_id': self.run_id, 'parent_pid': os.getpid(), 'nonce': nonce,
                   'purpose': 'B-R01-fresh-readonly', 'sources': sources, 'read_only_handoff': proof,
                   'raw23': expected, 'schema_sha256': hashlib.sha256(json.dumps(expected['sqlite_schema'], sort_keys=True).encode()).hexdigest()}
        controls = []
        for control in ('replay_challenge','source_hash','schema_hash','file_identity','database_hash'):
            controls.append(self._spawn_readback(payload, control))
        result = self._spawn_readback(payload, None)
        owner.check()
        if digest(owner.path) != proof['database_sha256']:
            raise AssertionError('child changed database')
        owner._readback_finished = True
        result.update(writers_closed=True, negative_controls=controls)
        return result

    def _spawn_readback(self, original, control):
        import subprocess
        import secrets
        payload = json.loads(json.dumps(original))
        nonce = secrets.token_hex(32)
        payload['nonce'] = nonce
        env = {k: os.environ[k] for k in ('SystemRoot','PATH') if k in os.environ}
        env.update(MOMOAI_TEST_MODE='1', PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR=str(SCRATCH))
        argv = [sys.executable, str(HERE / 'readback.py'), '--capability-stdin']
        if digest(sys.executable) != self.inventory['runtime'][str(Path(sys.executable).resolve())]:
            raise PermissionError('interpreter hash drift')
        entry = {'argv': argv, 'commandline': subprocess.list2cmdline(argv), 'env': env, 'spawned': False, 'consumed': False, 'payload': payload}
        self.__readbacks[nonce] = entry
        process = None
        try:
            self.__spawn = entry
            try:
                process = subprocess.Popen(argv, executable=sys.executable, cwd=str(REPO), env=env, shell=False,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            finally:
                self.__spawn = None
            entry['process'] = process
            challenge = json.loads(process.stdout.readline())
            message = self._consume_readback(nonce, process, challenge)
            try:
                self._consume_readback(nonce, process, challenge)
            except PermissionError:
                replay_denied = True
            else:
                raise AssertionError('single-use registry accepted replay')
            expected_failure = None
            if control == 'replay_challenge':
                message['challenge'] = '0'*64
                expected_failure = 'live parent/child challenge mismatch or replay'
            elif control == 'source_hash':
                message['sources'][str(HERE / 'readback.py')] = '0'*64
                expected_failure = 'frozen source hash drift'
            elif control == 'schema_hash':
                message['schema_sha256'] = '0'*64
                expected_failure = 'schema digest mismatch'
            elif control == 'file_identity':
                message['read_only_handoff']['identity'][1][1] += 1
                expected_failure = 'handoff sentinel/file identity lost'
            elif control == 'database_hash':
                message['read_only_handoff']['database_sha256'] = '0'*64
                expected_failure = 'database bytes changed since issuance'
            elif control is not None:
                raise PermissionError('unissued child diagnostic profile')
            output, errors = process.communicate(json.dumps(message) + '\n', timeout=90)
            if control is not None:
                if process.returncode != 1 or expected_failure not in output or errors:
                    raise AssertionError('wrong child negative result: ' + str(control) + ' ' + output + errors)
                return {'case': control, 'rejected': True, 'expected_failure': expected_failure}
            if process.returncode != 0:
                raise AssertionError('fresh child failed: ' + output + errors)
            result = json.loads(output)
            if result['status'] != 'READBACK_PASS' or result['issuing_run_id'] != self.run_id:
                raise AssertionError('unbound child result')
            result.update(replay_denied=replay_denied)
            return result
        finally:
            self.__spawn = None
            self.__readbacks.pop(nonce, None)
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()

    def check_read(self, path):
        canonical = os.path.normcase(os.path.abspath(path))
        if canonical not in self.allowed:
            self.denials.append({'event': 'open', 'path': canonical})
            raise PermissionError('Unapproved exact read: ' + canonical)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def preflight():
    required = {'MOMOAI_TEST_MODE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    if any(os.environ.get(k) != v for k, v in required.items()) or Path(os.environ.get('TMPDIR', '')).resolve() != SCRATCH.resolve():
        raise PermissionError('Required synthetic runtime environment absent')
    library = json.loads((E / 'c2_br_library_read_manifest.json').read_text(encoding='utf-8'))
    files = {p: h for d in library['distributions'].values() for p, h in d['files'].items()}
    if len(files) != 982:
        raise PermissionError('Library inventory must contain exact 982 files')
    mismatches = [p for p, h in files.items() if not Path(p).is_file() or digest(p) != h]
    if mismatches:
        raise PermissionError('Approved library hash mismatch: ' + repr(mismatches))
    base = Path(sys.base_prefix).resolve()
    runtime = {}
    for directory, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in {'site-packages', '__pycache__', 'scripts', 'include', 'libs', 'tcl', 'tools', 'doc'}]
        for name in names:
            p = Path(directory) / name
            if p.suffix.lower() in {'.py', '.pyd', '.dll', '.exe', '.zip'}:
                runtime[str(p)] = digest(p)
    if str(Path(sys.executable).resolve()) not in runtime or not runtime:
        raise PermissionError('Interpreter not inside CPython runtime manifest')
    # Measure real local platform metadata before installing network denial.
    # SQLAlchemy's platform.machine() then uses stdlib's real uname cache;
    # no socket audit event is permitted or faked under the boundary.
    import platform
    import subprocess
    platform.machine()
    return {'library_file_count': len(files), 'runtime_file_count': len(runtime), 'mismatches': mismatches,
            'runtime_excludes_site_packages': all('site-packages' not in p.lower() for p in runtime),
            'runtime': runtime, 'libraries': files, 'executable': sys.executable,
            'os_loader_boundary': 'Windows OS DLL loading is not exhaustively sandboxed'}

def ancestors_safe(path):
    import stat
    p = Path(os.path.abspath(path))
    for candidate in [*reversed(p.parents), p]:
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise PermissionError('reparse ancestor: ' + str(candidate))
    return p


class Owner:
    def __init__(self, boundary):
        import secrets
        self.boundary = boundary
        self.root = SCRATCH / ('br_assignment_' + secrets.token_hex(16))
        self.path = self.root / 'synthetic.sqlite'
        self.sentinel = self.root / 'owner.sentinel'
        self._token = secrets.token_bytes(32)
        self.building = True
        self.connections = 0
        self._live_connections = []
        self.sql_denials = []
        boundary.owners.append(self)
        if boundary._creating is not None:
            raise PermissionError('nested owner creation')
        boundary._creating = self
        try:
            ancestors_safe(self.root)
            self.root.mkdir(exist_ok=False)
            with self.sentinel.open('xb') as f:
                f.write(self._token)
            with self.path.open('xb'):
                pass
        finally:
            boundary._creating = None
            self.building = False
        self._identity = self._ids()
        self.check()

    def initialize(self, actual, sidecar):
        return self._initialize(actual, sidecar, False)

    def initialize_for_setup_probe(self, actual, sidecar):
        return self._initialize(actual, sidecar, True)

    def _initialize(self, actual, sidecar, setup_probe):
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool
        from sqlalchemy.schema import CreateTable, CreateIndex
        from sqlalchemy.dialects.sqlite import dialect
        import sqlite3
        if getattr(self, '_Owner__initialized', False):
            raise PermissionError('setup permanently closed')
        self.__initialized = True
        if set(actual.tables) != set(self.boundary.gate['actual_tables']) or set(sidecar.tables) != set(self.boundary.gate['new_tables']):
            raise PermissionError('exact schema inventory mismatch')
        tables = {**actual.tables, **sidecar.tables}
        indexes = {i.name: t.name for t in tables.values() for i in t.indexes}
        schema_path = REPO / 'app/services/p3_assignment_schema.py'
        ns = {'__file__': str(schema_path), '__name__': '_br_factory_schema'}
        exec(compile(schema_path.read_bytes(), str(schema_path), 'exec'), ns)
        triggers = ns['trigger_sql']()
        trigger_targets = {name: next(t for t in sidecar.tables if name.startswith(t + '_')) for name in triggers}
        state = {'ddl': True, 'seed': False}
        references = {'users','students','courses','course_enrollments','course_sessions','assignments','assignment_submissions','notifications'}
        self.fixture_ids = {name: str(__import__('uuid').UUID(int=n)) for n, name in enumerate(
            ['teacher','actor','student','course','enrollment','session','assignment','assignment2','submission','submission2','notification','notification2'], 1)}
        ids = self.fixture_ids
        from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint
        setup_triggers = {}
        for table_name in sorted(references):
            table = tables[table_name]
            keys = [list(c.columns) for c in table.constraints if isinstance(c, (UniqueConstraint, PrimaryKeyConstraint))]
            keys += [list(i.columns) for i in table.indexes if i.unique]
            condition = ' OR '.join('(' + ' AND '.join(col.name + '=NEW.' + col.name for col in key) + ')' for key in keys if key)
            name = 'br_setup_' + table_name + '_insert_conflict_guard'
            setup_triggers[name] = f"CREATE TRIGGER {name} BEFORE INSERT ON {table_name} WHEN EXISTS(SELECT 1 FROM {table_name} WHERE {condition}) BEGIN SELECT RAISE(ABORT, 'setup_reference_conflict'); END"
            trigger_targets[name] = table_name
        def authorize(action, a, b, database, origin):
            if database not in (None, 'main'):
                return sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and (b or a or '').lower() in {'count', 'typeof', 'length', 'like', 'glob'}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_PRAGMA and ((b is None and a in {'foreign_keys', 'recursive_triggers', 'foreign_key_check', 'integrity_check', 'read_uncommitted'}) or (a in {'table_info','table_xinfo','index_list','foreign_key_list'} and b in tables) or (a in {'index_info','index_xinfo'} and (b in indexes or any(b == 'sqlite_autoindex_' + name + '_' + str(i) for name, table in tables.items() for i in range(1, len(table.constraints) + 1))))):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_TRANSACTION and a in {'BEGIN', 'COMMIT', 'ROLLBACK'}:
                return sqlite3.SQLITE_OK
            if not state['ddl'] and not state['seed']:
                if action == sqlite3.SQLITE_INSERT and a in sidecar.tables:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_UPDATE and a == 'br_assignment_heads':
                    return sqlite3.SQLITE_OK
            if state['seed'] and action == sqlite3.SQLITE_INSERT and a in references:
                return sqlite3.SQLITE_OK
            if state['ddl']:
                if action == sqlite3.SQLITE_CREATE_TABLE and a in tables:
                    return sqlite3.SQLITE_OK
                if action in (sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER) and trigger_targets.get(a) == b:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_REINDEX and a in indexes:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_CREATE_INDEX and (indexes.get(a) == b or a.startswith('sqlite_autoindex_') and b in tables):
                    return sqlite3.SQLITE_OK
                if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and a == 'sqlite_master':
                    return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        self.__authorizer = authorize
        engine = create_engine('sqlite://', creator=self.connect, poolclass=NullPool)
        try:
            # Compile and issue exact tables individually: cross-metadata FK targets
            # remain the original Columns, never copied into sidecar metadata.
            with engine.begin() as c:
                for name in [t.name for t in actual.sorted_tables] + self.boundary.gate['new_tables']:
                    table = tables[name]
                    c.execute(CreateTable(table))
                    for index in sorted(table.indexes, key=lambda i: i.name):
                        c.execute(CreateIndex(index))
                for sql in [*triggers.values(), *setup_triggers.values()]:
                    c.exec_driver_sql(sql)
            state['ddl'] = False
            state['seed'] = True
            from datetime import datetime, date
            from sqlalchemy import DateTime, Date
            fixed = datetime(2026, 10, 18, 12)
            fixtures = {
                'users': [dict(user_id=ids['teacher'], email='teacher@synthetic.invalid', password_hash='SYNTHETIC_NOT_A_LOGIN', name='SYNTHETIC teacher', role='teacher', role_level=3),
                          dict(user_id=ids['actor'], email='student@synthetic.invalid', password_hash='SYNTHETIC_NOT_A_LOGIN', name='SYNTHETIC student', role='student', role_level=5)],
                'students': [dict(student_id=ids['student'], teacher_id=ids['teacher'], user_id=ids['actor'], name='SYNTHETIC', grade='SYNTHETIC')],
                'courses': [dict(course_id=ids['course'], course_name='SYNTHETIC', course_code='SYNTHETIC-BR', teacher_id=ids['teacher'], start_date=date(2026,1,1), end_date=date(2026,12,31))],
                'course_enrollments': [dict(enrollment_id=ids['enrollment'], course_id=ids['course'], student_id=ids['student'])],
                'course_sessions': [dict(session_id=ids['session'], course_id=ids['course'], session_number=1, session_date=date(2026,10,18))],
                'assignments': [dict(assignment_id=ids[key], title='SYNTHETIC', description='SYNTHETIC', course_id=ids['course'], teacher_id=ids['teacher'], due_date=datetime(2026,12,31)) for key in ('assignment','assignment2')],
                'assignment_submissions': [dict(submission_id=ids[sub], assignment_id=ids[assignment], student_id=ids['student'], content='SYNTHETIC') for sub, assignment in [('submission','assignment'),('submission2','assignment2')]],
                'notifications': [dict(notification_id=ids[key], user_id=ids['teacher'], notification_type='assignment_submitted', title='SYNTHETIC', message='SYNTHETIC') for key in ('notification','notification2')],
            }
            # No externally supplied rows/callback or SQL is admitted during setup.
            # Fixed INSERT-only seed; connections are never exposed until closure.
            with engine.begin() as c:
                c.connection.driver_connection.begin_immediate()
                for name, rows in fixtures.items():
                    for row in rows:
                        for col in tables[name].columns:
                            if col.name not in row and col.default is not None and isinstance(col.type, DateTime):
                                row[col.name] = fixed
                        c.execute(tables[name].insert().values(**row))
            self.setup_probe_results = []
            if setup_probe:
                readback_path = HERE / 'readback.py'
                raw_ns = {'__file__': str(readback_path), '__name__': '_br_setup_raw'}
                exec(compile(readback_path.read_bytes(), str(readback_path), 'exec'), raw_ns)
                with engine.connect() as c:
                    dbapi = c.connection.driver_connection
                    baseline = raw_ns['snapshot'](dbapi)
                    for table_name in sorted(references):
                        fixed_keys = {
                            'users': ('user_id','teacher'), 'students': ('student_id','student'),
                            'courses': ('course_id','course'), 'course_enrollments': ('enrollment_id','enrollment'),
                            'course_sessions': ('session_id','session'), 'assignments': ('assignment_id','assignment'),
                            'assignment_submissions': ('submission_id','submission'), 'notifications': ('notification_id','notification')}
                        key_column, fixture_key = fixed_keys[table_name]
                        row = c.exec_driver_sql('SELECT * FROM ' + table_name + ' WHERE ' + key_column + '=?', (ids[fixture_key],)).one()
                        for syntax in ('INSERT OR REPLACE', 'REPLACE'):
                            dbapi.begin_immediate()
                            error = None
                            try:
                                dbapi.execute(syntax + ' INTO ' + table_name + ' VALUES (' + ','.join('?' for _ in row) + ')', tuple(row))
                            except sqlite3.DatabaseError as exc:
                                error = str(exc)
                            finally:
                                dbapi.rollback()
                            self.setup_probe_results.append({'table': table_name, 'syntax': syntax, 'error': error,
                                'unchanged': raw_ns['snapshot'](dbapi) == baseline})
            state['seed'] = False
            state['ddl'] = True
            with engine.begin() as c:
                for name in setup_triggers:
                    c.exec_driver_sql('DROP TRIGGER ' + name)
        finally:
            state['ddl'] = False
            state['seed'] = False
        self.__sidecar = sidecar
        self.engine = engine
        return engine

    def handoff(self):
        self.check()
        if not getattr(self, '_Owner__initialized', False) or not hasattr(self, 'engine'):
            raise PermissionError('only closed-setup owners can be handed off')
        if any(Path(str(self.path) + suffix).exists() for suffix in ('-journal','-wal','-shm')):
            raise PermissionError('database still has side files')
        return {'root': str(self.root), 'database': str(self.path), 'read_only': True,
                'identity': [list(pair) for pair in self._identity],
                'sentinel_sha256': digest(self.sentinel), 'database_sha256': digest(self.path),
                'issued_run_id': self.boundary.run_id}

    def fixed_transition(self, generation):
        if type(generation) is not int or generation not in (1, 2):
            raise ValueError('fixed generation must be 1 or 2')
        ids = self.fixture_ids
        r = self.__sidecar.tables['br_assignment_revisions']
        h = self.__sidecar.tables['br_assignment_heads']
        revision_id = '00000000-0000-0000-0000-00000000010' + str(generation)
        with self.engine.begin() as c:
            c.connection.driver_connection.begin_immediate()
            c.execute(r.insert().values(revision_id=revision_id, submission_id=ids['submission'], revision_no=generation,
                parent_revision_id=None if generation == 1 else '00000000-0000-0000-0000-000000000101', actor_user_id=ids['actor'], content='SYNTHETIC', file_manifest='{}',
                payload_digest='a'*64, legacy_snapshot='{}', legacy_digest='b'*64,
                enrollment_id=ids['enrollment'], course_id=ids['course'], session_id=None,
                scope_state='unknown', program_id=None, edition_id=None, rubric_id=None, captured_at='2026-10-18T12:00:00.000000'))
            if generation == 1:
                c.execute(h.insert().values(submission_id=ids['submission'], revision_id=revision_id, generation=1, legacy_digest='b'*64))
            else:
                changed = c.execute(h.update().where(h.c.submission_id == ids['submission'], h.c.generation == 1,
                    h.c.revision_id == '00000000-0000-0000-0000-000000000101').values(revision_id=revision_id, generation=2, legacy_digest='b'*64))
                assert changed.rowcount == 1
        return {'generation': generation, 'revision_id': revision_id}

    def connect(self):
        return self._connect(False)

    def _constraint_connection(self):
        # Fixed harness-only physical DML profile, never used by a bound store.
        return self._connect(True)

    def _connect(self, physical):
        if getattr(self, '_readback_frozen', False):
            raise PermissionError('owner permanently frozen for read-only child handoff')
        import sqlite3
        from contextlib import contextmanager
        owner = self

        class GuardCursor(sqlite3.Cursor):
            def execute(self, sql, parameters=()):
                owner.check()
                return super().execute(sql, parameters)

            def executemany(self, sql, parameters):
                owner.check()
                for values in parameters:
                    self.execute(sql, values)
                return self

            def executescript(self, script):
                raise PermissionError('script batches forbidden')

        class GuardConnection(sqlite3.Connection):
            _closed = False

            def close(self):
                result = super().close()
                self._closed = True
                return result

            def enable_load_extension(self, enabled):
                if enabled is not False:
                    raise PermissionError('extension loading forbidden')
                return super().enable_load_extension(False)

            def load_extension(self, *args, **kwargs):
                raise PermissionError('extension loading forbidden')

            def set_authorizer(self, authorizer):
                if getattr(self, '_authorizer_installed', False):
                    raise PermissionError('authorizer is permanently installed')
                result = super().set_authorizer(authorizer)
                self._authorizer_installed = True
                return result

            def cursor(self, factory=GuardCursor):
                owner.check()
                if factory is not GuardCursor:
                    raise PermissionError('unissued cursor factory')
                return super().cursor(factory)

            def execute(self, sql, parameters=()):
                return self.cursor().execute(sql, parameters)

            def executemany(self, sql, parameters):
                return self.cursor().executemany(sql, parameters)

            def executescript(self, script):
                raise PermissionError('script batches forbidden')

            def begin_immediate(self):
                owner.check()
                self._tx_gate = True
                try:
                    return self.execute('BEGIN IMMEDIATE')
                finally:
                    self._tx_gate = False

            def commit(self):
                owner.check()
                self._tx_gate = True
                try:
                    return super().commit()
                finally:
                    self._tx_gate = False

            def __exit__(self, kind, value, tb):
                if kind is None:
                    self.commit()
                else:
                    self.rollback()
                return False

        self.check()
        if self.boundary.connecting is not None:
            raise PermissionError('nested sqlite connection')
        self.boundary.connecting = self
        try:
            c = sqlite3.connect(str(self.path), timeout=2, isolation_level=None,
                                factory=GuardConnection, cached_statements=0)
        finally:
            self.boundary.connecting = None
        self.connections += 1
        self._live_connections.append(c)
        c.enable_load_extension(False)
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA recursive_triggers=ON')
        assert c.execute('PRAGMA foreign_keys').fetchone() == (1,)
        assert c.execute('PRAGMA recursive_triggers').fetchone() == (1,)
        def authorize(action, a, b, database, origin):
            if database not in (None, 'main'):
                return sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and (b or a) in {'count', 'typeof', 'length'}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_PRAGMA and b is None and a in {'foreign_keys', 'recursive_triggers', 'table_info', 'index_list', 'index_info', 'foreign_key_list', 'foreign_key_check', 'integrity_check'}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_TRANSACTION and a == 'ROLLBACK':
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        profile_authorizer = getattr(self, '_Owner__authorizer', authorize)
        def guarded_authorizer(action, a, b, database, origin):
            if action == sqlite3.SQLITE_TRANSACTION and a != 'ROLLBACK' and not getattr(c, '_tx_gate', False):
                return sqlite3.SQLITE_DENY
            if physical and database == 'main' and action == sqlite3.SQLITE_DELETE and a == 'notifications':
                # F7 fixed sacrificial FK target; never enabled on normal connections.
                return sqlite3.SQLITE_OK
            if physical and database == 'main' and action in (sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and a in self.boundary.gate['new_tables']:
                return sqlite3.SQLITE_OK
            outcome = profile_authorizer(action, a, b, database, origin)
            if outcome == sqlite3.SQLITE_DENY:
                self.sql_denials.append({'action': action, 'a': a, 'b': b, 'database': database, 'origin': origin})
            return outcome
        c.set_authorizer(guarded_authorizer)
        return c

    def _ids(self):
        return tuple((p.stat().st_dev, p.stat().st_ino) for p in (self.root, self.path, self.sentinel))

    def check(self):
        if self not in self.boundary.owners or self.root.parent != SCRATCH or self.path != self.root / 'synthetic.sqlite' or self.sentinel != self.root / 'owner.sentinel':
            raise PermissionError('unissued owner')
        for p in (self.root, self.path, self.sentinel):
            ancestors_safe(p)
        if self._ids() != self._identity or self.sentinel.read_bytes() != self._token:
            raise PermissionError('owner identity/sentinel lost')


def new_owner(boundary):
    if type(boundary).__name__ != 'AuditBoundary':
        raise PermissionError('boundary required')
    return Owner(boundary)

