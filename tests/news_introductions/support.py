"""Isolated real NEWS routes; never imports the operational application factory."""
import importlib.util
import os
from pathlib import Path
import secrets
import sys
import tempfile
import types

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path(os.environ['COMMUNITY_TEST_SCRATCH']).resolve(strict=True)
ALLOWED = Path('C:/Users/aproa/AppData/Local/hermes/profiles/davinci/cache/scratch').resolve()
assert SCRATCH.is_relative_to(ALLOWED)
ROOT = Path(tempfile.mkdtemp(prefix='news-intro-', dir=SCRATCH))
pkg = types.ModuleType('app')
pkg.__path__ = [str(REPO / 'app')]
sys.modules['app'] = pkg
sys.path.insert(0, str(REPO))
from flask import Flask, Blueprint, g
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from jinja2 import ChoiceLoader, DictLoader
from sqlalchemy import event
from app.models import db, User
from app.models.site_content import SiteContent
news = types.ModuleType('app.news')
news.__path__ = [str(REPO / 'app/news')]
news.news_bp = Blueprint('news', 'app.news')
sys.modules['app.news'] = news
spec = importlib.util.spec_from_file_location('app.news.routes', REPO / 'app/news/routes.py')
routes = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = routes
spec.loader.exec_module(routes)

SHELL = '''<!doctype html><html lang="ko"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{% block title %}{% endblock %}</title><link rel="stylesheet" href="/static/css/tailwind.min.css"><link rel="stylesheet" href="/static/css/style.min.css"></head><body><header style="background:#fff3cd;padding:10px">LOCAL SYNTHETIC QA · 최소 대체 shell · 운영 인증 아님</header><main style="padding:16px">{% block content %}{% endblock %}</main>{% block extra_js %}{% endblock %}</body></html>'''

def build_app():
    app = Flask(__name__, template_folder=str(REPO / 'templates'), static_folder=str(REPO / 'static'))
    app.config.update(TESTING=True, SECRET_KEY=secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI='sqlite:///' + (ROOT / 'synthetic.sqlite').as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False, WTF_CSRF_ENABLED=True)
    db.init_app(app)
    with app.app_context():
        assert Path(db.engine.url.database).resolve() == ROOT / 'synthetic.sqlite'
        @event.listens_for(db.engine, 'before_cursor_execute')
        def guard(connection, cursor, statement, parameters, context, executemany):
            assert Path(connection.engine.url.database).resolve() == ROOT / 'synthetic.sqlite'
            assert not statement.lstrip().upper().startswith(('ATTACH', 'DETACH'))
    lm = LoginManager(app)
    lm.login_view = 'auth.login'
    @lm.user_loader
    def load(uid):
        return db.session.get(User, uid)
    @app.before_request
    def reset_cache():
        g.pop('_login_user', None)
        g.pop('csrf_token', None)
    app.add_url_rule('/auth/login', 'auth.login', lambda: ('LOCAL synthetic login destination', 200))
    CSRFProtect(app)
    app.register_blueprint(news.news_bp, url_prefix='/news')
    from app.community import community_bp
    app.register_blueprint(community_bp, url_prefix='/community')
    app.jinja_env.globals['csrf_token'] = generate_csrf
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': SHELL}), app.jinja_loader])
    with app.app_context():
        db.create_all()
        for role in ('admin', 'parent', 'student', 'teacher', 'manager'):
            db.session.add(User(user_id='fixture-' + role, email=role+'@example.invalid',
                password_hash='synthetic-unusable-password', name='합성 '+role, role=role, is_active=True))
        for key in ('course_intro', 'about_momo'):
            db.session.add(SiteContent(key=key, title='Stored <title>', content='Stored <script>alert(1)</script>'))
        db.session.commit()
    return app

def client(app, role='parent'):
    c = app.test_client()
    if role:
        with c.session_transaction() as session:
            session['_user_id'] = 'fixture-' + role
            session['_fresh'] = True
    return c
