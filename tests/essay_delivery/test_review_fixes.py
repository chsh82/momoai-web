"""Independent-review regressions, real blueprints and disposable SQLite."""
import json
import pytest
from pathlib import Path
from conftest import kernel
from test_essay_delivery import data, web, token, service
from test_essay_delivery_security import forward


@pytest.mark.parametrize('count', [1, 2])
def test_read_only_attachment_links_download_each_json_file(web, count):
    from bs4 import BeautifulSoup
    root = Path(web.app.config['UPLOAD_FOLDER']); root.mkdir(exist_ok=True)
    paths = []
    for i in range(count):
        name = f'attachment-{i}.txt'
        (root / name).write_text(f'bytes-{i}', encoding='utf-8'); paths.append(name)
    essay = web.essay()
    essay.attachment_path = json.dumps(paths)
    essay.attachment_filename = json.dumps(paths)
    web.db.session.commit()
    forward(web); web.actor('reader')
    page = web.client.get('/essays/one/view_submission')
    links = BeautifulSoup(page.data, 'html.parser').select('a[href*="/essays/download/"]')
    assert len(links) == count
    for i, link in enumerate(links):
        response = web.client.get(link['href'])
        assert response.status_code == 200
        assert response.data == f'bytes-{i}'.encode()


@pytest.mark.parametrize('uid', ['parent', 'pupil'])
@pytest.mark.parametrize('gate', ['unfinalized', 'inactive', 'allowed', 'draft'])
def test_portal_all_result_outputs_share_release_policy(web, uid, gate):
    from app.models.essay import EssayVersion, CorrectionAttachment
    e = web.essay(); e.is_finalized = gate != 'unfinalized'
    e.status = 'draft' if gate == 'draft' else 'completed'
    if gate == 'inactive':
        web.user(uid).is_active = False
    root = Path(web.app.config['HTML_FOLDER']); root.mkdir(exist_ok=True)
    path = root / 'released.html'; path.write_text('<html>released</html>', encoding='utf-8')
    web.db.session.add(EssayVersion(essay_id='one', version_number=1, html_path=str(path), html_content='<html>released</html>'))
    web.db.session.add(CorrectionAttachment(attachment_id='result-file', essay_id='one',
        original_filename='result.html', stored_filename='result.html', file_path=str(path), file_type='pdf'))
    web.db.session.commit(); web.actor(uid)
    # Parent policy intentionally permits finalized records regardless of status;
    # student policy additionally requires reviewing/completed.
    allowed = gate == 'allowed' or (uid == 'parent' and gate == 'draft')
    for url in ['/essays/one/report-frame', '/essays/print/one', '/essays/download-pdf/one', '/api/download/released.html', '/essays/correction-attachment/result-file']:
        response = web.client.get(url)
        assert (response.status_code == 200) == allowed, (url, uid, gate, response.status_code)


def test_inactive_parent_relation_cannot_print_or_export(web):
    from app.models import ParentStudent
    from app.models.essay import EssayVersion
    e = web.essay(); e.is_finalized = True; e.status = 'completed'
    web.db.session.add(EssayVersion(essay_id='one', version_number=1, html_content='<html>private</html>'))
    ParentStudent.query.one().is_active = False
    web.db.session.commit(); web.actor('parent')
    for url in ['/essays/one/report-frame', '/essays/print/one', '/essays/download-pdf/one']:
        assert web.client.get(url).status_code == 403


@pytest.mark.parametrize('method,url,payload', [
    ('post', '/essays/one/manual-correction', {}),
    ('patch', '/essays/one/update-original-text', {'text':'legitimate edit'}),
    ('post', '/teacher/api/essay/one/assign-session', {'session_id':'session-regular'}),
    ('post', '/essays/one/reset', {}),
    ('delete', '/essays/one/delete', {}),
    ('post', '/essays/api/cancel/one', {}),
    ('post', '/essays/api/regenerate/one', {}),
    ('post', '/essays/one/finalize', {}),
    ('post', '/essays/one/start', {}),
    ('post', '/essays/new', {}),
    ('post', '/essays/quick', {}),
    ('post', '/essays/ocr/upload', {}),
    ('post', '/essays/prompt-templates', {}),
])
def test_every_essay_mutation_rejects_missing_and_forged_csrf(web, method, url, payload):
    web.actor('regular')
    for headers in ({}, {'X-CSRFToken':'forged'}):
        response = web.client.open(url, method=method.upper(), json=payload, headers=headers)
        assert response.status_code == 400, (url, response.status_code)
    assert web.essay().original_text == 'preserve original'


@pytest.mark.parametrize('kind', ['manual', 'patch', 'assign'])
def test_authorized_real_ui_token_allows_correction_and_assignment(web, kind):
    web.actor('regular')
    csrf = token(web.client.get('/essays/one/manual-correction'))
    if kind == 'manual':
        response = web.client.post('/essays/one/manual-correction', data={'csrf_token':csrf, 'correction_content':'real manual feedback'})
        assert response.status_code == 302
        from app.models.essay import EssayVersion
        assert 'real manual feedback' in EssayVersion.query.one().html_content
    elif kind == 'patch':
        response = web.client.patch('/essays/one/update-original-text', json={'text':'legitimate edit'}, headers={'X-CSRFToken':csrf})
        assert response.status_code == 200
        assert web.essay().original_text == 'legitimate edit'
    else:
        response = web.client.post('/teacher/api/essay/one/assign-session', json={'session_id':'session-regular'}, headers={'X-CSRFToken':csrf})
        assert response.status_code == 200
        assert web.essay().session_id == 'session-regular'


@pytest.fixture
def library(web):
    import app.library
    web.app.register_blueprint(app.library.library_bp, url_prefix='/library')
    web.db.create_all()
    e = web.essay(); e.is_finalized = True
    web.db.session.commit()
    return web


@pytest.mark.parametrize('uid,visible', [('stranger',False), ('regular',True), ('reader',True), ('admin',True)])
def test_library_discovery_uses_per_essay_read_scope(library, uid, visible):
    forward(library); library.actor(uid)
    response = library.client.get('/library/admin/hall-of-fame/student-essays/s')
    if uid == 'reader':  # level-4 teachers cannot enter the level-3 publishing UI
        assert response.status_code == 403
    else:
        assert response.status_code == 200
        assert bool(response.json) == visible
        if visible: assert [r['essay_id'] for r in response.json] == ['one']


@pytest.mark.parametrize('uid', ['stranger', 'regular'])
def test_library_linked_publication_requires_current_correction_authority(library, uid):
    from app.models.library import HallOfFame
    forward(library, mode='correction', teacher='makeup')
    library.actor(uid)
    response = library.client.post('/library/admin/hall-of-fame/new', data={
        'essay_id':'one', 'student_id':'s', 'title':'cannot publish', 'content':'private',
        'category':'excellent_answer', 'is_published':'1'})
    assert response.status_code == 403
    assert HallOfFame.query.count() == 0


def test_library_authorized_publication_and_existing_public_read_remain(library):
    from app.models.library import HallOfFame
    library.actor('regular')
    csrf = token(library.client.get('/essays/one/manual-correction'))
    response = library.client.post('/library/admin/hall-of-fame/new', data={
        'csrf_token':csrf, 'essay_id':'one', 'student_id':'s', 'title':'public approved',
        'content':'approved content', 'category':'general', 'is_published':'1'})
    assert response.status_code == 302
    post = HallOfFame.query.one(); assert post.essay_id == 'one'
    library.actor('stranger')
    assert library.client.get('/library/hall-of-fame/'+post.post_id).status_code == 200


def test_stale_revoke_preserves_first_audit_across_two_sessions(data):
    from datetime import datetime
    from sqlalchemy.orm import Session
    from app.models.essay import EssayTeacherGrant
    svc = service()
    svc.forward_essays(data.user('admin'), [data.essay()], data.user('reader'), mode='reference', reason='read')
    data.db.session.commit()
    stale = EssayTeacherGrant.query.one()
    first_time = datetime(2026, 5, 2, 1, 2, 3)
    with Session(data.db.engine) as other:
        fresh = other.get(EssayTeacherGrant, stale.grant_id)
        fresh.revoked_at = first_time; fresh.revoked_by = 'regular'; fresh.revoke_reason = 'FIRST audit'
        other.commit()
    svc.revoke_grant(data.user('admin'), stale, 'SECOND must not overwrite')
    data.db.session.commit(); data.db.session.refresh(stale)
    assert (stale.revoked_at, stale.revoked_by, stale.revoke_reason) == (first_time, 'regular', 'FIRST audit')


def test_stale_forward_cannot_transfer_after_other_session_started_processing(data):
    from sqlalchemy.orm import Session
    from app.models import Essay
    from app.models.essay import EssayTeacherGrant
    stale = data.essay(); assert stale.status == 'draft'
    admin = data.user('admin'); recipient = data.user('reader')
    with Session(data.db.engine) as other:
        fresh = other.get(Essay, 'one'); fresh.status = 'processing'; other.commit()
    assert stale.status == 'draft', 'must exercise stale identity map'
    with pytest.raises(ValueError, match='생성 중'):
        service().forward_essays(admin, [stale], recipient, mode='correction', reason='stale transfer')
        data.db.session.commit()
    data.db.session.rollback()
    assert EssayTeacherGrant.query.count() == 0


@pytest.mark.parametrize('order', ['startup-first', 'transfer-first'])
def test_startup_and_transfer_two_sessions_both_orders(data, order):
    from sqlalchemy.orm import Session
    from app.models import Essay, User
    svc = service()
    admin = data.user('admin'); teacher = data.user('reader'); essay = data.essay()
    with Session(data.db.engine, expire_on_commit=False) as worker:
        stale = worker.get(Essay, 'one'); actor = worker.get(User, 'regular')
        if order == 'startup-first':
            svc.begin_correction(actor, stale, session=worker); worker.commit()
            with pytest.raises(ValueError, match='생성 중'):
                svc.forward_essays(admin, [essay], teacher, mode='correction', reason='cannot transfer')
            data.db.session.rollback()
        else:
            svc.forward_essays(admin, [essay], teacher, mode='correction', reason='new owner')
            data.db.session.commit()
            with pytest.raises(PermissionError):
                svc.begin_correction(actor, stale, session=worker)
            worker.rollback()
        data.db.session.refresh(essay)
        assert essay.status == ('processing' if order == 'startup-first' else 'draft')


def test_real_start_route_rejects_duplicate_processing_without_dispatch(web, monkeypatch):
    import app.essays.routes as routes
    class ForbiddenThread:
        def __init__(self, *a, **k):
            pytest.fail('duplicate startup dispatched correction')
    monkeypatch.setattr(routes.threading, 'Thread', ForbiddenThread)
    web.essay().status = 'processing'; web.db.session.commit()
    web.actor('regular'); csrf = token(web.client.get('/essays/one/manual-correction'))
    response = web.client.post('/essays/one/start', data={'csrf_token':csrf})
    assert response.status_code == 409


def test_sqlite_shared_mutex_is_not_select_for_update_or_retry(data):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.models import Essay, User
    svc = service()
    first = data.essay(); actor = data.user('regular')
    # A second real connection has a bounded zero busy timeout. The first
    # transaction owns the mutex before attempting a startup on the second.
    with Session(data.db.engine) as other:
        stale = other.get(Essay, 'one'); other_actor = other.get(User, 'regular')
        other.execute(sa.text('PRAGMA busy_timeout=0'))
        svc.lock_essay(first.essay_id)
        with pytest.raises(sa.exc.OperationalError, match='locked'):
            svc.begin_correction(other_actor, stale, session=other)
        other.rollback()
    data.db.session.rollback()


@pytest.mark.parametrize('action', ['start', 'forward', 'revoke'])
def test_database_contention_returns_conflict_and_no_partial_write(web, action):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.models.essay import EssayTeacherGrant
    if action == 'revoke':
        forward(web, mode='correction')
        grant_id = EssayTeacherGrant.query.one().grant_id
    web.actor('admin')
    csrf = token(web.client.get('/essays/forward?essay_id=one'))
    web.db.session.execute(sa.text('PRAGMA busy_timeout=0'))
    with Session(web.db.engine) as other:
        other.execute(sa.text("UPDATE essays SET status=status WHERE essay_id='one'"))
        url = {'start':'/essays/one/start', 'forward':'/essays/forward',
            'revoke':'/essays/grants/'+(grant_id if action == 'revoke' else 'unused')+'/revoke'}[action]
        response = web.client.post(url, data={'csrf_token':csrf, 'essay_id':'one',
            'teacher_id':'makeup', 'mode':'correction', 'reason':'busy'})
        assert response.status_code == 409
        other.rollback()
    web.db.session.expire_all()
    assert web.essay().status == 'draft'


@pytest.mark.parametrize('kind,folder', [('hall-of-fame','hall_of_fame'), ('admission-info','admission_info')])
def test_library_resource_links_have_dedicated_authorized_download_not_filename_bypass(library, kind, folder):
    from bs4 import BeautifulSoup
    from app.models.library import HallOfFame, AdmissionInfo
    model = HallOfFame if kind == 'hall-of-fame' else AdmissionInfo
    root = Path(library.app.config['UPLOAD_FOLDER']); (root / folder).mkdir(parents=True, exist_ok=True)
    (root / folder / 'public.txt').write_bytes(b'authorized public resource')
    post = model(title='Public resource', content='Published with permission', category='other',
        created_by='admin', file_path=folder+'/public.txt',
        **({'is_published':True} if kind == 'hall-of-fame' else {}))
    library.db.session.add(post); library.db.session.commit()
    library.actor('stranger')
    page = library.client.get('/library/'+kind+'/'+post.post_id)
    assert page.status_code == 200
    link = BeautifulSoup(page.data, 'html.parser').find('a', string=lambda t: t and '다운로드' in t)
    assert link
    response = library.client.get(link['href'])
    assert response.status_code == 200 and response.data == b'authorized public resource'
    assert library.client.get('/api/download/'+folder+'/public.txt').status_code == 404
    if kind == 'hall-of-fame':
        post.is_published = False
    else:
        from datetime import date
        post.publish_date = date.max
    library.db.session.commit()
    assert library.client.get(link['href']).status_code == 403
    library.actor('admin')
    assert library.client.get(link['href']).status_code == 403  # manager matches existing detail policy
    library.user('admin').role = 'admin'; library.user('admin').role_level = 1
    library.db.session.commit()
    assert library.client.get(link['href']).status_code == 200
    post.file_path = '../outside.txt'; library.db.session.commit()
    (root.parent / 'outside.txt').write_bytes(b'must not leak')
    assert library.client.get(link['href']).status_code == 404
