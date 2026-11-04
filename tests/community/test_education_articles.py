"""Scoped real community routes/forms/models; synthetic DB, no app bootstrap.
Run in a fresh process: python tests/community/test_education_articles.py
Unrelated base navigation is replaced with a minimal test shell, explicitly.
No production authentication/session forging or production database access.
"""
import ast
import io
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

REPO = Path(os.environ.get('COMMUNITY_TEST_REPO', Path(__file__).resolve().parents[2])).resolve()
SCRATCH = Path(os.environ['COMMUNITY_TEST_SCRATCH']).resolve(strict=True)
ROOT = Path(tempfile.mkdtemp(prefix='education-community-', dir=SCRATCH))
# Do not execute app/__init__.py or config.py (dotenv, scheduler, real DB).
pkg = types.ModuleType('app')
pkg.__path__ = [str(REPO / 'app')]
sys.modules['app'] = pkg
sys.path.insert(0, str(REPO))
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from jinja2 import ChoiceLoader, DictLoader
from bs4 import BeautifulSoup
from app.models import db, User, Post, Comment, PostLike, Tag, PostTag, Bookmark, PostFile, PostImage
OVERLAY = Path(os.environ.get('COMMUNITY_TEST_OVERLAY', REPO))
import importlib.util
spec = importlib.util.spec_from_file_location('app.community', REPO / 'app/community/__init__.py',
    submodule_search_locations=[str(OVERLAY / 'app/community'), str(REPO / 'app/community')])
community_module = importlib.util.module_from_spec(spec)
sys.modules['app.community'] = community_module
spec.loader.exec_module(community_module)
community_bp = community_module.community_bp
from sqlalchemy import event


def build_app():
    app = Flask(__name__, template_folder=str(REPO / 'templates'), static_folder=str(REPO / 'static'))
    from jinja2 import FileSystemLoader
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(OVERLAY / 'templates')), app.jinja_loader])
    app.config.update(TESTING=True, SECRET_KEY=secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI='sqlite:///' + (ROOT / 'synthetic.sqlite').as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False, WTF_CSRF_ENABLED=True,
        POST_FILES_FOLDER=str(ROOT / 'files'), POST_IMAGES_FOLDER=str(ROOT / 'images'),
        MAIL_SUPPRESS_SEND=True)
    for name in ('files', 'images'):
        (ROOT / name).mkdir()
    db.init_app(app)
    with app.app_context():
        assert Path(db.engine.url.database).resolve() == ROOT / 'synthetic.sqlite'
        @event.listens_for(db.engine, 'before_cursor_execute')
        def guard(connection, cursor, statement, parameters, context, executemany):
            assert Path(connection.engine.url.database).resolve() == ROOT / 'synthetic.sqlite'
            assert not statement.lstrip().upper().startswith(('ATTACH', 'DETACH'))
    lm = LoginManager(app)
    lm.login_view = 'auth.login'
    @app.before_request
    def reset_scoped_request_cache():
        # unittest retains an app context for ORM assertions; never reuse a
        # Flask-Login/CSRF g cache across different synthetic clients.
        from flask import g
        g.pop('_login_user', None)
        g.pop('csrf_token', None)
    @lm.user_loader
    def load(user_id):
        return db.session.get(User, user_id)
    app.add_url_rule('/auth/login', 'auth.login', lambda: ('synthetic login destination', 200))
    app.add_url_rule('/news/', 'news.hub', lambda: ('synthetic news destination', 200))
    app.add_url_rule('/auth/pending', 'auth.pending_approval', lambda: ('pending', 200))
    # Execute the exact existing approval guard AST, not a rewritten policy.
    tree = ast.parse((REPO / 'app/__init__.py').read_text(encoding='utf-8'))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'check_user_approval')
    fn.decorator_list = []
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), 'approval-guard', 'exec'), scope)
    app.before_request(scope['check_user_approval'])
    CSRFProtect(app)
    app.register_blueprint(community_bp, url_prefix='/community')
    app.jinja_env.filters['kst'] = lambda value, fmt='%Y-%m-%d': value.strftime(fmt) if value else ''
    app.jinja_env.globals['csrf_token'] = generate_csrf
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '''<!doctype html><html lang="ko"><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/static/css/tailwind.min.css"><link rel="stylesheet" href="/static/css/style.min.css"></head><body><main>{% block content %}{% endblock %}</main>{% block extra_js %}{% endblock %}</body></html>'''}), app.jinja_loader])
    with app.app_context():
        db.create_all()
        for role in ('admin', 'parent', 'student', 'teacher', 'manager', 'inactive'):
            db.session.add(User(user_id='fixture-' + role, email=role + '@example.invalid', name='합성 ' + role,
                password_hash='synthetic-unusable-password', role='parent' if role == 'inactive' else role,
                role_level=1 if role == 'admin' else 5, is_active=role != 'inactive'))
        db.session.commit()
    return app


class CommunityArticlesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_app()
        cls.net = patch.object(socket, 'create_connection', side_effect=AssertionError('external network forbidden'))
        cls.net.start()
        cls.push = patch('app.utils.push_utils.send_push_to_user_with_result', return_value={'status': 'disabled', 'detail': 'isolated test'}, create=True)
        cls.push.start()
        cls.legacy_push = patch('app.utils.push_utils.send_push_to_user', return_value=False, create=True)
        cls.legacy_push.start()

    @classmethod
    def tearDownClass(cls):
        cls.net.stop()
        cls.push.stop()
        cls.legacy_push.stop()
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        print('Synthetic evidence root:', ROOT)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        for model in (PostImage, PostFile, Bookmark, PostTag, Tag, PostLike, Comment, Post):
            db.session.query(model).delete()
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def client(self, role='admin'):
        client = self.app.test_client()
        if role:
            with client.session_transaction() as session:
                session['_user_id'] = 'fixture-' + role
                session['_fresh'] = True
        return client

    def token(self, client):
        # Generate a real CSRF token with this isolated client's session.
        with client.session_transaction() as session:
            with self.app.test_request_context():
                from flask import session as active
                from flask import g
                g.pop('csrf_token', None)
                active.update(session)
                token = generate_csrf()
                session.update(active)
        return token

    def post(self, client, path, data=None, **kwargs):
        token = self.token(client)
        if 'json' in kwargs:
            return client.post(path, headers={'X-CSRFToken': token}, **kwargs)
        return client.post(path, data={'csrf_token': token, **(data or {})}, **kwargs)

    def article(self, category='education_article', title='합성 교육기사'):
        p = Post(user_id='fixture-admin', category=category, title=title,
                 content='<p>합성 본문 기준일 2026-11-04</p><a href="https://example.com/">출처</a>')
        db.session.add(p)
        db.session.commit()
        return p.post_id

    def test_release_notice_uses_no_internal_review_names(self):
        html = self.client().get('/community/new').get_data(as_text=True)
        self.assertNotIn('Tom', html)
        self.assertNotIn('Alice', html)
        self.assertIn('즉시 반영', html)
        self.assertIn('공개 승인', html)

    def test_notice_removed_from_community_listing_without_deleting_posts(self):
        notice_id = self.article(category='notice', title='EXISTING MOMO NOTICE')
        question_id = self.article(category='question', title='PINNED QUESTION STAYS')
        db.session.get(Post, question_id).is_pinned = True
        db.session.commit()
        before = [(p.post_id,p.category,p.title,p.views) for p in Post.query.order_by(Post.post_id)]
        for suffix in ('', '?search=EXISTING', '?sort=views', '?sort=likes'):
            html = self.client('parent').get('/community/'+suffix).get_data(as_text=True)
            self.assertNotIn('EXISTING MOMO NOTICE',html)
            self.assertNotIn('category=notice',html)
        html = self.client('parent').get('/community/').get_data(as_text=True)
        self.assertIn('PINNED QUESTION STAYS', html)
        self.assertEqual(before,[(p.post_id,p.category,p.title,p.views) for p in Post.query.order_by(Post.post_id)])

    def test_legacy_notice_filter_redirects_to_news_anchor_after_login(self):
        response = self.client('parent').get('/community/?category=notice')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.location.endswith('/news/#momo-notices'))
        anonymous = self.client(None).get('/community/?category=notice')
        self.assertEqual(anonymous.status_code,302)
        self.assertIn('/auth/login',anonymous.location)

    def test_01_anonymous_requires_login(self):
        pid = self.article()
        for path in ('/community/', '/community/?category=education_article', '/community/' + pid, '/community/new', '/community/bookmarks'):
            response = self.client(None).get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/auth/login', response.location)

    def test_02_approved_roles_read(self):
        pid = self.article()
        for role in ('parent', 'student', 'teacher', 'admin', 'manager'):
            client = self.client(role)
            for path in ('/community/?category=education_article', '/community/' + pid):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('📰 교육기사', response.get_data(as_text=True))

    def test_03_non_admin_mutations_preserve_data(self):
        pid = self.article()
        for role in ('parent', 'student', 'teacher', 'manager'):
            client = self.client(role)
            for suffix in ('/new', '/' + pid + '/edit'):
                self.assertEqual(client.get('/community' + suffix).status_code, 302)
                response = self.post(client, '/community' + suffix, {'category': 'education_article', 'title': 'DENIED', 'content': 'DENIED'})
                self.assertEqual(response.status_code, 302)
            self.assertEqual(self.post(client, '/community/' + pid + '/delete').status_code, 302)
            self.assertEqual(Post.query.count(), 1)
            self.assertEqual(db.session.get(Post, pid).title, '합성 교육기사')

    def test_04_inactive_guard(self):
        pid = self.article()
        client = self.client('inactive')
        for path in ('/community/', '/community/' + pid, '/community/new'):
            response = client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/auth/pending', response.location)
        self.assertEqual(self.post(client, '/community/new', {'category': 'education_article', 'title': 'DENIED', 'content': 'DENIED'}).status_code, 302)
        self.assertEqual(Post.query.count(), 1)

    def test_05_admin_all_categories_create_edit(self):
        client = self.client()
        for category in ('education_article', 'notice', 'question', 'free', 'resource'):
            with self.subTest(category=category):
                response = self.post(client, '/community/new', {'category': category, 'title': category, 'content': '<p>합성 공개본문</p>'})
                self.assertEqual(response.status_code, 302)
                pid = response.location.rsplit('/', 1)[-1]
                page = client.get('/community/' + pid + '/edit')
                self.assertEqual(page.status_code, 200)
                soup = BeautifulSoup(page.data, 'html.parser')
                self.assertEqual(soup.select_one('select[name=category] option[selected]')['value'], category)
                response = self.post(client, '/community/' + pid + '/edit', {'category': category, 'title': category + ' revised', 'content': '합성 수정본문'})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(db.session.get(Post, pid).category, category)
                self.assertEqual(db.session.get(Post, pid).title, category + ' revised')

    def test_06_validation_and_csrf(self):
        client = self.client()
        for payload in ({'category': 'invalid', 'title': 'x', 'content': 'x'}, {'category': 'education_article', 'title': '', 'content': 'x'}, {'category': 'education_article', 'title': 'x', 'content': ''}):
            self.assertEqual(self.post(client, '/community/new', payload).status_code, 200)
            self.assertEqual(Post.query.count(), 0)
        self.assertEqual(client.post('/community/new', data={'category': 'education_article', 'title': 'x', 'content': 'x'}).status_code, 400)
        self.assertEqual(Post.query.count(), 0)

    def test_07_filter_search_sort_empty_and_reset(self):
        pid = self.article()
        self.article('free', '다른 분류')
        client = self.client('parent')
        for sort in ('recent', 'views', 'likes', 'invalid'):
            page = client.get('/community/?category=education_article&search=기준일&sort=' + sort)
            self.assertEqual(page.status_code, 200)
            html = page.get_data(as_text=True)
            self.assertIn('합성 교육기사', html)
            self.assertNotIn('다른 분류', html)
            soup = BeautifulSoup(html, 'html.parser')
            self.assertEqual(soup.select_one('input[name=category]')['value'], 'education_article')
            self.assertIn('초기화', html)
        self.assertIn('게시글이 없습니다', client.get('/community/?category=education_article&search=absent').get_data(as_text=True))
        self.assertIn('다른 분류', client.get('/community/').get_data(as_text=True))
        self.assertNotIn('&lt;p&gt;', client.get('/community/?category=education_article').get_data(as_text=True))

    def test_08_bookmarks_tags_interactions(self):
        pid = self.article()
        tag = Tag(name='합성태그')
        db.session.add(tag)
        db.session.flush()
        db.session.add(PostTag(post_id=pid, tag_id=tag.tag_id))
        db.session.commit()
        client = self.client('parent')
        path = '/community/api/posts/' + pid
        self.assertEqual(self.post(client, path + '/bookmark').json['action'], 'bookmarked')
        for url in ('/community/bookmarks', '/community/tags/합성태그'):
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('📰 교육기사', response.get_data(as_text=True))
        self.assertEqual(self.post(client, path + '/like').json['action'], 'liked')
        self.assertEqual(self.post(client, path + '/like').json['action'], 'unliked')
        response = self.post(client, path + '/comments', json={'content': '합성 댓글'})
        self.assertEqual(response.status_code, 200)
        cid = response.json['comment']['comment_id']
        self.assertEqual(self.post(client, path + '/comments', json={'content': '합성 대댓글', 'parent_comment_id': cid}).status_code, 200)
        html = client.get('/community/' + pid).get_data(as_text=True)
        self.assertIn('합성 대댓글', html)
        self.assertNotIn('우수질문 선정', html)
        self.assertEqual(self.post(client, path + '/bookmark').json['action'], 'unbookmarked')

    def test_09_synthetic_attachment_image(self):
        client = self.client()
        response = self.post(client, '/community/new', {'category': 'education_article', 'title': '합성 첨부', 'content': '합성', 'files': (io.BytesIO(b'synthetic only'), 'synthetic.txt'), 'images': (io.BytesIO(b'synthetic image fixture'), 'synthetic.png')})
        self.assertEqual(response.status_code, 302)
        pid = response.location.rsplit('/', 1)[-1]
        file = PostFile.query.filter_by(post_id=pid).one()
        image = PostImage.query.filter_by(post_id=pid).one()
        parent = self.client('parent')
        with parent.get('/community/files/' + file.file_id + '/download') as response:
            self.assertEqual(response.data, b'synthetic only')
        with parent.get('/community/post-images/' + image.stored_filename) as response:
            self.assertEqual(response.data, b'synthetic image fixture')
        self.assertEqual(self.client(None).get('/community/files/' + file.file_id + '/download').status_code, 302)

    def test_10_notice_and_no_posting_side_effect(self):
        client = self.client()
        html = client.get('/community/new').get_data(as_text=True)
        self.assertIn('비공개 임시저장 기능은 없습니다', html)
        self.assertIn('근거 확인과 최종 검수', html)
        client.get('/community/?category=education_article')
        self.assertEqual(Post.query.count(), 0)
        self.assertEqual(Tag.query.count(), 0)
        self.assertEqual(Bookmark.query.count(), 0)

    def test_11_pinned_and_sort_order(self):
        ids = [self.article(title=title) for title in ('낮은값', '높은값', '고정글')]
        for pid, views, likes, pinned in zip(ids, (1, 99, 0), (1, 99, 0), (False, False, True)):
            post = db.session.get(Post, pid)
            post.views, post.likes_count, post.is_pinned = views, likes, pinned
        db.session.commit()
        for sort in ('views', 'likes'):
            html = self.client('parent').get('/community/?category=education_article&sort=' + sort).get_data(as_text=True)
            self.assertLess(html.index('고정글'), html.index('높은값'))
            self.assertLess(html.index('높은값'), html.index('낮은값'))

    def test_12_question_only_actions_reject_article(self):
        pid = self.article()
        client = self.client('teacher')
        for action in ('select-question', 'select-excellent'):
            response = self.post(client, '/community/' + pid + '/' + action)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Post, pid).category, 'education_article')

    def test_13_invalid_edit_preserves_category(self):
        pid = self.article()
        client = self.client()
        response = self.post(client, '/community/' + pid + '/edit', {'title': 'invalid edit', 'content': 'x', 'category': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.get(Post, pid).title, '합성 교육기사')
        self.assertEqual(db.session.get(Post, pid).category, 'education_article')


if __name__ == '__main__':
    unittest.main(verbosity=2)
