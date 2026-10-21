"""B-R01 vertical behavioral tests; no normal application imports."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_owned(name):
    namespace = {'__file__': str(ROOT / (name + '.py')), '__name__': name}
    exec(compile((ROOT / (name + '.py')).read_bytes(), namespace['__file__'], 'exec'), namespace)
    return namespace

def test_preflight_inventory():
    result = load_owned('isolation_kernel')['preflight']()
    assert result['library_file_count'] == 982, result
    assert result['runtime_file_count'] > 0, result
    assert result['mismatches'] == [], result
    assert result['runtime_excludes_site_packages'] is True, result

def test_read_guard_denies_unlisted_file():
    kernel = load_owned('isolation_kernel')
    guard = kernel['AuditBoundary'](kernel['preflight']())
    try:
        guard.check_read(ROOT.parent / 'UNAPPROVED_NEGATIVE_CONTROL_DO_NOT_CREATE')
    except PermissionError:
        pass
    else:
        raise AssertionError('exact read guard permitted an unlisted file')

def test_installed_audit_blocks_external_effects():
    kernel = load_owned('isolation_kernel')
    guard = kernel['AuditBoundary'](kernel['preflight']())
    guard.install()
    events = [('open', (str(ROOT.parent / 'UNAPPROVED_NEGATIVE_CONTROL_DO_NOT_CREATE'), 'r', 0)),
              ('socket.connect', (None, ('127.0.0.1', 1))),
              ('subprocess.Popen', ('forbidden-negative-control', [], None, {})),
              ('sqlite3.connect', ('forbidden-negative-control.sqlite',))]
    for event, args in events:
        try:
            sys.audit(event, *args)
        except PermissionError:
            continue
        raise AssertionError('installed audit did not deny ' + event)

def test_exact_finder_resolves_manifest_namespace_only():
    inventory = load_owned('isolation_kernel')['preflight']()
    finder = load_owned('source_loader')['ExactFinder'](inventory)
    spec = finder.find_spec('flask.sansio')
    assert spec is not None, 'manifest-owned flask.sansio namespace was not resolved'
    assert spec.submodule_search_locations is not None
    assert finder.find_spec('flask.UNAPPROVED_namespace') is None


def test_preflight_platform_probe_requires_no_guard_exception():
    import platform
    kernel = load_owned('isolation_kernel')
    inventory = kernel['preflight']()
    guard = kernel['AuditBoundary'](inventory)
    guard.install()
    try:
        measured = platform.machine()
    except PermissionError as exc:
        raise AssertionError('preflight did not cache real local platform metadata') from exc
    assert isinstance(measured, str) and measured
    assert guard.denials == []


def test_actual_model_mapper_closure():
    result = load_owned('source_loader')['load_models'](BOUNDARY)
    assert result['model_count'] == 19, result
    assert result['table_names'] == sorted(BOUNDARY.gate['actual_tables']), result
    assert result['configured'] is True, result
    assert BOUNDARY.denials == [], BOUNDARY.denials
    globals()['MODELS'] = result


def test_factory_issues_fresh_sentinel_owner_without_sqlite():
    kernel = load_owned('isolation_kernel')
    factory = kernel.get('new_owner')
    assert callable(factory), 'sentinel-owned factory is not implemented'
    owner = factory(BOUNDARY)
    owner.check()
    assert owner.root.parent == kernel['SCRATCH']
    assert owner.path.name == 'synthetic.sqlite'
    assert owner.path.read_bytes() == b''
    assert owner.sentinel.read_bytes() == owner._token
    assert owner.connections == 0
    globals()['OWNER'] = owner

def test_owner_connection_select_only():
    owner = load_owned('isolation_kernel')['new_owner'](BOUNDARY)
    connect = getattr(owner, 'connect', None)
    assert callable(connect), 'owned guarded DBAPI connection is not implemented'
    c = connect()
    try:
        assert c.execute('SELECT 1').fetchone() == (1,)
        assert c.execute('PRAGMA foreign_keys').fetchone() == (1,)
        assert c.execute('PRAGMA recursive_triggers').fetchone() == (1,)
        for sql in ['CREATE TABLE forbidden(x)', 'ATTACH DATABASE ":memory:" AS other', 'PRAGMA foreign_keys=OFF', 'PRAGMA recursive_triggers=OFF', 'VACUUM', 'SELECT load_extension("forbidden")']:
            try:
                c.execute(sql)
            except Exception as exc:
                assert type(exc).__module__ == 'sqlite3', (sql, exc)
            else:
                raise AssertionError('SQL guard escaped: ' + sql)
    finally:
        c.close()

def test_sidecar_metadata_uses_actual_columns_without_registry_mutation():
    path = Path('C:/Users/aproa/momoai_web/app/services/p3_assignment_schema.py')
    assert path.is_file(), 'approved independent sidecar schema is not implemented'
    ns = {'__file__': str(path), '__name__': '_br_schema'}
    exec(compile(path.read_bytes(), str(path), 'exec'), ns)
    actual = MODELS['db'].metadata
    before = repr([(n, list(t.columns), list(t.constraints), list(t.indexes)) for n, t in actual.tables.items()])
    sidecar = ns['build_schema'](actual)
    assert sidecar is not actual
    assert sorted(sidecar.tables) == sorted(BOUNDARY.gate['new_tables'])
    after = repr([(n, list(t.columns), list(t.constraints), list(t.indexes)) for n, t in actual.tables.items()])
    assert before == after, 'actual metadata was modified'
    assert len(actual.tables) == 19
    for table in sidecar.tables.values():
        for fk in table.foreign_keys:
            assert fk.ondelete == 'RESTRICT'
            assert fk.column is fk.column.table.c[fk.column.name]
            assert fk.column.table.metadata in (actual, sidecar)
    globals()['SIDECAR'] = sidecar
    globals()['SCHEMA'] = ns

def test_factory_creates_exact23_then_permanently_closes_setup():
    if 'SIDECAR' not in globals():
        test_sidecar_metadata_uses_actual_columns_without_registry_mutation()
    owner = load_owned('isolation_kernel')['new_owner'](BOUNDARY)
    initialize = getattr(owner, 'initialize', None)
    assert callable(initialize), 'SQLAlchemy exact23 setup factory is not implemented'
    engine = initialize(MODELS['db'].metadata, SIDECAR)
    with engine.connect() as c:
        names = sorted(r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        assert names == sorted(BOUNDARY.gate['actual_tables'] + BOUNDARY.gate['new_tables'])
        assert c.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
        assert c.exec_driver_sql('PRAGMA integrity_check').fetchall() == [('ok',)]
    try:
        initialize(MODELS['db'].metadata, SIDECAR)
    except PermissionError:
        pass
    else:
        raise AssertionError('setup reopened')
    globals()['READY_OWNER'] = owner
    globals()['ENGINE'] = engine

def test_exact_physical_transition_trigger_inventory():
    test_factory_creates_exact23_then_permanently_closes_setup()
    rules = {'revisions': ['insert_conflict','update','delete','lineage_insert'],
             'heads': ['insert_conflict','delete','transition_insert','transition_update'],
             'receipts': ['insert_conflict','update','delete'],
             'outbox': ['insert_conflict','update','delete']}
    expected = sorted('br_assignment_' + suffix + '_' + rule + '_guard' for suffix, names in rules.items() for rule in names)
    with ENGINE.connect() as c:
        observed = sorted(r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='trigger'"))
    assert observed == expected, {'expected': expected, 'actual': observed}

def test_factory_seeds_only_eight_synthetic_reference_tables():
    test_factory_creates_exact23_then_permanently_closes_setup()
    with ENGINE.connect() as c:
        counts = {name: c.exec_driver_sql('SELECT count(*) FROM ' + name).scalar_one() for name in MODELS['table_names']}
    assert {n for n, count in counts.items() if count} == {'users','students','courses','course_enrollments','course_sessions','assignments','assignment_submissions','notifications'}, counts
    assert counts['users'] == 2
    globals().setdefault('ACCEPTANCE', {})['reference_row_counts'] = counts

def test_legal_initial_revision_head_transition():
    test_factory_seeds_only_eight_synthetic_reference_tables()
    transition = getattr(READY_OWNER, 'fixed_transition', None)
    assert callable(transition), 'fixed legal initial transition is not implemented'
    result = transition(1)
    assert result['generation'] == 1
    with ENGINE.connect() as c:
        h = c.exec_driver_sql('SELECT revision_id,generation,legacy_digest FROM br_assignment_heads').one()
        r = c.exec_driver_sql('SELECT revision_id,revision_no,legacy_digest,parent_revision_id FROM br_assignment_revisions').one()
        assert tuple(h) == tuple(r[:3])
        assert r[3] is None

def test_legal_successor_revision_head_transition():
    test_legal_initial_revision_head_transition()
    result = READY_OWNER.fixed_transition(2)
    assert result['generation'] == 2
    with ENGINE.connect() as c:
        assert c.exec_driver_sql('SELECT generation FROM br_assignment_heads').scalar_one() == 2
        rows = c.exec_driver_sql('SELECT revision_id,revision_no,parent_revision_id FROM br_assignment_revisions ORDER BY revision_no').fetchall()
        assert len(rows) == 2 and rows[1][2] == rows[0][0]

def test_legal_receipt_outbox_insert():
    test_legal_successor_revision_head_transition()
    ids = READY_OWNER.fixture_ids
    with ENGINE.begin() as c:
        c.connection.driver_connection.begin_immediate()
        c.execute(SIDECAR.tables['br_assignment_receipts'].insert().values(command_id='synthetic-command', actor_user_id=ids['actor'],
            idempotency_key='synthetic-key', assignment_id=ids['assignment'], submission_id=ids['submission'],
            revision_id='00000000-0000-0000-0000-000000000102', request_digest='c'*64,
            response_status=201, response_body='{}', committed_at='2026-10-18T12:00:00.000000'))
        c.execute(SIDECAR.tables['br_assignment_outbox'].insert().values(event_id='synthetic-event', command_id='synthetic-command',
            recipient_user_id=ids['teacher'], notification_id=ids['notification'], event_type='assignment_submitted', payload='{}',
            delivery_state='pending', attempt_count=0, created_at='2026-10-18T12:00:00.000000'))
    with ENGINE.connect() as c:
        assert c.exec_driver_sql('SELECT count(*) FROM br_assignment_receipts').scalar_one() == 1
        assert c.exec_driver_sql('SELECT count(*) FROM br_assignment_outbox').scalar_one() == 1

def test_runtime_sql_transaction_api_cannot_commit():
    test_factory_creates_exact23_then_permanently_closes_setup()
    c = READY_OWNER.connect()
    try:
        for sql in ('BEGIN IMMEDIATE', 'COMMIT', 'SAVEPOINT arbitrary', 'RELEASE arbitrary'):
            try:
                c.execute(sql)
            except Exception as exc:
                assert type(exc).__module__ == 'sqlite3', exc
            else:
                c.rollback()
                raise AssertionError('arbitrary SQL transaction API escaped: ' + sql)
    finally:
        c.rollback()
        c.close()

def test_raw23_readback_has_complete_schema_and_rows():
    test_legal_receipt_outbox_insert()
    assert (ROOT / 'readback.py').is_file(), 'independent raw23 readback is not implemented'
    raw = load_owned('readback')
    c = READY_OWNER.connect()
    try:
        snapshot = raw['snapshot'](c)
    finally:
        c.close()
    assert sorted(snapshot['rows']) == sorted(BOUNDARY.gate['actual_tables'] + BOUNDARY.gate['new_tables'])
    assert snapshot['foreign_key_check'] == []
    assert snapshot['integrity_check'] == [['ok']]
    assert snapshot['recursive_triggers'] == 1
    assert snapshot['foreign_keys'] == 1
    assert len(snapshot['columns']) == 23 and len(snapshot['indexes']) == 23 and len(snapshot['foreign_keys_by_table']) == 23
    assert len([r for r in snapshot['sqlite_schema'] if r[0] == 'trigger']) == 14
    globals()['RAW_BASELINE'] = snapshot
    ACCEPTANCE.update({'raw23': snapshot, 'owner_path': str(READY_OWNER.root)})

def test_executemany_revalidates_owner_for_each_statement():
    test_legal_successor_revision_head_transition()
    raw = load_owned('readback')['snapshot']
    owner = READY_OWNER
    c = owner.connect()
    baseline = raw(c)
    token = owner._token
    c.begin_immediate()
    ids = owner.fixture_ids
    def values():
        yield ('probe1', ids['actor'], 'probe1', ids['assignment'], ids['submission'], '00000000-0000-0000-0000-000000000101', 'c'*64, 201, '{}', '2026-10-18T12:00:00.000000')
        owner._token = b'SYNTHETIC sentinel fault injection'
        yield ('probe2', ids['actor'], 'probe2', ids['assignment'], ids['submission'], '00000000-0000-0000-0000-000000000102', 'c'*64, 201, '{}', '2026-10-18T12:00:00.000000')
    rejected = False
    try:
        c.executemany('INSERT INTO br_assignment_receipts VALUES (?,?,?,?,?,?,?,?,?,?)', values())
    except PermissionError:
        rejected = True
    finally:
        c.rollback()
        owner._token = token
        assert raw(c) == baseline
        c.close()
    assert rejected, 'executemany used one owner check for multiple SQL statements'

def test_immutable_update_delete_are_physical_not_authorizer_masked():
    import sqlite3
    test_raw23_readback_has_complete_schema_and_rows()
    c = getattr(READY_OWNER, '_constraint_connection', READY_OWNER.connect)()
    try:
        for table in ('br_assignment_revisions','br_assignment_receipts','br_assignment_outbox'):
            for sql, message in [('UPDATE ' + table + ' SET ' + ('content=content' if table.endswith('revisions') else 'response_body=response_body' if table.endswith('receipts') else 'payload=payload'), 'update'), ('DELETE FROM ' + table, 'delete')]:
                c.begin_immediate()
                try:
                    c.execute(sql)
                except sqlite3.IntegrityError as exc:
                    assert str(exc) == message, (sql, str(exc))
                except sqlite3.DatabaseError as exc:
                    raise AssertionError('physical trigger was masked by authorizer: ' + sql) from exc
                else:
                    raise AssertionError('immutable SQL escaped: ' + sql)
                finally:
                    c.rollback()
                assert load_owned('readback')['snapshot'](c) == RAW_BASELINE
    finally:
        c.close()

def test_conflicting_insert_never_masks_replace_or_upsert():
    import sqlite3
    test_raw23_readback_has_complete_schema_and_rows()
    c = READY_OWNER._constraint_connection()
    results = []
    raw = load_owned('readback')['snapshot']
    try:
        for table in SIDECAR.tables:
            cur = c.execute('SELECT * FROM ' + table + ' ORDER BY 1')
            columns = [d[0] for d in cur.description]
            original = dict(zip(columns, cur.fetchone()))
            for syntax in ('INSERT OR REPLACE', 'REPLACE', 'INSERT_UPSERT'):
                sql = ('INSERT' if syntax == 'INSERT_UPSERT' else syntax) + ' INTO ' + table + ' (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
                if syntax == 'INSERT_UPSERT':
                    sql += ' ON CONFLICT DO UPDATE SET ' + columns[0] + '=excluded.' + columns[0]
                c.begin_immediate()
                try:
                    c.execute(sql, tuple(original[n] for n in columns))
                except sqlite3.IntegrityError as exc:
                    assert str(exc) == 'insert_conflict', {'table': table, 'syntax': syntax, 'masked_by': str(exc)}
                else:
                    raise AssertionError('conflict escaped: ' + table + ' ' + syntax)
                finally:
                    c.rollback()
                assert raw(c) == RAW_BASELINE
                results.append({'table': table, 'syntax': syntax, 'conflict': 'existing_row', 'unchanged': True})
    finally:
        c.close()
    ACCEPTANCE['replace_upsert_existing_row'] = results

def test_setup_reference_replace_is_rejected_before_closure():
    if 'SIDECAR' not in globals():
        test_sidecar_metadata_uses_actual_columns_without_registry_mutation()
    owner = load_owned('isolation_kernel')['new_owner'](BOUNDARY)
    getattr(owner, 'initialize_for_setup_probe', owner.initialize)(MODELS['db'].metadata, SIDECAR)
    probes = getattr(owner, 'setup_probe_results', [])
    assert probes, 'fixed setup-phase reference REPLACE probes are not implemented'
    assert {r['table'] for r in probes} == {'users','students','courses','course_enrollments','course_sessions','assignments','assignment_submissions','notifications'}
    assert all(r['error'] in {'setup_reference_conflict', 'not authorized'} and r['unchanged'] for r in probes), probes
    globals().setdefault('ACCEPTANCE', {})['setup_reference_replace'] = probes

def test_connection_security_controls_cannot_be_replaced():
    test_factory_creates_exact23_then_permanently_closes_setup()
    c = READY_OWNER.connect()
    try:
        for name, action in [('extension_enable', lambda: c.enable_load_extension(True)), ('authorizer_remove', lambda: c.set_authorizer(None))]:
            try:
                action()
            except PermissionError:
                pass
            else:
                raise AssertionError('connection security control was caller-mutable: ' + name)
    finally:
        c.enable_load_extension(False)
        c.close()

def test_owner_loss_denies_preconnect_sql_and_commit_with_rollback():
    raw = load_owned('readback')['snapshot']
    results = []
    for point in ('preconnect','presql','precommit'):
        test_legal_initial_revision_head_transition()
        owner = READY_OWNER
        c = owner.connect()
        baseline = raw(c)
        token = owner._token
        if point == 'precommit':
            c.begin_immediate()
            row = list(c.execute('SELECT * FROM br_assignment_revisions').fetchone())
            columns = [d[0] for d in c.execute('SELECT * FROM br_assignment_revisions').description]
            values = dict(zip(columns, row))
            values.update(revision_id='synthetic-sentinel-probe', submission_id=owner.fixture_ids['submission2'])
            c.execute('INSERT INTO br_assignment_revisions VALUES (' + ','.join('?' for _ in columns) + ')', tuple(values[n] for n in columns))
        owner._token = b'SYNTHETIC fixed-point sentinel fault'
        denied = False
        try:
            if point == 'preconnect':
                owner.connect()
            elif point == 'presql':
                c.execute('SELECT 1')
            else:
                c.commit()
        except PermissionError:
            denied = True
        finally:
            # Cleanup must remain possible with the owner boundary still lost.
            c.rollback()
            owner._token = token
        assert denied, point
        assert raw(c) == baseline, point
        c.close()
        results.append({'point': point, 'denied': True, 'rollback_while_lost': True, 'complete23_unchanged': True, 'owner': str(owner.root)})
    globals().setdefault('ACCEPTANCE', {})['sentinel_faults'] = results


def test_setup_cannot_reopen_by_caller_phase_label():
    import sqlite3
    test_factory_creates_exact23_then_permanently_closes_setup()
    owner = READY_OWNER
    owner.phase = 'setup'
    owner.setup = True
    c = owner.connect()
    try:
        for sql in ('CREATE TABLE br_not_approved(x)', 'INSERT INTO users SELECT * FROM users WHERE 0', 'UPDATE students SET name=name', 'DELETE FROM students', 'PRAGMA recursive_triggers=OFF', 'PRAGMA foreign_keys=OFF', "ATTACH DATABASE ':memory:' AS other", 'VACUUM'):
            try:
                c.execute(sql)
            except sqlite3.DatabaseError:
                pass
            else:
                raise AssertionError('closed setup escaped: ' + sql)
        try:
            owner.initialize_for_setup_probe(MODELS['db'].metadata, SIDECAR)
        except PermissionError:
            pass
        else:
            raise AssertionError('diagnostic setup reopened an existing owner')
    finally:
        c.close()

def test_readonly_handoff_is_bound_to_new_owner_identity():
    test_raw23_readback_has_complete_schema_and_rows()
    export = getattr(READY_OWNER, 'handoff', None)
    assert callable(export), 'read-only newly issued owner handoff is not implemented'
    proof = export()
    assert proof['root'] == str(READY_OWNER.root)
    assert proof['database'] == str(READY_OWNER.path)
    assert proof['identity'] == [list(pair) for pair in READY_OWNER._identity]
    assert proof['read_only'] is True
    assert proof['issued_run_id'] == BOUNDARY.run_id
    ACCEPTANCE['read_only_handoff'] = proof

def test_caller_building_label_cannot_reissue_filesystem_writer():
    owner = load_owned('isolation_kernel')['new_owner'](BOUNDARY)
    owner.building = True
    assert not BOUNDARY.owner_path(owner.path, writing=True), 'caller-mutable building label reopened filesystem writes'
    assert not BOUNDARY.owner_path(owner.sentinel, writing=True), 'caller-mutable building label reopened sentinel writes'
    owner.check()

def test_untracked_fd_open_is_not_an_audit_escape():
    rejected = False
    before = len(BOUNDARY.denials)
    try:
        sys.audit('open', 123456789, 'r', 0)
    except PermissionError:
        rejected = True
    finally:
        # Explicit policy-only negative control; no fd is opened/read.
        controls = BOUNDARY.denials[before:]
        expected = [{'event': 'open', 'path': '123456789', 'reason': 'untracked file descriptor'}]
        if rejected:
            assert controls == expected, controls
        del BOUNDARY.denials[before:]
        globals().setdefault('ACCEPTANCE', {})['expected_fd_control_denials'] = controls
    assert rejected, 'untracked integer file descriptors bypassed the exact open policy'

def test_readback_rejects_checkpoint_cli_before_any_file_read():
    reader = load_owned('readback')
    saved = sys.argv
    try:
        sys.argv = [str(ROOT / 'readback.py'), '--checkpoint', str(ROOT / 'evidence' / ('0'*32 + '_checkpoint.json'))]
        try:
            reader['main']()
        except ValueError as exc:
            assert 'capability-stdin' in str(exc)
        else:
            raise AssertionError('retained checkpoint CLI remained usable')
    finally:
        sys.argv = saved

def test_live_parent_single_use_stdin_child_readback():
    test_raw23_readback_has_complete_schema_and_rows()
    launch = getattr(BOUNDARY, 'fresh_readback', None)
    assert callable(launch), 'F7 live parent registry/pipe child is not implemented'
    result = launch(READY_OWNER)
    assert result['status'] == 'READBACK_PASS', result
    assert result['table_count'] == 23
    assert result['schema_and_all_rows_equal'] is True
    assert result['replay_denied'] is True
    assert result['writers_closed'] is True
    assert result['unexpected_denials'] == []
    ACCEPTANCE['f7_live_child'] = result

def test_actual_windows_junction_ancestor_is_rejected():
    probe = getattr(BOUNDARY, 'fixed_junction_probe', None)
    assert callable(probe), 'actual Windows junction probe is not implemented'
    result = probe()
    assert result['created_reparse_point'] and result['ancestor_denied'] and result['cleaned']
    globals().setdefault('ACCEPTANCE', {})['junction_probe'] = result


def _fresh_physical_fixture(full=True):
    if full:
        test_raw23_readback_has_complete_schema_and_rows()
    else:
        test_factory_creates_exact23_then_permanently_closes_setup()
    return READY_OWNER


def _raw_insert(c, table, values, syntax='INSERT', upsert=False):
    columns = list(values)
    sql = syntax + ' INTO ' + table + ' (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
    if upsert:
        sql += ' ON CONFLICT DO UPDATE SET ' + columns[0] + '=excluded.' + columns[0]
    return sql, tuple(values[n] for n in columns)


def _reject_unchanged(owner, label, sql, params, expected):
    import sqlite3
    raw = load_owned('readback')['snapshot']
    c = owner._constraint_connection()
    try:
        baseline = raw(c)
        c.begin_immediate()
        try:
            c.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            assert str(exc) == expected, (label, str(exc), expected)
        else:
            raise AssertionError('raw negative escaped: ' + label)
        finally:
            c.rollback()
        assert raw(c) == baseline, label
        assert baseline['foreign_key_check'] == [] and baseline['integrity_check'] == [['ok']]
    finally:
        c.close()
    return {'case': label, 'error': expected, 'all23_schema_rows_unchanged': True, 'owner': str(owner.root)}


def test_alternate_unique_replace_upsert_matrix():
    # Existing enforcement regression, not a new RED/GREEN implementation claim.
    owner = _fresh_physical_fixture()
    c = owner.connect()
    try:
        originals = {}
        for t in ('revisions','receipts','outbox'):
            cursor = c.execute('SELECT * FROM br_assignment_' + t + ' ORDER BY 1 DESC')
            originals[t] = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
    finally:
        c.close()
    cases = [
        ('revisions','uq_br_revision_no', {'revision_id':'new-alt-revision'}),
        ('revisions','uq_br_revision_target', {}), # logically overlaps global revision PK
        ('receipts','uq_br_actor_key', {'command_id':'new-alt-command','revision_id':'00000000-0000-0000-0000-000000000101'}),
        ('receipts','uq_br_receipt_revision', {'command_id':'new-alt-command','idempotency_key':'new-alt-key'}),
        ('outbox','notification_unique', {'event_id':'new-alt-event','recipient_user_id':owner.fixture_ids['actor']}),
        ('outbox','uq_br_outbox_event', {'event_id':'new-alt-event','notification_id':owner.fixture_ids['notification2']}),
    ]
    results = []
    for suffix, key, changes in cases:
        values = dict(originals[suffix], **changes)
        for syntax in ('INSERT OR REPLACE','REPLACE','UPSERT'):
            sql, params = _raw_insert(None, 'br_assignment_' + suffix, values,
                'INSERT' if syntax == 'UPSERT' else syntax, syntax == 'UPSERT')
            results.append(_reject_unchanged(owner, key + '/' + syntax, sql, params, 'insert_conflict'))
    ACCEPTANCE['alternate_unique_matrix'] = results
    ACCEPTANCE['unique_overlap_notes'] = ['revision_target composite necessarily overlaps global revision_id PK; remaining alternate unique probes use nonconflicting PKs and valid FK targets']


def _revision_values(owner, **changes):
    ids = owner.fixture_ids
    values = dict(revision_id='raw-revision-1', submission_id=ids['submission'], revision_no=1,
        parent_revision_id=None, actor_user_id=ids['actor'], content='SYNTHETIC', file_manifest='{}',
        payload_digest='a'*64, legacy_snapshot='{}', legacy_digest='b'*64,
        enrollment_id=ids['enrollment'], course_id=ids['course'], session_id=None,
        scope_state='unknown', program_id=None, edition_id=None, rubric_id=None, captured_at='2026-10-18T12:00:00.000000')
    values.update(changes)
    return values


def test_raw_revision_lineage_negative_matrix():
    owner = _fresh_physical_fixture(False)
    results = []
    for label, changes in [('initial_parent', {'parent_revision_id':'missing'}),
                           ('initial_self', {'parent_revision_id':'raw-revision-1'}),
                           ('successor_without_head', {'revision_no':2,'parent_revision_id':'missing'})]:
        sql, params = _raw_insert(None, 'br_assignment_revisions', _revision_values(owner, **changes))
        results.append(_reject_unchanged(owner, label, sql, params, 'lineage_insert'))
    owner.fixed_transition(1)
    for label, changes in [
        ('successor_null', {'revision_no':2}),
        ('successor_self', {'revision_no':2,'parent_revision_id':'raw-revision-1'}),
        ('future_parent', {'revision_no':2,'parent_revision_id':'future-revision'}),
        ('foreign_parent', {'revision_no':2,'submission_id':owner.fixture_ids['submission2'],'parent_revision_id':'00000000-0000-0000-0000-000000000101'}),
        ('skip_number', {'revision_no':3,'parent_revision_id':'00000000-0000-0000-0000-000000000101'}),
        ('initial_with_existing_head', {'revision_no':1})]:
        sql, params = _raw_insert(None, 'br_assignment_revisions', _revision_values(owner, **changes))
        results.append(_reject_unchanged(owner, label, sql, params, 'insert_conflict' if label == 'initial_with_existing_head' else 'lineage_insert'))
    globals().setdefault('ACCEPTANCE', {})['revision_lineage_matrix'] = results


def test_raw_head_negative_matrix():
    owner = _fresh_physical_fixture(False)
    c = owner.connect()
    try:
        c.begin_immediate()
        c.execute(*_raw_insert(None, 'br_assignment_revisions', _revision_values(owner)))
        c.commit()
    finally:
        c.close()
    initial = dict(submission_id=owner.fixture_ids['submission'], revision_id='raw-revision-1', generation=1, legacy_digest='b'*64)
    results = []
    for label, changes in [('initial_generation', {'generation':2}),('initial_target', {'revision_id':'missing'}),
                           ('initial_submission', {'submission_id':owner.fixture_ids['submission2']}),('initial_digest', {'legacy_digest':'c'*64})]:
        sql, params = _raw_insert(None, 'br_assignment_heads', dict(initial, **changes))
        results.append(_reject_unchanged(owner, label, sql, params, 'transition_insert'))
    c = owner.connect()
    try:
        c.begin_immediate()
        c.execute(*_raw_insert(None, 'br_assignment_heads', initial))
        successor = _revision_values(owner, revision_id='raw-revision-2', revision_no=2, parent_revision_id='raw-revision-1')
        c.execute(*_raw_insert(None, 'br_assignment_revisions', successor))
        c.commit()
    finally:
        c.close()
    legal = dict(revision_id='raw-revision-2',generation=2,legacy_digest='b'*64)
    for label, changes in [('submission_change', {'submission_id':owner.fixture_ids['submission2']}),
                           ('generation_same', {'generation':1}),('generation_decrease', {'generation':0}),
                           ('generation_skip', {'generation':3}),('wrong_parent_target', {'revision_id':'raw-revision-1'}),
                           ('missing_target', {'revision_id':'missing'}),('update_digest', {'legacy_digest':'c'*64})]:
        values = dict(legal, **changes)
        sql = 'UPDATE br_assignment_heads SET ' + ','.join(n+'=?' for n in values)
        results.append(_reject_unchanged(owner, label, sql, tuple(values.values()), 'transition_update'))
    results.append(_reject_unchanged(owner, 'head_delete', 'DELETE FROM br_assignment_heads', (), 'delete'))
    for syntax in ('INSERT OR REPLACE','REPLACE','UPSERT'):
        sql, params = _raw_insert(None, 'br_assignment_heads', initial, 'INSERT' if syntax == 'UPSERT' else syntax, syntax == 'UPSERT')
        results.append(_reject_unchanged(owner, 'head_pk/'+syntax, sql, params, 'insert_conflict'))
    globals().setdefault('ACCEPTANCE', {})['head_negative_matrix'] = results


def test_independent_foreign_key_insert_negatives():
    owner = _fresh_physical_fixture(False)
    results = []
    for field in ('submission_id','actor_user_id','enrollment_id','course_id','session_id'):
        sql, params = _raw_insert(None, 'br_assignment_revisions', _revision_values(owner, **{field:'missing-synthetic-FK'}))
        results.append(_reject_unchanged(owner, 'revision_fk/'+field, sql, params, 'FOREIGN KEY constraint failed'))
    globals().setdefault('ACCEPTANCE', {})['independent_fk'] = results

def test_unmasked_notification_delete_restrict():
    owner = _fresh_physical_fixture()
    result = _reject_unchanged(owner, 'notification_restrict', 'DELETE FROM notifications WHERE notification_id=?',
        (owner.fixture_ids['notification'],), 'FOREIGN KEY constraint failed')
    ACCEPTANCE['unmasked_restrict'] = [result]


# Test-owned closed SQL specification. Never imported/read/generated from schema implementation.
EXPECTED_TRIGGER_CONDITIONS = {
    'br_assignment_revisions_insert_conflict_guard': "EXISTS(SELECT 1 FROM br_assignment_revisions WHERE revision_id=NEW.revision_id OR (submission_id=NEW.submission_id AND revision_no=NEW.revision_no))",
    'br_assignment_revisions_lineage_insert_guard': "NOT EXISTS(SELECT 1 FROM br_assignment_revisions WHERE revision_id=NEW.revision_id OR (submission_id=NEW.submission_id AND revision_no=NEW.revision_no)) AND (NOT ((NEW.revision_no=1 AND NEW.parent_revision_id IS NULL AND NOT EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id)) OR (NEW.revision_no>1 AND NEW.parent_revision_id IS NOT NULL AND NEW.parent_revision_id != NEW.revision_id AND EXISTS(SELECT 1 FROM br_assignment_heads h JOIN br_assignment_revisions p ON p.revision_id=h.revision_id AND p.submission_id=h.submission_id WHERE h.submission_id=NEW.submission_id AND h.generation=NEW.revision_no-1 AND h.revision_id=NEW.parent_revision_id AND p.revision_no=NEW.revision_no-1))))",
    'br_assignment_heads_insert_conflict_guard': "EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id)",
    'br_assignment_heads_transition_insert_guard': "NOT EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id) AND (NEW.generation != 1 OR NOT EXISTS(SELECT 1 FROM br_assignment_revisions r WHERE r.submission_id=NEW.submission_id AND r.revision_id=NEW.revision_id AND r.revision_no=1 AND r.parent_revision_id IS NULL AND r.legacy_digest=NEW.legacy_digest))",
    'br_assignment_heads_transition_update_guard': "NEW.submission_id != OLD.submission_id OR NEW.generation != OLD.generation+1 OR NOT EXISTS(SELECT 1 FROM br_assignment_revisions r WHERE r.submission_id=NEW.submission_id AND r.revision_id=NEW.revision_id AND r.revision_no=NEW.generation AND r.parent_revision_id=OLD.revision_id AND r.legacy_digest=NEW.legacy_digest)",
    'br_assignment_receipts_insert_conflict_guard': "EXISTS(SELECT 1 FROM br_assignment_receipts WHERE command_id=NEW.command_id OR (actor_user_id=NEW.actor_user_id AND idempotency_key=NEW.idempotency_key) OR revision_id=NEW.revision_id)",
    'br_assignment_outbox_insert_conflict_guard': "EXISTS(SELECT 1 FROM br_assignment_outbox WHERE event_id=NEW.event_id OR notification_id=NEW.notification_id OR (command_id=NEW.command_id AND recipient_user_id=NEW.recipient_user_id AND event_type=NEW.event_type))",
}
EXPECTED_UNCONDITIONAL_TRIGGERS = {
    'br_assignment_revisions_update_guard': ('br_assignment_revisions','UPDATE','update'),
    'br_assignment_revisions_delete_guard': ('br_assignment_revisions','DELETE','delete'),
    'br_assignment_heads_delete_guard': ('br_assignment_heads','DELETE','delete'),
    'br_assignment_receipts_update_guard': ('br_assignment_receipts','UPDATE','update'),
    'br_assignment_receipts_delete_guard': ('br_assignment_receipts','DELETE','delete'),
    'br_assignment_outbox_update_guard': ('br_assignment_outbox','UPDATE','update'),
    'br_assignment_outbox_delete_guard': ('br_assignment_outbox','DELETE','delete'),
}


def test_trigger_sql_matches_independent_test_owned_specification():
    owner = _fresh_physical_fixture(False)
    c = owner.connect()
    try:
        observed = dict(c.execute("SELECT name,sql FROM sqlite_schema WHERE type='trigger'"))
    finally:
        c.close()
    expected = {}
    for name, (table, verb, message) in EXPECTED_UNCONDITIONAL_TRIGGERS.items():
        expected[name] = f"CREATE TRIGGER {name} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT, '{message}'); END"
    for name, condition in EXPECTED_TRIGGER_CONDITIONS.items():
        # Parse the independently fixed expected identifiers, never metadata/implementation.
        table = '_'.join(name.split('_')[:3])
        rule = name[len(table)+1:-6]
        verb = 'UPDATE' if rule == 'transition_update' else 'INSERT'
        expected[name] = f"CREATE TRIGGER {name} BEFORE {verb} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, '{rule}'); END"
    normalize = lambda mapping: {n: ' '.join(sql.split()) for n, sql in mapping.items()}
    assert normalize(observed) == normalize(expected), {'actual': observed, 'expected': expected}
    assert normalize(SCHEMA['trigger_sql']()) == normalize(expected)
    globals().setdefault('ACCEPTANCE', {})['independent_trigger_sql'] = {'count': len(expected), 'test_owned_conditions': True, 'sqlite_and_implementation_equal': True}


def test_receipt_and_outbox_independent_fk_matrix():
    owner = _fresh_physical_fixture(False)
    owner.fixed_transition(1)
    ids = owner.fixture_ids
    receipt = dict(command_id='raw-command',actor_user_id=ids['actor'],idempotency_key='raw-key',
        assignment_id=ids['assignment'],submission_id=ids['submission'],revision_id='00000000-0000-0000-0000-000000000101',
        request_digest='c'*64,response_status=201,response_body='{}',committed_at='2026-10-18T12:00:00.000000')
    results = []
    for field in ('actor_user_id','assignment_id','submission_id','revision_id'):
        sql, params = _raw_insert(None, 'br_assignment_receipts', dict(receipt, **{field:'missing-synthetic-FK'}))
        results.append(_reject_unchanged(owner, 'receipt_fk/'+field, sql, params, 'FOREIGN KEY constraint failed'))
    c = owner.connect()
    try:
        c.begin_immediate()
        c.execute(*_raw_insert(None, 'br_assignment_receipts', receipt))
        c.commit()
    finally:
        c.close()
    outbox = dict(event_id='raw-event',command_id='raw-command',recipient_user_id=ids['teacher'],notification_id=ids['notification'],
        event_type='assignment_submitted',payload='{}',delivery_state='pending',attempt_count=0,created_at='2026-10-18T12:00:00.000000')
    for field in ('command_id','recipient_user_id','notification_id'):
        sql, params = _raw_insert(None, 'br_assignment_outbox', dict(outbox, **{field:'missing-synthetic-FK'}))
        results.append(_reject_unchanged(owner, 'outbox_fk/'+field, sql, params, 'FOREIGN KEY constraint failed'))
    globals().setdefault('ACCEPTANCE', {})['receipt_outbox_fk'] = results

def test_handed_off_owner_cannot_reopen_writer():
    test_live_parent_single_use_stdin_child_readback()
    try:
        c = READY_OWNER.connect()
    except PermissionError:
        pass
    else:
        c.close()
        raise AssertionError('F7 frozen handed-off owner reopened a writer')
    try:
        BOUNDARY.fresh_readback(READY_OWNER)
    except PermissionError:
        pass
    else:
        raise AssertionError('F7 handed-off owner was replayed')
    ACCEPTANCE['f7_owner_permanently_frozen'] = True

def test_live_child_rejects_stale_or_mismatched_capabilities():
    test_live_parent_single_use_stdin_child_readback()
    controls = ACCEPTANCE['f7_live_child'].get('negative_controls', [])
    assert {c['case'] for c in controls} == {'replay_challenge','source_hash','schema_hash','file_identity','database_hash'}, 'live child capability mismatch controls missing'
    assert all(c['rejected'] for c in controls)

def test_fresh_child_cannot_write_ddl_reconnect_or_spawn():
    test_live_parent_single_use_stdin_child_readback()
    controls = ACCEPTANCE['f7_live_child'].get('read_only_controls', [])
    assert {c['case'] for c in controls} == {'ddl','dml','pragma_write','attach','other_database','file_write','other_process'}, 'fresh child read-only negative controls missing'
    assert all(c['denied'] for c in controls)

def test_fixture_has_second_notification_for_independent_unique_probe():
    owner = _fresh_physical_fixture(False)
    c = owner.connect()
    try:
        assert c.execute('SELECT count(*) FROM notifications').fetchone() == (2,), 'second synthetic notification required to isolate outbox event unique without invalid FK'
    finally:
        c.close()


def test_revision_notnull_and_check_constraint_matrix():
    owner = _fresh_physical_fixture(False)
    base = _revision_values(owner)
    results = []
    nullable = {'parent_revision_id','session_id','program_id','edition_id','rubric_id'}
    for field in base:
        if field not in nullable:
            sql, params = _raw_insert(None, 'br_assignment_revisions', dict(base, **{field:None}))
            results.append(_reject_unchanged(owner, 'revision_notnull/'+field, sql, params,
                'NOT NULL constraint failed: br_assignment_revisions.'+field))
    cases = [
        ('payload_digest','A'*64,"length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'"),
        ('payload_digest','a'*63,"length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'"),
        ('legacy_digest','g'*64,"length(legacy_digest)=64 AND legacy_digest NOT GLOB '*[^0-9a-f]*'"),
        ('legacy_digest','b'*65,"length(legacy_digest)=64 AND legacy_digest NOT GLOB '*[^0-9a-f]*'"),
        ('scope_state','verified',"scope_state IN ('explicit_scope_checked','unknown')"),
        ('program_id','synthetic','program_id IS NULL AND edition_id IS NULL AND rubric_id IS NULL'),
        ('edition_id','synthetic','program_id IS NULL AND edition_id IS NULL AND rubric_id IS NULL'),
        ('rubric_id','synthetic','program_id IS NULL AND edition_id IS NULL AND rubric_id IS NULL')]
    for field, value, check in cases:
        sql, params = _raw_insert(None, 'br_assignment_revisions', dict(base, **{field:value}))
        results.append(_reject_unchanged(owner, 'revision_check/'+field+'/'+str(len(str(value))), sql, params, 'CHECK constraint failed: '+check))
    for value in (0,-1,1.5,'not-integer'):
        sql, params = _raw_insert(None, 'br_assignment_revisions', dict(base, revision_no=value))
        results.append(_reject_unchanged(owner, 'revision_number/'+str(value), sql, params, 'lineage_insert'))
    globals().setdefault('ACCEPTANCE', {})['revision_notnull_check'] = results


def test_receipt_outbox_notnull_and_check_constraint_matrix():
    owner = _fresh_physical_fixture(False)
    owner.fixed_transition(1)
    ids = owner.fixture_ids
    receipt = dict(command_id='raw-command',actor_user_id=ids['actor'],idempotency_key='raw-key',
        assignment_id=ids['assignment'],submission_id=ids['submission'],revision_id='00000000-0000-0000-0000-000000000101',
        request_digest='c'*64,response_status=201,response_body='{}',committed_at='2026-10-18T12:00:00.000000')
    results = []
    for field in receipt:
        sql, params = _raw_insert(None, 'br_assignment_receipts', dict(receipt, **{field:None}))
        results.append(_reject_unchanged(owner, 'receipt_notnull/'+field, sql, params, 'NOT NULL constraint failed: br_assignment_receipts.'+field))
    for field, value, check in [
        ('idempotency_key','', 'length(idempotency_key) BETWEEN 1 AND 128'),
        ('idempotency_key','x'*129, 'length(idempotency_key) BETWEEN 1 AND 128'),
        ('response_status',400,'response_status IN (200,201)'),
        ('response_status',200.5,'response_status IN (200,201)'),
        ('request_digest','C'*64,"length(request_digest)=64 AND request_digest NOT GLOB '*[^0-9a-f]*'")]:
        sql, params = _raw_insert(None, 'br_assignment_receipts', dict(receipt, **{field:value}))
        results.append(_reject_unchanged(owner, 'receipt_check/'+field+'/'+str(len(str(value))), sql, params, 'CHECK constraint failed: '+check))
    c = owner.connect()
    try:
        c.begin_immediate()
        c.execute(*_raw_insert(None, 'br_assignment_receipts', receipt))
        c.commit()
    finally:
        c.close()
    outbox = dict(event_id='raw-event',command_id='raw-command',recipient_user_id=ids['teacher'],notification_id=ids['notification'],
        event_type='assignment_submitted',payload='{}',delivery_state='pending',attempt_count=0,created_at='2026-10-18T12:00:00.000000')
    for field in outbox:
        sql, params = _raw_insert(None, 'br_assignment_outbox', dict(outbox, **{field:None}))
        results.append(_reject_unchanged(owner, 'outbox_notnull/'+field, sql, params, 'NOT NULL constraint failed: br_assignment_outbox.'+field))
    for field, value, check in [
        ('event_type','other',"event_type='assignment_submitted'"),
        ('delivery_state','sent',"delivery_state='pending'"),
        *[('attempt_count',v,"typeof(attempt_count)='integer' AND attempt_count=0") for v in (-1,1,0.5,'false')]]:
        sql, params = _raw_insert(None, 'br_assignment_outbox', dict(outbox, **{field:value}))
        results.append(_reject_unchanged(owner, 'outbox_check/'+field+'/'+str(value), sql, params, 'CHECK constraint failed: '+check))
    globals().setdefault('ACCEPTANCE', {})['receipt_outbox_notnull_check'] = results


def test_final_fresh_child_readback_binds_checkpoint_snapshot():
    # Final same-live-run export, never a retained checkpoint reopen.
    test_readonly_handoff_is_bound_to_new_owner_identity()
    result = BOUNDARY.fresh_readback(READY_OWNER)
    assert result['status'] == 'READBACK_PASS'
    assert result['schema_and_all_rows_equal'] and result['database_sha256_unchanged']
    assert result['unexpected_denials'] == []
    ACCEPTANCE['final_live_child'] = result
    ACCEPTANCE['final_live_child_owner'] = str(READY_OWNER.root)

if __name__ == '__main__':
    test = globals()[sys.argv[1] if len(sys.argv) > 1 else 'test_preflight_inventory']
    test()
    print('PASS ' + test.__name__)
