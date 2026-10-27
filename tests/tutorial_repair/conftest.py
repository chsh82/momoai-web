"""Isolated real tutorial blueprint/models; no production factory, config or DB.

Run this directory in its own pytest process: app package replacements are deliberate.
Only the global shell and identity tables are reduced; tutorial routes/templates/JS are real.
"""
import importlib
import os
from pathlib import Path
import sys
import types

import pytest
from flask import Flask, url_for, g
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from jinja2 import ChoiceLoader, DictLoader

ROOT = Path(__file__).resolve().parents[2]
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
package = types.ModuleType('app')
package.__path__ = [str(ROOT / 'app')]
sys.modules['app'] = package
db = SQLAlchemy()
models = types.ModuleType('app.models')
models.db = db
models.__path__ = [str(ROOT / 'app/models')]
sys.modules['app.models'] = models


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.String(36), primary_key=True)
    role = db.Column(db.String(20))

    def get_id(self):
        return self.user_id


class Student(db.Model):
    __tablename__ = 'students'
    student_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'))


student_module = types.ModuleType('app.models.student')
student_module.Student = Student
sys.modules['app.models.student'] = student_module
from app.tutorial import tutorial_bp, content
from app.tutorial.models import TutorialProgress, TutorialCourseReward
from app.models.mileage import PointEvent


@pytest.fixture
def tutorial(monkeypatch):
    app = Flask('tutorial-test', static_folder=str(ROOT / 'static'))
    app.config.update(TESTING=True, SECRET_KEY='synthetic-only', SQLALCHEMY_DATABASE_URI='sqlite://')
    db.init_app(app)
    app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '''<!doctype html><html><head>
{% block extra_head %}{% endblock %}</head><body>{% block content %}{% endblock %}
{% block scripts %}{% endblock %}</body></html>'''}), app.jinja_loader])
    app.jinja_env.globals['static_v'] = lambda f: url_for('static', filename=f)
    manager = LoginManager(app)
    manager.user_loader(lambda uid: db.session.get(User, uid))
    @app.before_request
    def clear_test_identity_cache():
        # The fixture keeps an outer DB context for assertions; production requests
        # have separate g objects. Do not leak flask-login's g cache across clients.
        g.pop('_login_user', None)

    def course(track, code):
        count = 9 if track == 'mid' and code == 'course2' else 4
        return {'title': 'Synthetic tutorial', 'lede': 'Synthetic', 'lessons': [
            {'id': f'{track}-{code}-l{i}', 'title': f'Synthetic lesson {i}',
             'cards': [{'no':'1', 'title':'Synthetic card', 'say':'Read this'}],
             'questions': [{'id':f'q{i}', 'type':'choice', 'q':'Pick one',
                            'opts':[{'text':'Yes'},{'text':'No'}], 'a':0,
                            'why':'Synthetic reason', 'ruleNo':'1', 'ruleName':'Synthetic rule'}]}
            for i in range(1, count + 1)]}
    monkeypatch.setattr(content, 'get_course', course)
    with app.app_context():
        db.create_all()
        db.session.add_all([User(user_id='pupil',role='student'), User(user_id='other',role='student'),
                            User(user_id='admin',role='admin'), User(user_id='parent',role='parent'),
                            User(user_id='teacher',role='teacher')])
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as s:
            s['_user_id'] = 'pupil'
            s['_fresh'] = True
        yield app, db, client, TutorialProgress
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def complete(client, track='elem', index=1, course='course1', **extra):
    return client.post('/tutorial/api/complete', json=dict(
        track=track, course=course, lesson_id=f'{track}-{course}-l{index}', score=1, total=1, **extra))
