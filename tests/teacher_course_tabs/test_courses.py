"""Isolated real-blueprint/ORM checks. Never import the operational app factory."""
import importlib
from pathlib import Path
import sys
import types
from datetime import date, datetime, time

import pytest
from flask import Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

ROOT = Path(__file__).resolve().parents[2]
# Import the app's real submodules without executing app/__init__.py.
package = types.ModuleType('app')
package.__path__ = [str(ROOT / 'app')]
sys.modules['app'] = package
from app.models import db, User, Student, Course, CourseEnrollment
from app.teacher import teacher_bp


@pytest.fixture
def app():
    app = Flask('teacher_courses_fixture', template_folder=str(ROOT / 'templates'))
    app.config.update(TESTING=True, SECRET_KEY='synthetic-only', SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    login = LoginManager(app)
    @login.user_loader
    def load_user(uid):
        return db.session.get(User, uid)
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    # Only unrelated site chrome is reduced; the candidate course template and macros are real.
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>{% block content %}{% endblock %}</body></html>'}), FileSystemLoader(str(ROOT / 'templates'))])
    app.jinja_env.filters['kst'] = lambda value, fmt: value.strftime(fmt)
    with app.app_context():
        db.create_all()
        for uid, role in [('owner', 'teacher'), ('other', 'teacher'), ('parent', 'parent')]:
            db.session.add(User(user_id=uid, email=uid+'@fixture.invalid', name=uid, role=role, password_hash='not-a-real-login'))
        db.session.add(Student(student_id='student', teacher_id='owner', name='Needle', grade='초3'))
        for owner in ['owner', 'other']:
            for state in ['active', 'completed', 'cancelled']:
                for n, wd in [(1, 3), (2, 1)]:
                    cid = f'{owner}-{state}-{n}'
                    db.session.add(Course(course_id=cid, teacher_id=owner, course_name=cid, course_code=cid,
                        grade='초3', course_type='정규반', status=state, weekday=wd, start_time=time(15),
                        start_date=date(2026, 1, 1), end_date=date(2026, 12, 1), created_at=datetime(2026, 1, n)))
                    db.session.add(CourseEnrollment(course_id=cid, student_id='student'))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = 'owner'
        session['_fresh'] = True
    return client


def get_html(client, **query):
    response = client.get('/teacher/courses', query_string=query)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_default_only_active(client):
    html = get_html(client)
    assert 'owner-active-1' in html
    assert 'owner-completed-1' not in html
    assert 'owner-cancelled-1' not in html
    assert 'other-active-1' not in html


def test_tabs_preserve_filters_and_sort(client):
    from bs4 import BeautifulSoup
    from urllib.parse import parse_qs, urlsplit
    query = dict(status='active', grade='초3', weekday='1', course_type='정규반', search='Needle & sort=newest', sort='weekday')
    soup = BeautifulSoup(get_html(client, **query), 'html.parser')
    nav = soup.find('nav', attrs={'aria-label': '수업 상태'})
    assert nav is not None
    for state, label in [('active', '진행 중'), ('completed', '완료'), ('cancelled', '취소')]:
        anchor = nav.find('a', string=lambda text: text and text.strip() == label)
        assert anchor is not None
        expected = {key: [value] for key, value in dict(query, status=state).items()}
        assert parse_qs(urlsplit(anchor['href']).query) == expected
        assert (anchor.get('aria-current') == 'page') == (state == 'active')
    assert soup.select('select[name=status]') == []


@pytest.mark.parametrize('state', ['active', 'completed', 'cancelled'])
def test_filter_form_preserves_selected_tab_and_sort(client, state):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(get_html(client, status=state, sort='weekday'), 'html.parser')
    form = soup.find('form')
    assert form.select_one('input[type=hidden][name=status]')['value'] == state
    assert form.select_one('input[type=hidden][name=sort]')['value'] == 'weekday'


@pytest.mark.parametrize('status', ['', 'completed', 'bogus'])
def test_sort_urls_use_normalized_status_and_preserve_literal_search(client, status):
    from bs4 import BeautifulSoup
    from urllib.parse import parse_qs, urlsplit
    # Matching special characters detects the old raw-query .replace corruption.
    with client.application.app_context():
        for row in Course.query.filter_by(teacher_id='owner').all():
            row.course_name = 'literal sort=newest & question?'
        db.session.commit()
    query = dict(status=status, grade='초3', weekday='1', course_type='정규반', search='literal sort=newest & question?')
    soup = BeautifulSoup(get_html(client, **query), 'html.parser')
    for label, sort in [('최신순', 'newest'), ('요일순', 'weekday')]:
        anchor = soup.find('a', string=lambda text: text and text.strip() == label)
        assert anchor is not None
        expected = dict(query, status='completed' if status == 'completed' else 'active', sort=sort)
        assert parse_qs(urlsplit(anchor['href']).query) == {k: [v] for k, v in expected.items()}


@pytest.mark.parametrize('state,label', [('active', '진행 중인'), ('completed', '완료된'), ('cancelled', '취소된')])
@pytest.mark.parametrize('filtered', [False, True])
def test_empty_state_and_reset_stay_in_selected_tab(client, state, label, filtered):
    from bs4 import BeautifulSoup
    from urllib.parse import parse_qs, urlsplit
    if not filtered:
        with client.application.app_context():
            Course.query.filter_by(teacher_id='owner', status=state).delete()
            db.session.commit()
    html = get_html(client, status=state, search='missing' if filtered else '', sort='weekday')
    soup = BeautifulSoup(html, 'html.parser')
    if filtered:
        assert '검색 조건에 맞는 수업이 없습니다.' in html
        reset = soup.find('a', string=lambda text: text and text.strip() == '초기화')
        assert reset is not None
        assert parse_qs(urlsplit(reset['href']).query) == {'status': [state], 'sort': ['weekday']}
        cleared = client.get(reset['href']).get_data(as_text=True)
        assert f'owner-{state}-1' in cleared
        assert '전체 수업 보기' not in html
    else:
        assert f'{label} 담당 수업이 없습니다.' in html
        assert '검색 조건에 맞는 수업이 없습니다.' not in html
        assert soup.find('a', string=lambda text: text and text.strip() == '초기화') is None


@pytest.mark.parametrize('state', ['active', 'completed', 'cancelled'])
@pytest.mark.parametrize('search', ['', 'Needle', 'owner-'])
@pytest.mark.parametrize('sort', ['newest', 'weekday'])
def test_status_and_ownership_survive_both_search_paths(client, state, search, sort):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(get_html(client, status=state, search=search, sort=sort), 'html.parser')
    names = [h.get_text(strip=True) for h in soup.select('h3')]
    assert names == [f'owner-{state}-2', f'owner-{state}-1']
    # Give newest and weekday opposite orders; verify both SQL and Python-merge sorting.
    with client.application.app_context():
        db.session.get(Course, f'owner-{state}-1').weekday = 0
        db.session.commit()
    soup = BeautifulSoup(get_html(client, status=state, search=search, sort=sort), 'html.parser')
    expected = [1, 2] if sort == 'weekday' else [2, 1]
    assert [h.get_text(strip=True) for h in soup.select('h3')] == [f'owner-{state}-{n}' for n in expected]


@pytest.mark.parametrize('state', ['active', 'completed', 'cancelled'])
@pytest.mark.parametrize('filters', [{'grade': '초4'}, {'weekday': '6'}, {'course_type': '특강'}, {'grade': '초3', 'weekday': '1', 'course_type': '정규반'}])
def test_student_name_merge_respects_every_filter(client, state, filters):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(get_html(client, status=state, search='Needle', **filters), 'html.parser')
    expected = [f'owner-{state}-2'] if len(filters) == 3 else []
    assert [h.get_text(strip=True) for h in soup.select('h3')] == expected


def test_student_and_text_merge_deduplicates(client):
    from bs4 import BeautifulSoup
    with client.application.app_context():
        db.session.get(Course, 'owner-completed-1').course_name = 'Needle'
        db.session.commit()
    soup = BeautifulSoup(get_html(client, status='completed', search='Needle'), 'html.parser')
    assert [h.get_text(strip=True) for h in soup.select('h3')] == ['owner-completed-2', 'Needle']


def test_weekday_text_search(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(get_html(client, status='completed', search='화요일'), 'html.parser')
    assert [h.get_text(strip=True) for h in soup.select('h3')] == ['owner-completed-2']


def test_role_and_login_guards_unchanged(app):
    client = app.test_client()
    assert client.get('/teacher/courses').status_code == 401
    with client.session_transaction() as session:
        session['_user_id'] = 'parent'
    assert client.get('/teacher/courses').status_code == 403


def test_browser_tab_search_sort_reset_and_history(client):
    from playwright.sync_api import sync_playwright, expect
    from urllib.parse import urlsplit, parse_qs
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        # Fulfil real browser HTTP requests with the real authenticated Flask client.
        # This creates no external socket, server, operational app or persistent DB.
        def respond(route):
            url = urlsplit(route.request.url)
            assert url.hostname == 'teacher-fixture.invalid'
            response = client.get(url.path + ('?' + url.query if url.query else ''))
            route.fulfill(status=response.status_code, body=response.get_data(), content_type='text/html; charset=utf-8')
        page.route('**/*', respond)
        page.goto('http://teacher-fixture.invalid/teacher/courses')
        expect(page.locator('h3')).to_have_text(['owner-active-2', 'owner-active-1'])
        nav = page.get_by_role('navigation', name='수업 상태')
        nav.get_by_role('link', name='완료', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-completed-2', 'owner-completed-1'])
        expect(nav.get_by_role('link', name='완료', exact=True)).to_have_attribute('aria-current', 'page')
        page.locator('select[name=grade]').select_option('초3')
        page.locator('select[name=weekday]').select_option('1')
        page.locator('select[name=course_type]').select_option('정규반')
        page.locator('input[name=search]').fill('Needle')
        page.get_by_role('button', name='검색', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-completed-2'])
        page.get_by_role('link', name='요일순', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-completed-2'])
        nav.get_by_role('link', name='진행 중', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-active-2'])
        qs = parse_qs(urlsplit(page.url).query)
        assert qs == {'status': ['active'], 'grade': ['초3'], 'weekday': ['1'], 'course_type': ['정규반'], 'search': ['Needle'], 'sort': ['weekday']}
        nav.get_by_role('link', name='완료', exact=True).click()
        page.get_by_role('link', name='초기화', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-completed-2', 'owner-completed-1'])
        assert parse_qs(urlsplit(page.url).query) == {'status': ['completed'], 'sort': ['weekday']}
        page.locator('input[name=search]').fill('not-found')
        page.get_by_role('button', name='검색', exact=True).click()
        expect(page.get_by_text('검색 조건에 맞는 수업이 없습니다.', exact=True)).to_be_visible()
        page.get_by_role('link', name='필터 해제', exact=True).click()
        expect(page.locator('h3')).to_have_count(2)
        nav.get_by_role('link', name='취소', exact=True).click()
        expect(page.locator('h3')).to_have_text(['owner-cancelled-2', 'owner-cancelled-1'])
        page.go_back()
        expect(page.locator('h3')).to_have_text(['owner-completed-2', 'owner-completed-1'])
        page.screenshot(path=str(ROOT / 'reports/teacher-course-tabs/browser-completed.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(ROOT / 'reports/teacher-course-tabs/browser-completed-mobile.png'), full_page=True)
        print('Chromium:', browser.version)
        browser.close()


@pytest.mark.parametrize('status', ['', '   ', 'all', 'bogus'])
def test_unrecognized_status_normalizes_to_active(client, status):
    html = get_html(client, status=status)
    assert 'owner-active-1' in html
    assert 'owner-completed-1' not in html
    assert 'owner-cancelled-1' not in html
