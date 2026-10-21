"""Raw SQLite readback independent of SQLAlchemy/metadata/schema module."""


def snapshot(c):
    def rows(sql):
        return [list(row) for row in c.execute(sql).fetchall()]
    schema = rows('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')
    names = sorted(row[1] for row in schema if row[0] == 'table' and not row[1].startswith('sqlite_'))
    # Never interpolate an untrusted SQLite identifier, even from sqlite_schema.
    if any(not name.replace('_', '').isascii() or not name.replace('_', '').isalnum() for name in names):
        raise PermissionError('unexpected raw table identifier')
    columns = {n: rows('PRAGMA table_info("' + n + '")') for n in names}
    index_lists = {n: rows('PRAGMA index_list("' + n + '")') for n in names}
    indexes = {}
    for n, entries in index_lists.items():
        indexes[n] = []
        for entry in entries:
            index = entry[1].replace('"', '""')
            indexes[n].append({'definition': entry, 'columns': rows('PRAGMA index_info("' + index + '")')})
    data = {n: sorted(rows('SELECT * FROM "' + n + '"'), key=repr) for n in names}
    return {'sqlite_schema': schema, 'columns': columns, 'indexes': indexes,
            'foreign_keys_by_table': {n: rows('PRAGMA foreign_key_list("' + n + '")') for n in names},
            'rows': data, 'foreign_key_check': rows('PRAGMA foreign_key_check'),
            'integrity_check': rows('PRAGMA integrity_check'),
            'foreign_keys': c.execute('PRAGMA foreign_keys').fetchone()[0],
            'recursive_triggers': c.execute('PRAGMA recursive_triggers').fetchone()[0]}


def main():
    import hashlib
    import importlib.machinery
    import json
    import os
    from pathlib import Path
    import sys
    import uuid
    here = Path(__file__).resolve().parent
    if sys.argv[1:] != ['--capability-stdin']:
        raise ValueError('only --capability-stdin is accepted; checkpoints are not capabilities')
    import stat
    import secrets
    if not stat.S_ISFIFO(os.fstat(sys.stdin.fileno()).st_mode):
        raise PermissionError('capability requires an inherited stdin pipe')
    challenge = secrets.token_hex(32)
    print(json.dumps({'challenge': challenge, 'child_pid': os.getpid(), 'parent_pid': os.getppid()}), flush=True)
    wire = sys.stdin.readline(8 * 1024 * 1024)
    if not wire.endswith('\n') or sys.stdin.read(1):
        raise PermissionError('exactly one bounded capability message required')
    report = json.loads(wire)
    if (report.get('challenge') != challenge or report.get('child_pid') != os.getpid() or
            report.get('parent_pid') != os.getppid() or report.get('purpose') != 'B-R01-fresh-readonly'):
        raise PermissionError('live parent/child challenge mismatch or replay')
    if len(report.get('nonce', '')) != 64:
        raise PermissionError('invalid one-use capability nonce')
    run_id = report['run_id']
    if uuid.UUID(hex=run_id).hex != run_id:
        raise PermissionError('noncanonical run id')
    proof = report['read_only_handoff']
    if proof['issued_run_id'] != run_id or proof['read_only'] is not True:
        raise PermissionError('handoff is not bound to its issuing run')
    if hashlib.sha256(json.dumps(report['raw23']['sqlite_schema'], sort_keys=True).encode()).hexdigest() != report['schema_sha256']:
        raise PermissionError('schema digest mismatch')
    ns = {'__file__': str(here / 'isolation_kernel.py'), '__name__': '_br_read_kernel'}
    exec(compile((here / 'isolation_kernel.py').read_bytes(), ns['__file__'], 'exec'), ns)
    inventory = ns['preflight']()
    scratch = ns['SCRATCH']
    root = Path(proof['root']).absolute()
    database = Path(proof['database']).absolute()
    if root.parent != scratch or not root.name.startswith('br_assignment_') or uuid.UUID(hex=root.name[14:]).hex != root.name[14:] or database != root / 'synthetic.sqlite':
        raise PermissionError('handoff outside exact new-owner shape')
    sentinel = root / 'owner.sentinel'
    exact_sources = {here / (n + '.py') for n in ('run_br_assignment','isolation_kernel','source_loader','test_assignment_real_route','readback')}
    exact_sources.add(ns['REPO'] / 'app/services/p3_assignment_schema.py')
    if {Path(p).absolute() for p in report['sources']} != exact_sources:
        raise PermissionError('checkpoint source inventory is not exact6')
    for path, expected in report['sources'].items():
        if ns['digest'](path) != expected:
            raise PermissionError('frozen source hash drift: ' + path)
    def check_identity():
        for p in (root, database, sentinel):
            ns['ancestors_safe'](p)
        identity = [[p.stat().st_dev, p.stat().st_ino] for p in (root, database, sentinel)]
        if identity != proof['identity'] or ns['digest'](sentinel) != proof['sentinel_sha256']:
            raise PermissionError('handoff sentinel/file identity lost')
    check_identity()
    if ns['digest'](database) != proof['database_sha256']:
        raise PermissionError('database bytes changed since issuance')
    loader = {'__file__': str(here / 'source_loader.py'), '__name__': '_br_read_loader'}
    exec(compile((here / 'source_loader.py').read_bytes(), loader['__file__'], 'exec'), loader)
    sys.meta_path[:] = [importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter, loader['ExactFinder'](inventory)]
    allowed = {os.path.normcase(os.path.abspath(p)) for p in [*inventory['runtime'], *inventory['libraries'], *exact_sources, database, sentinel]}
    uri = database.as_uri() + '?mode=ro'
    state = {'connecting': False}
    denials = []
    def audit(event, args):
        reason = None
        if event == 'open':
            path, mode, flags = args
            if isinstance(path, int) or (isinstance(mode, str) and any(x in mode for x in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                reason = 'readback forbids writes/fd opens'
            elif os.path.normcase(os.path.abspath(path)) not in allowed:
                reason = 'readback exact read denied: ' + str(path)
        elif event.startswith('sqlite3.connect'):
            if not state['connecting'] or event == 'sqlite3.connect' and args[0] != uri:
                reason = 'readback unissued connection'
        elif event.startswith(('socket.', 'subprocess.', 'os.system', 'os.spawn', 'os.exec', 'sqlite3.load_extension')) or event in {'os.mkdir','os.remove','os.rename','os.rmdir','os.link','os.symlink','os.truncate','os.chmod','os.utime'}:
            reason = 'readback external mutation/capability denied: ' + event
        elif event == 'import' and args[0].split('.')[0] in {'app','config','testing_safety'}:
            reason = 'normal app import denied'
        if reason:
            denials.append({'event': event, 'reason': reason})
            raise PermissionError(reason)
    sys.addaudithook(audit)
    import sqlite3
    class ReadConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            check_identity()
            return super().execute(sql, parameters)
    state['connecting'] = True
    try:
        c = sqlite3.connect(uri, uri=True, factory=ReadConnection, cached_statements=0, isolation_level=None)
    finally:
        state['connecting'] = False
    try:
        c.enable_load_extension(False)
        c.execute('PRAGMA query_only=ON')
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA recursive_triggers=ON')
        table_names = set(report['raw23']['rows'])
        index_names = {entry['definition'][1] for entries in report['raw23']['indexes'].values() for entry in entries}
        def authorize(action, a, b, db, origin):
            if db not in (None, 'main'):
                return sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_PRAGMA and ((b is None and a in {'foreign_keys','recursive_triggers','foreign_key_check','integrity_check'}) or (a in {'table_info','index_list','foreign_key_list'} and b in table_names) or (a == 'index_info' and b in index_names)):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        c.set_authorizer(authorize)
        controls = []
        for label, sql in [('ddl','CREATE TABLE forbidden(x)'), ('dml','DELETE FROM br_assignment_heads'),
                           ('pragma_write','PRAGMA query_only=OFF'), ('attach',"ATTACH DATABASE ':memory:' AS other")]:
            try:
                c.execute(sql)
            except sqlite3.DatabaseError:
                controls.append({'case': label, 'denied': True})
            else:
                raise AssertionError('readback SQL control escaped: ' + label)
        import subprocess
        for label, operation, event in [
            ('other_database', lambda: sqlite3.connect(':memory:'), 'sqlite3.connect'),
            ('file_write', lambda: open(database, 'rb+'), 'open'),
            ('other_process', lambda: subprocess.Popen([sys.executable, '-c', 'raise SystemExit(9)']), 'subprocess.Popen')]:
            before = len(denials)
            try:
                operation()
            except PermissionError:
                observed = denials[before:]
                if len(observed) != 1 or observed[0]['event'] != event:
                    raise AssertionError('wrong readback audit control denial')
                del denials[before:]
                controls.append({'case': label, 'denied': True, 'audit_event': event})
            else:
                raise AssertionError('readback audit control escaped: ' + label)
        actual = snapshot(c)
        if actual != report['raw23']:
            raise AssertionError('independent full23 rows/schema readback mismatch')
        if actual['foreign_key_check'] != [] or actual['integrity_check'] != [['ok']]:
            raise AssertionError('independent SQLite health check failed')
    finally:
        c.close()
    check_identity()
    if ns['digest'](database) != proof['database_sha256'] or denials:
        raise AssertionError('readback mutated database or swallowed an audit denial')
    print(json.dumps({'status': 'READBACK_PASS', 'scope': 'B-R01_PARTIAL', 'issuing_run_id': run_id,
                      'table_count': len(actual['rows']), 'schema_and_all_rows_equal': True,
                      'foreign_key_check': actual['foreign_key_check'], 'integrity_check': actual['integrity_check'],
                      'database_sha256_unchanged': True, 'unexpected_denials': denials,
                      'runtime_file_count': inventory['runtime_file_count'], 'library_file_count': inventory['library_file_count'],
                      'read_only_controls': controls, 'schema_sha256': report['schema_sha256'], 'protocol': 'parent-registry-direct-stdin-challenge-v1'}, indent=2))
    return 0


if __name__ == '__main__':
    import sys
    try:
        code = main()
    except BaseException as exc:
        frames = []
        tb = exc.__traceback__
        while tb:
            frames.append({'file': tb.tb_frame.f_code.co_filename, 'function': tb.tb_frame.f_code.co_name, 'line': tb.tb_lineno})
            tb = tb.tb_next
        print({'status': 'READBACK_FAILED', 'exception': type(exc).__name__, 'message': str(exc), 'frames': frames})
        code = 1
    raise SystemExit(code)
