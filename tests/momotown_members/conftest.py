"""Factory-free real blueprint / synthetic identity / loopback only."""
import sys, types
from pathlib import Path
from threading import Thread
from collections import defaultdict
import pytest
from flask import Flask, session, request, abort, redirect, render_template
from flask_login import LoginManager, UserMixin, login_user
from flask_wtf.csrf import generate_csrf
from werkzeug.serving import make_server
ROOT=Path(__file__).resolve().parents[2]
BASE='/student/interest-quest'
ROLES=('student','parent','teacher','staff','manager','admin','master_admin')
if 'app' not in sys.modules:
    package=types.ModuleType('app');package.__path__=[str(ROOT/'app')];sys.modules['app']=package
from app.interest_quest import interest_quest_bp
from app.interest_mid import interest_mid_bp
class Identity(UserMixin):
    def __init__(self,uid):
        self.id=self.user_id=uid;self.role=uid.split(':')[0];self.active=not uid.endswith(':inactive')
        self.name='격리 계정';self.email='fixture@example.invalid'
        self.role_level={'master_admin':1,'admin':1,'manager':2,'staff':3,'teacher':3,'parent':4,'student':5}.get(self.role,9)
        self.is_admin=self.role=='admin';self.is_master_admin=self.role_level==1;self.is_teacher=self.role=='teacher'
    @property
    def is_authenticated(self):return True  # Actual User overrides UserMixin even when inactive.
    @property
    def is_active(self):return self.active
    def has_permission_level(self,n):return self.role_level<=n
@pytest.fixture
def web(tmp_path,monkeypatch):
    students=[types.SimpleNamespace(student_id='s1',user_id='student',name='격리 학생'),types.SimpleNamespace(student_id='s2',user_id='student:other',name='다른 학생')]
    queries=[]
    class Query:
        def __init__(self,filters=None):self.filters=filters or {}
        def filter_by(self,**kwargs):
            assert set(kwargs)<={'user_id','student_id'};queries.append(kwargs);return Query(kwargs)
        def all(self):return [s for s in students if all(getattr(s,k)==v for k,v in self.filters.items())]
    models=types.ModuleType('app.models');models.Student=type('Student',(),{'query':Query()});monkeypatch.setitem(sys.modules,'app.models',models)
    app=Flask('member-isolation',template_folder=str(ROOT/'templates'))
    from jinja2 import ChoiceLoader, DictLoader
    # Unrelated live-only badge/widget includes have no exploration links.
    app.jinja_loader=ChoiceLoader([DictLoader({'news/publishing/unread_badge.html':'','partials/momo_agent_widget.html':''}),app.jinja_loader])
    app.config.update(TESTING=True,SECRET_KEY='member-fixture-only',STUDENT_INTEREST_QUEST_ENABLED=False,STUDENT_INTEREST_MID_ENABLED=False,MEMBER_INTEREST_QUEST_ENABLED=True,MOMOTOWN_FEEDBACK_DB=str(tmp_path/'private.sqlite3'))
    manager=LoginManager(app);manager.login_view='auth.login';manager.user_loader(lambda uid:Identity(uid))
    app.add_url_rule('/login','auth.login',lambda:('login required',401))
    app.register_blueprint(interest_quest_bp,url_prefix=BASE);app.register_blueprint(interest_mid_bp,url_prefix='/student/interest-mid')
    @app.route('/__login/<uid>')
    def fixture_login(uid):
        if request.remote_addr!='127.0.0.1' or uid.split(':')[0] not in ROLES:abort(403)
        session.clear();login_user(Identity(uid),force=True);return redirect(BASE+'/')
    app.jinja_env.globals['now']=lambda:None
    app.jinja_env.filters['kst']=lambda value,*args:'격리 날짜'
    app.jinja_env.globals.update(static_v=lambda name:'/static/'+name,csrf_token=generate_csrf,url_for=lambda ep,**kw:BASE+'/' if ep=='interest_quest.index' else '/student/interest-mid/' if ep=='interest_mid.index' else '/fixture/'+ep)
    @app.route('/__sidebar')
    def sidebar():
        return render_template('base.html',unread_counts=defaultdict(int),p3_reports_navigation=False,news_learning_menu=False)
    writes=[]
    @app.before_request
    def record():
        if request.method=='POST' and request.path.startswith(BASE):writes.append(request.path)
    yield dict(app=app,client=app.test_client(),db=Path(app.config['MOMOTOWN_FEEDBACK_DB']),queries=queries,students=students,writes=writes)
@pytest.fixture
def live(web):
    http=make_server('127.0.0.1',0,web['app'],threaded=True);thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    yield dict(web,origin=f'http://127.0.0.1:{http.server_port}')
    http.shutdown();http.server_close();thread.join(timeout=5)
def identify(c,role,active=True):
    with c.session_transaction() as s:
        s.clear()
        if role:s['_user_id']=role+('' if active else ':inactive')
