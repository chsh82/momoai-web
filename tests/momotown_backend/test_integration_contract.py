"""Vertical API contracts with real blueprint/store and PK-faithful identity double."""
import json
import sqlite3
import types
from uuid import uuid4
import pytest
import test_backend as regression
from test_backend import web as legacy_web, BASE, payload, post, identify, VERSION


@pytest.fixture
def web(legacy_web, monkeypatch):
    app, client, models = legacy_web
    class Query:
        def filter_by(self, **kwargs):
            assert set(kwargs) <= {'user_id', 'student_id'}, 'Student PK is student_id, not id'
            self.kwargs = kwargs
            return self
        def all(self):
            key = self.kwargs.get('student_id') or self.kwargs.get('user_id', 'u1').replace('u', 's', 1)
            return [types.SimpleNamespace(student_id=key, name='Isolated student')]
    monkeypatch.setattr(models.Student, 'query', Query())
    return app, client, models


def assert_restore_contract(data, body, presentations):
    assert data['answers'] == body['answers'] and len(data['answers']) == 32
    assert data['form_version'] == VERSION
    assert data['copy_version'] == 'momotown-festival-v02'
    assert data['presentations'] == presentations


def test_refresh_contract_create_write_restore_and_saved_payload(web):
    app, c, _ = web
    body = payload()
    data = post(c, '/attempts', body).get_json()
    assert_restore_contract(data, body, [])
    path = '/attempts/'+data['attempt_id']
    domain = data['presented_villages'][0]
    for sections, merged in [(['study'], ['study']), (['intro'], ['intro', 'study']), (['intro'], ['intro', 'study'])]:
        saved = post(c, path+'/presentation', dict(analysis_revision=data['analysis_revision'], domain_id=domain, sections=sections)).get_json()
        expected = [dict(domain_id=domain, shown_sections=merged)]
        assert_restore_contract(saved, body, expected)
        assert c.get(BASE+path).get_json() == saved
    # Legacy scoring snapshots may lack contract fields: source answers/versions
    # must come from immutable persisted payload/columns, never inferred defaults.
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        snapshot = db.execute('SELECT snapshot FROM attempts').fetchone()[0]
        snapshot = json.loads(snapshot)
        snapshot.update(answers=['forged'], form_version='forged', copy_version='forged', presentations=[])
        db.execute('UPDATE attempts SET snapshot=?, copy_version=?', (json.dumps(snapshot), 'saved-copy-v0'))
        db.execute('INSERT INTO presentations VALUES (?,?,?,?,?)', (data['attempt_id'], str(uuid4()), domain, 'intro', 'old'))
    restored = c.get(BASE+path).get_json()
    assert restored['answers'] == body['answers']
    assert restored['form_version'] == VERSION
    assert restored['copy_version'] == 'saved-copy-v0'
    assert restored['presentations'] == expected


@pytest.mark.parametrize('operation', ['presentation', 'preference', 'create_retry'])
def test_superseded_same_student_same_form_attempt_rejects_writes(web, operation):
    app, c, _ = web
    body = payload()
    data = post(c, '/attempts', body).get_json()
    path = '/attempts/'+data['attempt_id']
    for v in data['presented_villages']:
        assert post(c, path+'/presentation', dict(analysis_revision=data['analysis_revision'], domain_id=v, sections=['intro','study'])).status_code == 200
    preference = dict(request_id=str(uuid4()), analysis_revision=data['analysis_revision'], selected_village_id=data['presented_villages'][0])
    assert post(c, path+'/preference', preference).status_code == 200
    post(c, '/attempts', payload())
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        before = [db.execute('SELECT * FROM '+table).fetchall() for table in ('attempts','presentations','preferences')]
    if operation == 'create_retry':
        response = post(c, '/attempts', body)
    elif operation == 'presentation':
        response = post(c, path+'/presentation', dict(analysis_revision=data['analysis_revision'], domain_id=data['presented_villages'][0], sections=['intro']))
    else:
        response = post(c, path+'/preference', preference)
        assert post(c, path+'/preference', dict(preference, request_id=str(uuid4()))).status_code == 409
    assert response.status_code == 409
    assert c.get(BASE+path).status_code == 409
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        after = [db.execute('SELECT * FROM '+table).fetchall() for table in ('attempts','presentations','preferences')]
    assert before == after


def test_admin_summary_uses_entire_filtered_latest_cohort_not_page_or_preview(web):
    app, c, _ = web
    # Historical completed attempt must not count once replaced by pending.
    old = post(c, '/attempts', payload()).get_json()
    post(c, '/attempts', payload())
    identify(c, uid='u2')
    complete = post(c, '/attempts', payload()).get_json()
    path = '/attempts/'+complete['attempt_id']
    for v in complete['presented_villages']:
        post(c, path+'/presentation', dict(analysis_revision=complete['analysis_revision'], domain_id=v, sections=['intro','study']))
    post(c, path+'/preference', dict(request_id=str(uuid4()), analysis_revision=complete['analysis_revision'], selected_village_id=complete['presented_villages'][1]))
    identify(c, uid='u3')
    preview = post(c, '/attempts', payload()).get_json()
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        db.execute('UPDATE attempts SET origin=? WHERE attempt_id=?', ('ADMIN_PREVIEW', preview['attempt_id']))
    identify(c, 'admin')
    data = c.get(BASE+'/feedback.json?limit=1&offset=1').get_json()
    assert len(data['rows']) == 1
    summary = data['summary']
    assert summary['attempts'] == summary['students'] == 2
    assert summary['completed'] == summary['pending'] == 1
    assert summary['selected_villages'] == {complete['presented_villages'][1]: 1}
    assert summary['selected_display_positions'] == {'2': 1}
    assert 'accuracy' not in json.dumps(summary).lower()
    # History changes rows only; summary consistently describes latest cohort.
    assert c.get(BASE+'/feedback.json?history=1&limit=1').get_json()['summary'] == summary
    filtered = c.get(BASE+'/feedback.json?status=completed').get_json()['summary']
    assert filtered['attempts'] == filtered['completed'] == 1 and filtered['pending'] == 0
    empty = c.get(BASE+'/feedback.json?student=missing').get_json()['summary']
    assert empty['attempts'] == empty['students'] == empty['completed'] == empty['pending'] == 0
    assert empty['selected_villages'] == empty['selected_display_positions'] == {}


@pytest.mark.parametrize('check', [
    regression.test_attempt_snapshot_idempotency_restore,
    regression.test_preference_seen_gate_history_unchanged_analysis,
    regression.test_csrf_strict_fields_payload_limits,
    regression.test_private_cache_headers,
    regression.test_storage_busy_io_errors_are_retryable,
    regression.test_scoring_parity_against_actual_javascript_with_ties,
    regression.test_scope_flags_on_every_attempt_api,
    regression.test_admin_completed_lookup_pagination_schema_no_reasons,
])
def test_existing_regression_checks_with_pk_faithful_fixture(web, check):
    check(web)


def test_preference_write_retry_restore_contract(web):
    _, c, _ = web
    body = payload()
    data = post(c, '/attempts', body).get_json()
    path = '/attempts/'+data['attempt_id']
    expected = []
    for v in data['presented_villages']:
        post(c, path+'/presentation', dict(analysis_revision=data['analysis_revision'], domain_id=v, sections=['intro','study']))
        expected.append(dict(domain_id=v, shown_sections=['intro','study']))
    request = dict(request_id=str(uuid4()), analysis_revision=data['analysis_revision'], selected_village_id=data['presented_villages'][0])
    saved = post(c, path+'/preference', request).get_json()
    assert_restore_contract(saved, body, expected)
    assert saved['preference']['revision'] == 1
    assert post(c, path+'/preference', request).get_json() == saved
    assert c.get(BASE+path).get_json() == saved
    assert post(c, '/attempts', body).get_json() == saved


def test_actual_student_primary_key_create_restore_lookup(web):
    _, c, models = web
    body = payload()
    response = post(c, '/attempts', body)
    assert response.status_code == 200
    data = response.get_json()
    assert c.get(BASE+'/attempts/'+data['attempt_id']).status_code == 200
    identify(c, 'admin')
    row = c.get(BASE+'/feedback.json').get_json()['rows'][0]
    assert row['student_id'] == 's1'
    assert row['student_name'] == 'Isolated student'
    assert models.Student.query.kwargs == {'student_id': 's1'}
