"""Factory-free, file-backed synthetic accounts; real feature blueprint/store."""
import sys
import types
from pathlib import Path
from threading import Thread
import pytest
from flask import Flask, redirect, render_template_string
from flask_login import LoginManager, UserMixin, login_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
BASE = '/student/interest-quest'
package = types.ModuleType('app')
package.__path__ = [str(ROOT/'app')]
sys.modules['app'] = package
models = types.ModuleType('app.models')
sys.modules['app.models'] = models
db = SQLAlchemy()
class User(UserMixin, db.Model):
    user_id = db.Column(db.String, primary_key=True)
    role = db.Column(db.String)
    name = db.Column(db.String)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    def get_id(self): return self.user_id
    @property
    def is_authenticated(self): return True
class Student(db.Model):
    student_id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.String)
    name = db.Column(db.String)
    status = db.Column(db.String, default='active')
class ParentStudent(db.Model):
    relation_id = db.Column(db.String, primary_key=True)
    parent_id = db.Column(db.String)
    student_id = db.Column(db.String)
    is_active = db.Column(db.Boolean, default=True)
    permission_level = db.Column(db.String, default='view_only')
models.User, models.Student, models.ParentStudent = User, Student, ParentStudent
from app.interest_quest import interest_quest_bp
from app.interest_quest import backend, store

@pytest.fixture
def web(tmp_path):
    app = Flask('result-library-local', template_folder=str(ROOT/'templates'), static_folder=str(ROOT/'static'))
    app.config.update(TESTING=True, SECRET_KEY='synthetic-only', MEMBER_INTEREST_QUEST_ENABLED=True,
                      STUDENT_INTEREST_QUEST_ENABLED=True, MOMOTOWN_FEEDBACK_DB=str(tmp_path/'feedback.db'),
                      SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'accounts.db'))
    db.init_app(app)
    manager = LoginManager(app)
    manager.user_loader(lambda uid: db.session.get(User, uid))
    app.add_url_rule('/login', 'auth.login', lambda:('login required',401))
    @app.route('/__fixture_login/<uid>')
    def fixture_login(uid):
        login_user(db.session.get(User, uid), force=True)
        return redirect(BASE+'/')
    @app.route('/host/<name>')
    def host(name):
        return render_template_string('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/static/css/interest-reports.css"><body><header class="report-header">LOCAL SYNTHETIC PREVIEW · reduced host shell</header><main class="report-main"><h1>원래 페이지 {{ name }}</h1><label>검색 조건 <input id="filter" value="유지할 조건"></label><div style="height:650px"></div><a id="entry" href="{{ url_for('interest_quest.index') }}">전공마을 탐험</a><a id="child-entry" href="{{ url_for('interest_quest.children_page') }}" data-interest-layer>자녀 탐색 결과</a><div style="height:900px"></div></main>{% include 'interest_quest/layer.html' ignore missing %}</body></html>''',name=name)
    app.register_blueprint(interest_quest_bp, url_prefix=BASE)
    with app.app_context():
        db.create_all()
        db.session.add_all([User(user_id=u, role=r, name=u) for u,r in [('u1','student'),('u2','student'),('p1','parent'),('p2','parent'),('admin','admin'),('teacher','teacher')]])
        db.session.add_all([Student(student_id='s1',user_id='u1',name='격리 학생 <태그>'),Student(student_id='s2',user_id='u2',name='다른 학생')])
        db.session.add(ParentStudent(relation_id='r1',parent_id='p1',student_id='s1'))
        db.session.commit()
    client=app.test_client()
    client.get('/__fixture_login/u1')
    yield app,client
    with app.app_context(): db.session.remove(); db.engine.dispose()

@pytest.fixture
def live(web):
    app,client=web
    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    yield app,client,f'http://127.0.0.1:{server.server_port}'
    server.shutdown(); server.server_close(); thread.join(5)

def create(app, variant=0):
    from uuid import uuid4
    with app.app_context():
        answers=[q['options'][variant%len(q['options'])]['id'] for q in backend.canonical_form()['items']]
        body=dict(request_id=str(uuid4()),form_version=backend.FORM_VERSION,answers=answers)
        return store.create('s1',body,backend.analyze(answers))
