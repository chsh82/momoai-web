"""Run ON SERVER after release. Query-only SQLite, no factory/login mutation.
Reduced base shell: server-rendered deployed templates, NOT browser account QA.
"""
import json
from pathlib import Path
import sqlite3
import sys
import types

ROOT=Path('/home/chsh82/momoai_web')
pkg=types.ModuleType('app');pkg.__path__=[str(ROOT/'app')];sys.modules['app']=pkg
sys.path.insert(0,str(ROOT))
from flask import Flask, template_rendered
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from jinja2 import ChoiceLoader, DictLoader
from app.models import db,User,Student,CourseEnrollment
from app.admin import admin_bp

app=Flask('read-only-release-probe',template_folder=str(ROOT/'templates'))
def connect():
    c=sqlite3.connect('file:'+str(ROOT/'instance/momoai.db')+'?mode=ro',uri=True)
    c.execute('PRAGMA query_only=ON')
    return c
app.config.update(SECRET_KEY='isolated-readonly-probe-not-production',TESTING=True,SQLALCHEMY_DATABASE_URI='sqlite://',SQLALCHEMY_ENGINE_OPTIONS={'creator':connect})
db.init_app(app);lm=LoginManager(app)
@lm.user_loader
def load(uid):return db.session.get(User,uid)
app.jinja_env.globals['csrf_token']=generate_csrf
app.jinja_env.filters['kst']=lambda value,fmt='%Y-%m-%d':value.strftime(fmt) if value else ''
app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'<!doctype html>{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),app.jinja_loader])
app.register_blueprint(admin_bp,url_prefix='/admin')
result={'factory_started':False,'database_mode':'read-only + query_only','browser_login_tested':False,'render_shell':'reduced'}
with app.app_context():
    actor=User.query.filter_by(role='admin',role_level=1).first()
    assert actor
    client=app.test_client()
    with client.session_transaction() as s:s['_user_id']=actor.user_id;s['_fresh']=True
    captures=[]
    def captured(sender,template,context,**kw):captures.append(context)
    template_rendered.connect(captured,app)
    def verify_search(term,sort):
        captures.clear();r=client.get('/admin/courses',query_string={'search':term,'sort':sort})
        assert r.status_code==200
        courses=captures[-1]['courses'];flags=[c.status!='active' for c in courses]
        assert flags==sorted(flags)
        assert len({c.course_id for c in courses})==len(courses)
        return {'records':len(courses),'active':flags.count(False),'other':flags.count(True),'html_bytes':len(r.data)}
    result['text_search']={sort:verify_search('초',sort) for sort in ('newest','weekday')}
    student=Student.query.join(CourseEnrollment,CourseEnrollment.student_id==Student.student_id).first()
    assert student
    result['student_search']={sort:verify_search(student.name,sort) for sort in ('newest','weekday')}
    captures.clear();r=client.get('/admin/makeup-requests?status=pending');assert r.status_code==200
    pending=captures[-1]['requests']
    expected=sum(not item.teacher_confirmed for item in pending)
    import re
    assert len(re.findall(r'>\s*관리자 직접 승인\s*</button>',r.get_data(as_text=True)))==expected
    result['makeup_render']={'http_status':r.status_code,'pending':len(pending),'unconfirmed':expected,'direct_control_present':('관리자 직접 승인' in r.get_data(as_text=True))}
    db.session.remove();db.engine.dispose()
print(json.dumps(result,sort_keys=True))
