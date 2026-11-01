"""Synthetic SQLite only; no factory side effects or real deliveries."""
import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
import importlib
import sys
from datetime import date, datetime
from types import SimpleNamespace
import pytest
from conftest import kernel


@pytest.fixture
def data(kernel):
    app, db, root = kernel
    db.create_all()
    t = db.metadata.tables
    with db.engine.begin() as c:
        for uid, role, level in [('admin','manager',2), ('regular','teacher',3),
                ('makeup','teacher',3), ('reader','teacher',4), ('pupil','student',6),
                ('parent','parent',5), ('stranger','teacher',3)]:
            c.execute(t['users'].insert().values(user_id=uid,email=uid+'@example.invalid',
                password_hash='synthetic',name=uid,role=role,role_level=level,is_active=True))
        for sid in ['s','other']:
            c.execute(t['students'].insert().values(student_id=sid,name=sid,grade='초5',
                user_id='pupil' if sid == 's' else None,teacher_id='regular'))
        c.execute(t['parent_student'].insert().values(relation_id='ps',parent_id='parent',student_id='s',is_active=True))
        for cid, teacher, kind in [('regular','regular','정규반'),('makeup','makeup','보강수업')]:
            c.execute(t['courses'].insert().values(course_id=cid,course_code=cid,course_name=cid,
                teacher_id=teacher,course_type=kind,status='active',is_terminated=False,
                start_date=date(2026,1,1),end_date=date(2026,12,31)))
            c.execute(t['course_enrollments'].insert().values(enrollment_id='e-'+cid,
                student_id='s',course_id=cid,status='active',enrolled_at=datetime(2026,1,1)))
            c.execute(t['course_sessions'].insert().values(session_id='session-'+cid,
                course_id=cid,session_number=1,session_date=date(2026,5,1),status='completed'))
        for eid in ['one','two']:
            c.execute(t['essays'].insert().values(essay_id=eid,student_id='s',user_id='regular',
                course_id='regular',original_text='preserve original',grade='초5',status='draft'))
    from app.models import User, Student, Essay
    return SimpleNamespace(app=app,db=db,root=root,t=t,
        user=lambda uid: db.session.get(User,uid),student=lambda sid='s': db.session.get(Student,sid),
        essay=lambda eid='one': db.session.get(Essay,eid))


@pytest.fixture
def web(data, monkeypatch):
    from flask_login import LoginManager
    from jinja2 import ChoiceLoader, DictLoader
    from types import ModuleType
    app = data.app
    login = LoginManager(app)
    @login.user_loader
    def load(uid):
        return data.user(uid)
    # Only outer chrome is reduced; target templates/routes are real.
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '{% block content %}{% endblock %}'}), app.jinja_loader])
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf
    app.jinja_env.filters['kst'] = lambda dt, fmt='%m/%d %H:%M': dt.strftime(fmt) if dt else ''
    app.jinja_env.filters['basename'] = lambda path: os.path.basename(path) if path else ''
    from flask_login import login_required
    @app.route('/api/download/<path:filename>')
    @login_required
    def api_download(filename):
        return service().download_output(filename)
    badge = ModuleType('app.services.badge_service')
    badge.evaluate_badges = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, badge.__name__, badge)
    push = ModuleType('app.utils.push_utils')
    deliveries = []
    push.send_push_to_user = lambda **kw: deliveries.append(kw)
    monkeypatch.setitem(sys.modules, push.__name__, push)
    for suffix, cls in [('momoai_service','MOMOAIService'),('ocr_service','OCRService'),('gemini_ocr_service','GeminiOCRService')]:
        m = ModuleType('app.essays.'+suffix)
        setattr(m, cls, lambda *a, **k: pytest.fail('external service forbidden'))
        monkeypatch.setitem(sys.modules,m.__name__,m)
    for package in ['student_portal','parent_portal','essays']:
        # Restore Python's parent-package attribute as well as sys.modules.
        # Otherwise later tests patch a stale routes module, not the registered view.
        monkeypatch.delattr(importlib.import_module('app'), package, raising=False)
        for name in list(sys.modules):
            if name in ('app.'+package, 'app.'+package+'.routes'):
                monkeypatch.delitem(sys.modules,name)
        module = importlib.import_module('app.'+package)
        bp = getattr(module, {'student_portal':'student_bp','parent_portal':'parent_bp','essays':'essays_bp'}[package])
        app.register_blueprint(bp,url_prefix='/'+{'student_portal':'student','parent_portal':'parent','essays':'essays'}[package])
    module = importlib.import_module('app.teacher')
    app.register_blueprint(module.teacher_bp,url_prefix='/teacher')
    data.db.create_all()  # Route-only model modules are now registered too.
    client = app.test_client()
    def actor(uid):
        from flask import g
        g.pop('_login_user',None)
        g.pop('csrf_token',None)
        with client.session_transaction() as s:
            s.clear(); s['_user_id']=uid; s['_fresh']=True
    data.client=client; data.actor=actor; data.deliveries=deliveries
    return data


def service():
    import app.services
    import importlib.util
    assert importlib.util.find_spec('app.services.essay_delivery'), 'explicit essay delivery service missing'
    return importlib.import_module('app.services.essay_delivery')


def test_makeup_selection_links_exact_completed_lesson_without_other_essay_access(data):
    svc = service()
    choices = svc.makeup_choices(data.student())
    assert [x.session_id for x in choices] == ['session-makeup']
    e = data.essay()
    svc.assign_submission(e, data.student(), mode='makeup', session_id='session-makeup',teacher_id='makeup')
    data.db.session.commit()
    assert (e.user_id,e.course_id,e.session_id,e.session_assigned_auto) == ('makeup','makeup','session-makeup',False)
    from app.services.essay_scope import original_access_query
    assert [r.essay_id for r in data.db.session.execute(original_access_query(data.user('makeup'),'essay'))] == ['one']
    assert data.essay('two').user_id == 'regular'


def token(response):
    from bs4 import BeautifulSoup
    field = BeautifulSoup(response.data,'html.parser').select_one('input[name=csrf_token]')
    assert field, 'real submission form must contain CSRF token'
    return field['value']


@pytest.mark.parametrize('uid,path', [('pupil','/student/essays/new'),('parent','/parent/essays/submit')])
def test_real_makeup_form_post_and_csrf(web, uid, path):
    web.actor(uid)
    page = web.client.get(path)
    assert page.status_code == 200
    from bs4 import BeautifulSoup
    first_submit=BeautifulSoup(page.data,'html.parser').select_one('button[type=submit]')
    assert first_submit.get('value') != 'makeup', 'Enter must preserve regular submission, not silently choose makeup'
    soup=BeautifulSoup(page.data,'html.parser')
    regular_select=soup.select_one('select[name=teacher_id]')
    if regular_select:
        assert not regular_select.select('option[value=makeup]'), 'makeup recipient must only use the explicit makeup control'
    else:
        assert not soup.select('input[name=teacher_id][value=makeup]')
    assert '보강 수업에 제출' in page.get_data(as_text=True)
    csrf = token(page)
    payload = dict(student_id='s',title='Makeup HTTP',content='original',essay_type='basic',
        submission_mode='makeup',makeup_session_id='session-makeup',makeup_teacher_id='makeup')
    for bad in (None,'forged'):
        p = dict(payload)
        if bad: p['csrf_token']=bad
        assert web.client.post(path,data=p).status_code == 400
    assert web.client.post(path,data=dict(payload,csrf_token=csrf)).status_code == 302
    from app.models import Essay, Notification
    e = Essay.query.filter_by(title='Makeup HTTP').one()
    assert (e.student_id,e.user_id,e.course_id,e.session_id) == ('s','makeup','makeup','session-makeup')
    assert Notification.query.filter_by(user_id='makeup').count() == 1
    assert [d['user_id'] for d in web.deliveries] == ['makeup']


def test_admin_reference_forward_is_per_essay_durable_audited_and_read_only(web):
    web.actor('admin')
    page = web.client.get('/essays/forward?essay_id=one')
    assert page.status_code == 200, 'admin forwarding form missing'
    csrf = token(page)
    from app.models import Notification
    assert Notification.query.count() == 0
    assert web.deliveries == []
    payload = dict(essay_id='one',teacher_id='reader',mode='reference',reason='보강 참고',csrf_token=csrf)
    assert web.client.post('/essays/forward',data=payload).status_code == 302
    from app.models.essay import EssayTeacherGrant
    grant = EssayTeacherGrant.query.one()
    assert (grant.essay_id,grant.teacher_id,grant.mode,grant.actor_id,grant.reason) == ('one','reader','reference','admin','보강 참고')
    assert grant.created_at and grant.revoked_at is None
    assert Notification.query.filter_by(user_id='reader',notification_type='essay_forwarded').count() == 1
    assert web.essay().user_id == 'regular'
    web.actor('reader')
    response = web.client.get('/essays/one/view_submission')
    assert response.status_code == 200
    assert web.client.get('/essays/two/view_submission').status_code != 200
    before = web.essay().original_text
    assert web.client.patch('/essays/one/update-original-text',json={'text':'forbidden'}).status_code == 403
    assert web.essay().original_text == before


def test_transfer_has_single_correction_owner_preserves_history_and_revoke_restores_original(web):
    web.actor('admin')
    csrf = token(web.client.get('/essays/forward?essay_id=one'))
    payload = dict(essay_id='one',teacher_id='makeup',mode='correction',reason='첨삭 담당 이전',csrf_token=csrf)
    assert web.client.post('/essays/forward',data=payload).status_code == 302
    from app.models.essay import EssayTeacherGrant, EssayVersion
    from app.services.essay_delivery import can_correct
    e = web.essay()
    assert e.user_id == 'regular'
    assert can_correct(web.user('makeup'),e)
    assert not can_correct(web.user('regular'),e)
    assert can_correct(web.user('regular'),web.essay('two'))
    web.actor('makeup')
    csrf = token(web.client.get('/essays/one/manual-correction'))
    assert web.client.patch('/essays/one/update-original-text',json={'text':'correction owner'}, headers={'X-CSRFToken':csrf}).status_code == 200
    web.actor('regular')
    assert web.client.patch('/essays/one/update-original-text',json={'text':'old owner'}).status_code == 403
    web.actor('admin')
    csrf = token(web.client.get('/essays/forward?essay_id=one'))
    g = EssayTeacherGrant.query.filter_by(revoked_at=None).one()
    response = web.client.post('/essays/grants/'+g.grant_id+'/revoke',data={'csrf_token':csrf,'reason':'담당 원복'})
    assert response.status_code == 302
    web.db.session.refresh(g)
    assert g.revoked_at and g.revoked_by == 'admin' and g.revoke_reason == '담당 원복'
    assert can_correct(web.user('regular'),e)
    assert not can_correct(web.user('makeup'),e)
    assert e.original_text == 'correction owner'
    web.actor('makeup')
    assert web.client.get('/essays/one/view_submission').status_code != 200


def test_management_selection_ui_posts_multiple_essay_ids(web):
    from bs4 import BeautifulSoup
    web.actor('admin')
    page = web.client.get('/essays/')
    assert page.status_code == 200
    soup = BeautifulSoup(page.data,'html.parser')
    checks = soup.select('input[type=checkbox][name=essay_id]')
    assert {x['value'] for x in checks} == {'one','two'}, 'per-essay selection controls missing'
    form = soup.select_one('form#essay-forward-selection')
    assert form and form['action'] == '/essays/forward'
    csrf = token(web.client.get('/essays/forward?essay_id=one&essay_id=two'))
    assert web.client.post('/essays/forward',data=dict(essay_id=['one','two'],teacher_id='reader',
        mode='reference',reason='두 글 참고',csrf_token=csrf)).status_code == 302
    from app.models.essay import EssayTeacherGrant
    assert {g.essay_id for g in EssayTeacherGrant.query.all()} == {'one','two'}


def test_other_teacher_cannot_unassign_or_relink_an_essay(web):
    web.actor('stranger')
    response = web.client.post('/teacher/api/essay/one/assign-session',json={'session_id':None})
    assert response.status_code == 403
    assert web.essay().course_id == 'regular'


def test_teacher_assignment_list_does_not_expand_makeup_enrollment_to_all_essays(web,monkeypatch):
    import app.teacher.routes as routes
    monkeypatch.setattr(routes,'render_template',lambda name,**context: {
        'ids':[e.essay_id for e in context.get('essays_pending',[])+context.get('essays_completed',[])]})
    web.actor('makeup')
    response=web.client.get('/teacher/assignments')
    assert response.status_code==200
    assert response.json['ids']==[], 'makeup enrollment is not student-wide essay access'
    service().assign_submission(web.essay(),web.student(),mode='makeup',session_id='session-makeup')
    web.db.session.commit()
    assert web.client.get('/teacher/assignments').json['ids']==['one']
