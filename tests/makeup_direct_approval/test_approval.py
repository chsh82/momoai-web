"""Real approval routes/Jinja over sentinel-guarded synthetic SQLite only."""
import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
import re
from datetime import date, time
import pytest
from conftest import login
def approval_payload(client):
    response = client.get('/admin/makeup-requests')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    # The page shell already has CSRF; later tests bind the actual approval form.
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return {'csrf_token': token.group(1) if token else '', 'approval_mode': 'direct', 'direct_confirmed': '1',
        'makeup_date': '2026-11-02', 'makeup_time_hour': '14', 'makeup_time_minute': '20',
        'admin_notes': 'Synthetic manager decision'}


def test_direct_admin_approval_creates_real_course_without_teacher_confirmation(makeup):
    app, db, tables, client, item = makeup
    login(client, 'master')
    payload = approval_payload(client)
    response = client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload)
    assert response.status_code == 302
    db.session.expire_all()
    assert item.status == 'approved', 'direct approval must not require teacher confirmation'
    assert item.teacher_confirmed is False
    assert item.teacher_confirmed_at is None
    assert item.admin_response_by == 'master' and item.admin_response_date is not None
    assert item.admin_notes == '[관리자 직접 승인] Synthetic manager decision'
    course = item.created_makeup_course
    assert course.start_date == date(2026, 11, 2) and course.start_time == time(14, 20)
    assert course.teacher_id == 'teacher-a'
    assert len(course.sessions) == 1 and len(course.enrollments) == 1


def counts(db, tables):
    return {name: db.session.execute(db.select(db.func.count()).select_from(tables[name])).scalar_one()
        for name in ('courses', 'course_sessions', 'course_enrollments', 'notifications', 'attendance')}


@pytest.mark.parametrize('uid', ['master', 'manager'])
def test_direct_approval_is_audited_and_sequential_replay_is_noop(makeup, uid):
    app, db, tables, client, item = makeup
    login(client, uid)
    payload = approval_payload(client)
    before_teacher = (item.teacher_confirmed, item.teacher_confirmed_at,
        item.teacher_proposed_date, item.teacher_proposed_time)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 302
    db.session.expire_all()
    assert item.status == 'approved' and item.admin_response_by == uid
    assert (item.teacher_confirmed, item.teacher_confirmed_at,
        item.teacher_proposed_date, item.teacher_proposed_time) == before_teacher
    after = counts(db, tables)
    course_id = item.created_makeup_course_id
    for _ in range(2):
        assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 302
    db.session.expire_all()
    assert item.created_makeup_course_id == course_id and counts(db, tables) == after
    assert after['notifications'] > 0
    assert '[관리자 직접 승인]' in client.get('/admin/makeup-requests').get_data(as_text=True)


@pytest.mark.parametrize('uid', ['staff', 'teacher-a', 'parent', 'pupil'])
def test_non_admin_direct_post_is_denied_without_mutation(makeup, uid):
    app, db, tables, client, item = makeup
    login(client, 'master')
    payload = approval_payload(client)
    before = counts(db, tables)
    login(client, uid)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 403
    assert counts(db, tables) == before and item.status == 'pending'


def test_anonymous_direct_post_is_denied(makeup):
    app, db, tables, client, item = makeup
    before = counts(db, tables)
    response = client.post('/admin/makeup-requests/direct-synthetic/approve', data={'approval_mode': 'direct'})
    assert response.status_code == 401
    assert counts(db, tables) == before and item.status == 'pending'


@pytest.mark.parametrize('mode', ['normal', 'direct'])
@pytest.mark.parametrize('token', [None, 'arbitrary-invalid-token'])
def test_missing_or_invalid_csrf_is_rejected_before_mutation(makeup, mode, token):
    app, db, tables, client, item = makeup
    login(client, 'master')
    payload = approval_payload(client)
    payload['approval_mode'] = mode
    if token is None:
        payload.pop('csrf_token')
    else:
        payload['csrf_token'] = token
    before = counts(db, tables)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 400
    assert counts(db, tables) == before and item.status == 'pending'


@pytest.mark.parametrize('field,value', [
    ('direct_confirmed', ''), ('direct_confirmed', 'true'),
    ('makeup_date', ''), ('makeup_date', 'not-a-date'), ('makeup_date', '2026-02-30'),
    ('makeup_time_hour', ''), ('makeup_time_hour', '24'), ('makeup_time_hour', '-1'),
    ('makeup_time_hour', 'foo'), ('makeup_time_minute', ''),
    ('makeup_time_minute', '60'), ('makeup_time_minute', '-1'),
])
def test_direct_invalid_schedule_or_ack_is_noop(makeup, field, value):
    app, db, tables, client, item = makeup
    login(client, 'manager')
    payload = approval_payload(client)
    payload[field] = value
    before = counts(db, tables)
    response = client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload)
    assert response.status_code == 302
    db.session.expire_all()
    assert counts(db, tables) == before and item.status == 'pending'
    assert item.admin_response_by is None and item.admin_response_date is None
    assert item.teacher_confirmed is False


def test_unknown_mode_and_nonexistent_request(makeup):
    app, db, tables, client, item = makeup
    login(client, 'master')
    payload = approval_payload(client)
    before = counts(db, tables)
    payload['approval_mode'] = 'force'
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 400
    payload['approval_mode'] = 'direct'
    assert client.post('/admin/makeup-requests/not-found/approve', data=payload).status_code == 404
    assert counts(db, tables) == before


@pytest.mark.parametrize('confirmed', [False, True])
def test_normal_approval_preserves_teacher_gate_and_original_time_default(makeup, confirmed):
    app, db, tables, client, item = makeup
    login(client, 'master')
    item.teacher_confirmed = confirmed
    db.session.commit()
    payload = approval_payload(client)
    payload.pop('approval_mode')  # Existing forms default to normal.
    payload.pop('direct_confirmed')
    payload['makeup_time_hour'] = ''
    payload['makeup_time_minute'] = ''
    before = counts(db, tables)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 302
    db.session.expire_all()
    assert item.status == ('approved' if confirmed else 'pending')
    if confirmed:
        assert item.created_makeup_course.start_time == time(10)
        assert item.admin_notes == 'Synthetic manager decision'
    else:
        assert counts(db, tables) == before


@pytest.mark.parametrize('status', ['approved', 'rejected'])
def test_closed_request_cannot_be_direct_approved(makeup, status):
    app, db, tables, client, item = makeup
    login(client, 'master')
    item.status = status
    db.session.commit()
    payload = approval_payload(client)
    before = counts(db, tables)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 302
    db.session.expire_all()
    assert counts(db, tables) == before and item.status == status


def test_linked_pending_request_cannot_create_duplicate(makeup):
    app, db, tables, client, item = makeup
    login(client, 'master')
    item.created_makeup_course_id = 'c-b'
    db.session.commit()
    payload = approval_payload(client)
    before = counts(db, tables)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve', data=payload).status_code == 302
    assert counts(db, tables) == before and item.created_makeup_course_id == 'c-b'


def test_rendered_actual_approval_form_has_csrf_direct_and_existing_actions(makeup):
    app, db, tables, client, item = makeup
    login(client, 'master')
    html = client.get('/admin/makeup-requests').get_data(as_text=True)
    form = html.split('<form id="approveForm"', 1)[1].split('</form>', 1)[0]
    assert re.search(r'name="csrf_token"\s+value="[^"]+"', form)
    assert 'name="approval_mode"' in form and 'name="direct_confirmed"' in form
    assert '관리자 직접 승인' in html and '강사에게 물어보기' in html
    assert 'id="proposeToParentButton"' in form
    item.teacher_confirmed = True
    db.session.commit()
    confirmed = client.get('/admin/makeup-requests').get_data(as_text=True)
    assert '승인 (강사 확인 필요)' not in confirmed
    assert 'showApproveModal' in confirmed
