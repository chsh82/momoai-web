"""Real Chromium -> real blueprint -> synthetic SQLite contract tests."""
import os
from pathlib import Path
import threading

import pytest
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server


@pytest.fixture
def browser_page(tutorial):
    app, db, client, Progress = tutorial
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        executable = os.environ.get('TUTORIAL_CHROMIUM', 'C:/Program Files/Google/Chrome/Application/chrome.exe')
        browser = p.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page(viewport={'width':390,'height':844})
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        cookie = client.get_cookie('session')
        if cookie:
            page.context.add_cookies([{'name':'session','value':cookie.value,'url':origin}])
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        yield page, origin
        assert not errors, errors
        browser.close()
    server.shutdown()
    thread.join(timeout=5)


def finish(page):
    page.locator('#cardNextBtn').click()
    page.locator('.opt').first.click()
    page.locator('#quizNextBtn').click()
    expect(page.locator('#result')).to_have_class('screen on')


def test_saved_result_next_lesson_and_courses_anchor(browser_page, tutorial):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    finish(page)
    expect(page.locator('#saveStatus')).to_have_text('레슨 완료 · 진도 저장됨')
    expect(page.locator('#courseProgress')).to_contain_text('1/4')
    expect(page.locator('#learn .of')).to_have_text('레슨 1/4 · 배우기')
    expect(page.locator('#quiz-screen .of')).to_have_text('레슨 1/4 · 확인 문제')
    expect(page.locator('#nextLessonBtn')).to_be_visible()
    page.locator('#nextLessonBtn').click()
    expect(page).to_have_url(origin + '/tutorial/elem/course1/elem-course1-l2')
    page.locator('#learn .back').click()
    expect(page).to_have_url(origin + '/tutorial/elem/#courses')
    expect(page.locator('#courses')).to_have_class('screen on')


@pytest.mark.parametrize('failure', ['http500','null','missing_saved','network'])
def test_failure_retry_never_claims_saved_or_next_until_ack(browser_page, failure):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    def fail(route):
        if failure == 'network':
            route.abort()
        elif failure == 'null':
            route.fulfill(status=200, content_type='application/json', body='null')
        elif failure == 'missing_saved':
            route.fulfill(status=200, json={'points_awarded':False})
        else:
            route.fulfill(status=500, json={'saved':False})
    page.route('**/api/complete', fail)
    finish(page)
    expect(page.locator('#saveWarn')).to_be_visible()
    expect(page.locator('#nextLessonBtn')).to_be_hidden()
    expect(page.locator('#saveStatus')).to_contain_text('미저장')
    page.unroute('**/api/complete')
    page.get_by_role('button', name='다시 저장', exact=True).click()
    expect(page.locator('#saveStatus')).to_have_text('레슨 완료 · 진도 저장됨')
    expect(page.locator('#nextLessonBtn')).to_be_visible()


@pytest.mark.parametrize('reply', ['success','failure'])
def test_replay_invalidates_old_async_completion(browser_page, reply):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    held = []
    page.route('**/api/complete', lambda route: held.append(route))
    finish(page)
    expect(page.locator('#saveStatus')).to_have_text('진도 저장 중…')
    expect(page.locator('#nextLessonBtn')).to_be_hidden()
    page.get_by_role('button', name='다시 풀기', exact=True).click()
    if reply == 'success':
        held[0].continue_()
    else:
        held[0].fulfill(status=500, json={'saved':False})
    page.wait_for_timeout(150)
    expect(page.locator('#saveStatus')).to_be_empty()
    expect(page.locator('#saveWarn')).to_be_hidden()
    expect(page.locator('#nextLessonBtn')).to_be_hidden()
    expect(page.locator('#courseProgress')).to_be_hidden()
    expect(page.locator('#mileLine')).to_be_hidden()
    expect(page.locator('#learn')).to_have_class('screen on')


def test_home_during_save_waits_for_ack_and_refreshed_progress(browser_page):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    held = []
    page.route('**/api/complete', lambda route: held.append(route))
    finish(page)
    page.locator('#result .back').click()
    page.wait_for_timeout(100)
    assert page.url.endswith('elem-course1-l1'), 'Must not leave before save acknowledgement'
    held[0].continue_()
    expect(page).to_have_url(origin + '/tutorial/elem/#courses')
    expect(page.locator('a.course').first).to_contain_text('1/4')


def set_actor(page, origin, tutorial, uid):
    app, db, client, Progress = tutorial
    page.context.clear_cookies()
    if uid:
        serializer = app.session_interface.get_signing_serializer(app)
        page.context.add_cookies([{'name':'session','value':serializer.dumps({'_user_id':uid,'_fresh':True}), 'url':origin}])


@pytest.mark.parametrize('uid', ['admin','teacher','parent',None])
def test_role_specific_result_never_offers_unsaved_next(browser_page, tutorial, uid):
    page, origin = browser_page
    set_actor(page, origin, tutorial, uid)
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    finish(page)
    expect(page.locator('#nextLessonBtn')).to_be_hidden()
    expect(page.locator('#courseProgress')).to_be_hidden()
    expect(page.locator('#mileLine')).to_be_hidden()
    if uid:
        expect(page.locator('#saveStatus')).to_have_text('체험 완료 · 진도 저장 대상 아님')
        expect(page.locator('#skipNote')).to_be_visible()
        expect(page.locator('#saveWarn')).to_be_hidden()
    else:
        expect(page.locator('#saveStatus')).to_have_text('문제 풀이 끝 · 진도 미저장 · 로그인이 필요해요')
        expect(page.locator('#saveWarn')).to_be_visible()
    app, db, client, Progress = tutorial
    assert Progress.query.count() == 0
    page.locator('#result .back').click()
    expect(page).to_have_url(origin + '/tutorial/elem/#courses')


def test_replay_resets_saved_result_before_new_attempt(browser_page):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    finish(page)
    expect(page.locator('#nextLessonBtn')).to_be_visible()
    page.get_by_role('button', name='다시 풀기', exact=True).click()
    expect(page.locator('#saveStatus')).to_be_empty()
    expect(page.locator('#nextLessonBtn')).to_be_hidden()
    expect(page.locator('#courseProgress')).to_be_hidden()
    page.locator('#cardNextBtn').click()
    expect(page.locator('.opt').first).to_be_enabled()
    page.locator('.opt').last.click()
    page.locator('#quizNextBtn').click()
    expect(page.locator('#scoreN')).to_have_text('0')
    expect(page.locator('#courseProgress')).to_contain_text('1/4')


@pytest.mark.parametrize('track,total', [('elem',4),('mid',9)])
def test_full_course_result_has_no_next_and_hole_resumes_first(browser_page, tutorial, track, total):
    from conftest import complete
    app, db, client, Progress = tutorial
    page, origin = browser_page
    page.goto(origin + f'/tutorial/{track}/course2/{track}-course2-l{total}')
    finish(page)
    expect(page.locator('#courseProgress')).to_contain_text(f'1/{total}')
    expect(page.locator('#nextLessonBtn')).to_have_attribute('href', f'/tutorial/{track}/course2/{track}-course2-l1')
    for i in range(1,total):
        complete(client, track=track, index=i, course='course2')
    page.reload()
    finish(page)
    expect(page.locator('#courseProgress')).to_have_text(f'코스 진도 {total}/{total} · 코스 전체 완료!')
    expect(page.locator('#nextLessonBtn')).to_be_hidden()


def test_failed_save_can_explicitly_leave_without_claiming_saved(browser_page, tutorial):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    page.route('**/api/complete', lambda route: route.fulfill(status=500, json={'saved':False}))
    finish(page)
    expect(page.locator('#saveWarn')).to_be_visible()
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('#result .back').click()
    expect(page).to_have_url(origin + '/tutorial/elem/#courses')
    app, db, client, Progress = tutorial
    assert Progress.query.count() == 0


def test_failed_home_stays_for_retry_and_pending_retry_is_single_flight(browser_page):
    page, origin = browser_page
    page.goto(origin + '/tutorial/elem/course1/elem-course1-l1')
    page.route('**/api/complete', lambda route: route.fulfill(status=500, json={'saved':False}))
    finish(page)
    expect(page.locator('#saveWarn')).to_be_visible()
    page.locator('#result .back').click()
    assert page.url.endswith('elem-course1-l1')
    page.unroute('**/api/complete')
    held = []
    page.route('**/api/complete', lambda route: held.append(route))
    page.get_by_role('button', name='다시 저장', exact=True).click()
    page.evaluate('() => { tryCompleteSave(); tryCompleteSave(); }')
    page.wait_for_timeout(150)
    assert len(held) == 1
    held[0].continue_()
    expect(page.locator('#saveStatus')).to_have_text('레슨 완료 · 진도 저장됨')
