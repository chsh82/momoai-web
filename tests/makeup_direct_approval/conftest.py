"""Standalone synthetic harness; never call the operational app factory."""
import sys
import types
import socket
import tempfile
import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1', 'Use explicit synthetic test opt-in'
from pathlib import Path
from datetime import date, time
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# Avoid config/.env import and factory startup while importing actual models/blueprints.
pkg = types.ModuleType('app')
pkg.__path__ = [str(ROOT / 'app')]
sys.modules['app'] = pkg
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from jinja2 import ChoiceLoader, DictLoader
from app.models import db, User, Student, Course, ParentStudent
from app.models.makeup_request import MakeupClassRequest

@pytest.fixture
def makeup(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: (_ for _ in ()).throw(AssertionError('external network forbidden')))
    scratch = Path(os.environ['TMPDIR'])
    with tempfile.TemporaryDirectory(prefix='makeup-direct-', dir=scratch) as tmp:
        app = Flask('synthetic-makeup', template_folder=str(ROOT/'templates'), static_folder=str(ROOT/'static'))
        app.config.update(SECRET_KEY='synthetic-only', TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///'+str(Path(tmp)/'synthetic.db'), SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app)
        lm = LoginManager(app)
        @lm.user_loader
        def load(uid): return db.session.get(User, uid)
        app.jinja_env.globals['csrf_token'] = generate_csrf
        app.jinja_env.filters['kst'] = lambda value, fmt='%Y-%m-%d': value.strftime(fmt) if value else ''
        app.jinja_loader = ChoiceLoader([DictLoader({'base.html':'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/css/tailwind.min.css"></head><body><p>합성 로컬 미리보기 (축소 셸)</p>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>'}), app.jinja_loader])
        from app.admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')
        from app.chat_widget import chat_widget_bp
        app.register_blueprint(chat_widget_bp)
        app.add_url_rule('/parent', endpoint='parent.index', view_func=lambda:'synthetic parent')
        from app.utils import push_utils
        monkeypatch.setattr(push_utils, 'send_push_to_user', lambda **kw: None)
        with app.app_context():
            db.create_all()
            for uid,role,level in [('master','admin',1),('manager','admin',2),('staff','admin',3),('teacher-a','teacher',3),('parent','parent',4),('pupil','student',5)]:
                db.session.add(User(user_id=uid,email=uid+'@synthetic.invalid',password_hash='not-a-login',name='Synthetic '+uid,role=role,role_level=level))
            db.session.add(Student(student_id='s',teacher_id='teacher-a',user_id='pupil',name="Synthetic O'Neil",grade='초4'))
            db.session.add(Course(course_id='c-a',course_code='SYNTHETIC',course_name='Synthetic course',teacher_id='teacher-a',course_type='정규반',grade='초4',weekday=0,start_time=time(10),end_time=time(12),start_date=date(2026,1,1),end_date=date(2026,12,31)))
            db.session.add(ParentStudent(parent_id='parent',student_id='s',is_active=True))
            db.session.add(MakeupClassRequest(request_id='direct-synthetic',student_id='s',requested_course_id='c-a',requested_by='parent',status='pending',teacher_confirmed=False,reason='Synthetic only'))
            db.session.commit()
        client=app.test_client()
        # Actual table objects expose all real schema; no invented model doubles.
        with app.app_context():
            yield app,db,db.metadata.tables,client,db.session.get(MakeupClassRequest,'direct-synthetic')
            db.session.remove()
            db.engine.dispose()

def login(client, uid='master'):
    from flask import g
    g.pop('_login_user',None)
    with client.session_transaction() as s:
        s['_user_id']=uid
        s['_fresh']=True
