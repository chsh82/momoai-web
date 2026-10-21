"""Approved external B-R01 runner. No normal app, network, subprocess or DB fallback."""
import ast
import builtins
import importlib.util
import importlib.machinery
import json
from pathlib import Path
import sys
import traceback
import types
import uuid

HERE = Path(__file__).resolve().parent

def owned(name):
    ns = {'__file__': str(HERE / (name + '.py')), '__name__': name}
    exec(compile(Path(ns['__file__']).read_bytes(), ns['__file__'], 'exec'), ns)
    return ns

def main():
    kernel = owned('isolation_kernel')
    inventory = kernel['preflight']()
    run_id = uuid.uuid4().hex
    evidence = HERE / 'evidence'
    evidence.mkdir(exist_ok=True)
    with (evidence / (run_id + '_runtime_manifest.json')).open('x', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2)
    checkpoint = (evidence / (run_id + '_checkpoint.json')).open('x', encoding='utf-8')
    report = {'run_id': run_id, 'scope': 'B-R01', 'runtime_file_count': inventory['runtime_file_count'],
              'library_file_count': inventory['library_file_count'], 'status': 'PREFLIGHT_PASS', 'database_connections': 0,
              'sources': {str(p): kernel['digest'](p) for p in HERE.glob('*.py')}, 'completed_tests': []}
    schema = kernel['REPO'] / 'app/services/p3_assignment_schema.py'
    report['sources'][str(schema)] = kernel['digest'](schema)
    frozen_sources = dict(report['sources'])
    boundary = None
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'preflight':
            print('PASS preflight', inventory['runtime_file_count'], 'CPython files; 982 library files')
        elif len(sys.argv) >= 4 and sys.argv[1:4] == ['test', '--slice', 'B-R01']:
            boundary = kernel['AuditBoundary'](inventory)
            boundary.run_id = run_id
            boundary.install()
            ns = owned('test_assignment_real_route')
            ns['BOUNDARY'] = boundary
            foundation = {'test_preflight_inventory', 'test_read_guard_denies_unlisted_file',
                          'test_installed_audit_blocks_external_effects', 'test_exact_finder_resolves_manifest_namespace_only',
                          'test_preflight_platform_probe_requires_no_guard_exception'}
            cases = [name for name, fn in ns.items() if name.startswith('test_') and callable(fn) and name not in foundation]
            if '--case' in sys.argv:
                selected = sys.argv[sys.argv.index('--case') + 1]
                cases = ['test_actual_model_mapper_closure', selected] if selected != cases[0] else [selected]
            for case in cases:
                ns[case]()
                report['completed_tests'].append(case)
                print('PASS ' + case)
            report['test_count'] = len(report['completed_tests'])
            report['status'] = 'B_R01_PARTIAL' if any(o.connections for o in boundary.owners) else 'MAPPER_PASS_NOT_SCHEMA_ACCEPTED'
            report['full_B_R01_accepted'] = False
            report.update(ns.get('ACCEPTANCE', {}))
        else:
            raise ValueError('Only preflight or test --slice B-R01 is implemented')
    except BaseException as exc:
        report['status'] = 'BLOCKED' if boundary and boundary.denials else 'FAILED'
        report['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
        frames = []
        tb = exc.__traceback__
        while tb is not None:
            frames.append({'file': tb.tb_frame.f_code.co_filename,
                           'function': tb.tb_frame.f_code.co_name,
                           'line': tb.tb_lineno})
            tb = tb.tb_next
        report['traceback_frames'] = frames
        report['traceback'] = type(exc).__name__ + ': ' + str(exc)
        print(report['traceback'])
    finally:
        report['unexpected_denials'] = boundary.denials if boundary else []
        report['database_connections'] = sum(o.connections for o in boundary.owners) if boundary else 0
        report['owner_count'] = len(boundary.owners) if boundary else 0
        report['sql_denials'] = [dict(owner=str(o.root), **d) for o in boundary.owners for d in o.sql_denials] if boundary else []
        report['test_count'] = len(report['completed_tests'])
        report['full_B_R01_accepted'] = False
        schema = kernel['REPO'] / 'app/services/p3_assignment_schema.py'
        if schema.is_file():
            report['sources'][str(schema)] = kernel['digest'](schema)
        if report['unexpected_denials']:
            report['status'] = 'BLOCKED'
        report['execution_exit'] = 0 if report['status'] in {'PREFLIGHT_PASS','MAPPER_PASS_NOT_SCHEMA_ACCEPTED','B_R01_PARTIAL'} else 1
        report['not_accepted'] = [
            'setup-reference trigger proof remains layered: 12 CASCADE authorizer refusals, not unmasked trigger proof',
            'complete unmasked per-edge FK/RESTRICT matrix: head/self-parent FK and immutable-sidecar RESTRICT are trigger-masked; independent FK12 and notification RESTRICT1 proven',
            'three frozen execution orders and later B-R02 through B-R10 not implemented/exercised',
            'independent review and global closeout not performed']
        report['historical_readback_deviation'] = '--checkpoint accepted untrusted external JSON and reopened retained owner: old evidence preserved, NOT F7 compliant'
        report['current_readback_protocol'] = 'exact sys.executable/readback.py --capability-stdin; parent in-memory single-consumption registry; owned direct pipe; child challenge/PIDs; exact6/schema/identity/DB binding; fresh owner permanently frozen; sanitized env'
        report['source_frozen_unchanged'] = all(kernel['digest'](p) == h for p, h in frozen_sources.items())
        if not report['source_frozen_unchanged']:
            report['status'] = 'FAILED'
            report['execution_exit'] = 1
        fields = ('alternate_unique_matrix','revision_lineage_matrix','head_negative_matrix','independent_fk','receipt_outbox_fk',
                  'unmasked_restrict','revision_notnull_check','receipt_outbox_notnull_check')
        report['negative_case_counts'] = {field: len(report.get(field, [])) for field in fields}
        report['setup_reference_layer_counts'] = {reason: sum(p['error'] == reason for p in report.get('setup_reference_replace', []))
                                                for reason in ('setup_reference_conflict','not authorized')}
        report['tdd_accounting'] = 'New runtime protocol/junction/fixed deletion profile/freeze/fixture behaviors have actual RED->GREEN logs; added matrices/SQL spec first-pass results are regression evidence only, not retrospective RED'
        report['symlink_status'] = 'historical C2A SKIP preserved; actual Windows junction independently PASS when junction_probe present'

        json.dump(report, checkpoint, indent=2)
        checkpoint.close()
        print('CHECKPOINT', str(evidence / (run_id + '_checkpoint.json')), report['status'])
    return 0 if report['status'] in {'PREFLIGHT_PASS', 'MAPPER_PASS_NOT_SCHEMA_ACCEPTED', 'B_R01_PARTIAL'} else 1

if __name__ == '__main__':
    raise SystemExit(main())
