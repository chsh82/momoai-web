"""Real loopback Flask -> production blueprint/backend/store -> Chromium.

Only the account identity and Student query boundary are doubled. No app
factory, ORM database, fake API responses, or browser request interception.
"""
import json
from pathlib import Path
import sqlite3
import sys
from threading import Thread
import types
from uuid import uuid4

import pytest
from flask import Flask, abort, redirect, request
from flask_login import LoginManager, UserMixin, login_user
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
BASE = '/student/interest-quest'
NAME = '<img src=x onerror=alert(1)>격리 학생'
VERSION = '1.0.0-draft1+interest-only-momotown-v02'
if 'app' not in sys.modules:
    package = types.ModuleType('app')
    package.__path__ = [str(ROOT/'app')]
    sys.modules['app'] = package
from app.interest_quest import interest_quest_bp


@pytest.fixture
def live(tmp_path, monkeypatch):
    students = [types.SimpleNamespace(student_id='s1', user_id='u1', name=NAME),
                types.SimpleNamespace(student_id='s2', user_id='u2', name='다른 격리 학생')]
    class Query:
        def __init__(self, filters=None): self.filters = filters or {}
        def filter_by(self, **kwargs):
            assert set(kwargs) <= {'student_id', 'user_id'}, 'Actual PK is Student.student_id'
            return Query(kwargs)
        def all(self):
            return [s for s in students if all(getattr(s, key)==value for key,value in self.filters.items())]
    models = types.ModuleType('app.models')
    models.Student = type('Student', (), {'query': Query()})
    monkeypatch.setitem(sys.modules, 'app.models', models)
    class Identity(UserMixin):
        def __init__(self, uid):
            self.id = uid
            self.role = 'admin' if uid=='admin' else 'student'
            self.is_admin = self.role=='admin'
    app = Flask('isolated-real-momotown', template_folder=str(ROOT/'templates'))
    app.config.update(TESTING=True, SECRET_KEY='isolated-browser-test-only',
                      STUDENT_INTEREST_QUEST_ENABLED=True,
                      MOMOTOWN_FEEDBACK_DB=str(tmp_path/'private.sqlite3'))
    manager = LoginManager(app)
    manager.user_loader(lambda uid: Identity(uid) if uid in ('u1','u2','admin') else None)
    @app.route('/__fixture_login/<uid>')
    def fixture_login(uid):
        if request.remote_addr != '127.0.0.1' or uid not in ('u1','u2','admin'): abort(403)
        login_user(Identity(uid))
        return redirect(BASE+'/')
    app.add_url_rule('/login', 'auth.login', lambda: ('fixture login required', 401))
    writes = []
    @app.before_request
    def capture_writes():
        if request.method=='POST' and request.path.startswith(BASE):
            writes.append(dict(path=request.path, payload=request.get_json(silent=True), csrf=request.headers.get('X-CSRFToken')))
    app.register_blueprint(interest_quest_bp, url_prefix=BASE)
    http = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield dict(app=app, origin=f'http://127.0.0.1:{http.server_port}', writes=writes,
               db=Path(app.config['MOMOTOWN_FEEDBACK_DB']))
    http.shutdown(); http.server_close(); thread.join(timeout=5)


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        yield page
        context.close(); browser.close()
        assert not errors


def login(page, live, uid='u1'):
    page.goto(live['origin']+'/__fixture_login/'+uid)
    page.wait_for_function('window.festivalIdentity?.mode === '+json.dumps('admin_preview' if uid=='admin' else 'student'))


def complete(page):
    page.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();}')
    page.get_by_role('tab').first.wait_for()


def visit_three(page):
    assert page.locator('#result-panel').get_attribute('data-step') == 'core'
    for text in ('학과·직업·공부', '두 번째 마을', '세 번째 마을', '비교와 리포트'):
        page.get_by_role('tab').filter(has_text=text).click()


def snapshot(live):
    with sqlite3.connect(live['db']) as db:
        return {table: db.execute('SELECT * FROM '+table).fetchall() for table in ('attempts','presentations','preferences')}


def get_attempt(page, live, attempt_id):
    response = page.request.get(live['origin']+BASE+'/attempts/'+attempt_id)
    assert response.status == 200
    return response.json()


def test_real_student_journey_sqlite_parity_save_ack_report_and_reload(page, live):
    login(page, live)
    assert NAME in page.locator('#main').inner_text()
    assert page.locator('#main img[src=x]').count() == 0
    assert page.locator('input[type=text]').count() == 0
    assert page.context.cookies(), 'Real Flask-Login session cookie must authenticate browser fetches'
    # Exercise all real radio inputs and progression, not a prefilled session.
    page.evaluate('init()')
    page.locator('button[onclick="continueJourney()"]').click()
    choices = page.evaluate('qaSampleValues("lab")')
    for index, option in enumerate(choices):
        assert page.evaluate('session.cursor') == index
        page.locator('.option').filter(has=page.locator('input[value="'+option+'"]')).click()
        page.locator('#next').click()
        if index in (7,15,23):
            page.locator('button[onclick="continueJourney()"]').click()
    with page.expect_response(lambda r: r.url.endswith('/attempts') and r.request.method=='POST') as attempt:
        page.locator('button[onclick="finish()"]').first.click()
    assert attempt.value.status == 200
    page.get_by_role('tab').first.wait_for()
    attempt_id = page.evaluate('session.festival.attempt_id')
    created = get_attempt(page, live, attempt_id)
    answers = page.evaluate('session.values')
    assert len(answers) == 32 and created['answers'] == answers
    expected = page.evaluate('''()=>InterestScoring.score(session.values.map((id,i)=>({item_id:FORM.items[i].id,option_id:id})),FORM).domains.map(({domain_id,selected_count,offered_count,comparison_units,display_order})=>({domain_id,selected_count,offered_count,comparison_units,display_order}))''')
    assert created['analysis']['domains'] == expected
    assert created['analysis']['representatives'] == created['presented_villages']
    baseline_report = page.evaluate('reportHtml(reportModel(session))')
    visit_three(page)
    page.get_by_role('button', name='전체 리포트 보기', exact=True).click()
    cards = page.locator('#dialog .preference-card')
    assert cards.count() == 3
    assert page.get_by_role('button', name='선택하고 리포트 보기', exact=True).is_disabled()
    cards.nth(1).click()
    assert page.locator('#dialog .preference-card[aria-pressed=true]').count() == 1
    with page.expect_response(lambda r: r.url.endswith('/preference') and r.request.method=='POST') as acknowledgement:
        page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    assert acknowledgement.value.status == 200
    saved = acknowledgement.value.json()
    page.locator('.journey-report').wait_for()
    assert page.evaluate('session.festival.acknowledged') is True
    assert saved['analysis'] == created['analysis']
    assert saved['preference']['selected_village_id'] == created['presented_villages'][1]
    assert saved['preference']['selected_display_position'] == 2
    assert saved['form_version'] == VERSION and saved['copy_version'] == 'momotown-festival-v02'
    assert len(saved['presentations']) == 3
    assert all(p['shown_sections']==['intro','study'] for p in saved['presentations'])
    assert get_attempt(page, live, attempt_id) == saved
    assert page.evaluate('reportHtml(reportModel(session))') == baseline_report
    with sqlite3.connect(live['db']) as db:
        assert db.execute('SELECT student_id,origin FROM attempts').fetchall() == [('s1','STUDENT')]
        assert db.execute('SELECT count(*) FROM preferences').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM presentations').fetchone()[0] == 6
        persisted = json.loads(db.execute('SELECT snapshot FROM attempts').fetchone()[0])
        assert persisted['analysis'] == created['analysis']
        schema = ' '.join(r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
        assert 'reason' not in schema.lower()
        assert NAME not in str(snapshot(live))
    assert all('reason' not in json.dumps(w['payload']) for w in live['writes'])
    assert all(w['csrf'] for w in live['writes'])
    assert 'attempt='+attempt_id in page.url
    before = snapshot(live)
    page.reload()
    page.wait_for_function('session?.festival?.verified===true')
    assert page.evaluate('session.values') == answers
    assert page.evaluate('session.festival.preference') == saved['preference']
    assert page.evaluate('session.festival.acknowledged') is True
    page.evaluate('printResult()')
    page.locator('.journey-report').wait_for()
    assert page.evaluate('reportHtml(reportModel(session))') == baseline_report
    assert get_attempt(page, live, attempt_id) == saved
    assert snapshot(live) == before


def test_real_csrf_and_cross_student_ownership_never_write(page, live):
    login(page, live); complete(page)
    data = get_attempt(page, live, page.evaluate('session.festival.attempt_id'))
    path = live['origin']+BASE+'/attempts/'+data['attempt_id']
    bodies = [('/presentation',dict(analysis_revision=data['analysis_revision'],domain_id=data['presented_villages'][0],sections=['intro'])),
              ('/preference',dict(request_id=str(uuid4()),analysis_revision=data['analysis_revision'],selected_village_id=data['presented_villages'][0]))]
    before = snapshot(live)
    create = next(w['payload'] for w in live['writes'] if w['path']==BASE+'/attempts')
    for suffix, body in [('', create)]:
        for headers in ({}, {'X-CSRFToken':'forged'}):
            assert page.request.post(live['origin']+BASE+'/attempts',data=body,headers=headers).status == 400
    for suffix,body in bodies:
        for headers in ({}, {'X-CSRFToken':'forged'}):
            assert page.request.post(path+suffix,data=body,headers=headers).status == 400
    assert snapshot(live) == before
    login(page, live, 'u2')
    token = page.request.get(live['origin']+BASE+'/context').json()['csrf_token']
    assert page.request.get(path).status == 404
    for suffix,body in bodies:
        assert page.request.post(path+suffix,data=body,headers={'X-CSRFToken':token}).status == 404
    assert snapshot(live) == before


def test_real_admin_flags_off_preview_and_lookup_totals_no_writes(page, live):
    login(page, live); complete(page); visit_three(page)
    page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(2).click()
    page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    page.locator('.journey-report').wait_for()
    login(page, live, 'u2'); complete(page)
    # The visible result tab queues a real presentation write. Await its
    # acknowledgement/readback before taking the no-admin-writes baseline;
    # otherwise a student request can commit after this snapshot.
    page.evaluate('async()=>{await session.festival.presentation_queue;}')
    student_attempt = get_attempt(page, live, page.evaluate('session.festival.attempt_id'))
    assert student_attempt['presentations'] == [
        dict(domain_id=student_attempt['presented_villages'][0], shown_sections=['intro'])]
    before = snapshot(live)
    live['app'].config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    assert page.request.get(live['origin']+BASE+'/context').status == 403
    login(page, live, 'admin')
    assert NAME not in page.locator('#main').inner_text()
    assert '관리자 미리보기' in page.locator('#main').inner_text()
    writes_before = len(live['writes'])
    complete(page); visit_three(page); page.evaluate('printResult()')
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    page.locator('.journey-report').wait_for()
    assert len(live['writes']) == writes_before
    assert snapshot(live) == before
    result = page.request.get(live['origin']+BASE+'/feedback.json?limit=1').json()
    assert len(result['rows']) == 1 and result['has_more'] is True
    assert result['summary']['attempts'] == result['summary']['students'] == 2
    assert result['summary']['completed'] == result['summary']['pending'] == 1
    assert result['summary']['selected_display_positions'] == {'3':1}
    page.goto(live['origin']+BASE+'/feedback')
    assert NAME in page.locator('body').inner_text()
    assert page.locator('img[src=x]').count() == 0
    assert snapshot(live) == before
