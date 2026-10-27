"""Delayed HTTP responses against candidate overlay; no generated/live files change."""
import json
import os

import pytest
from test_momotown import page, server, student, complete, visit_three, HTML

SOURCE = HTML.parent / 'momotown-v02.js'


@pytest.fixture
def candidate(page, server):
    original = HTML.read_text(encoding='utf8')
    marker = '/* Final display-only festival overlay. FORM/V12/scorer remain canonical. */'
    head, tail = original.split(marker, 1)
    document = head + SOURCE.read_text(encoding='utf8') + '</script>' + tail.rsplit('</script>', 1)[1]
    if os.environ.get('MOMOTOWN_NAVIGATION_BASELINE'):
        document = original
    page.route(server['url'], lambda route: route.fulfill(
        status=200, content_type='text/html; charset=utf-8', body=document))
    page.set_viewport_size({'width': 1440, 'height': 1000})
    student(page, server)
    return page


def hold(page, pattern):
    held = []
    def receive(route):
        held.append(route)
        page.unroute(pattern, receive)
    page.route(pattern, receive)
    return held


def depart(page, transition):
    """Use the actual controls/history, not assignments to the app's view."""
    if transition == 'review':
        if page.locator('#dialog').is_visible():
            page.get_by_role('button', name='닫기', exact=True).click()
        page.get_by_role('button', name='선택한 응답 수정', exact=True).click()
    elif transition == 'home':
        if page.locator('#dialog').is_visible():
            page.locator('#dialog').get_by_role('button', name='첫 화면으로', exact=True).click()
        else:
            page.get_by_role('button', name='메뉴', exact=True).click()
            page.locator('.nav').get_by_role('button', name='첫 화면으로', exact=True).click()
    elif transition == 'close':
        if not page.locator('#dialog').is_visible():
            page.get_by_role('button', name='메뉴', exact=True).click()
            page.get_by_role('button', name='기록 저장·불러오기', exact=True).click()
        page.get_by_role('button', name='닫기', exact=True).click()
    elif transition == 'escape':
        page.keyboard.press('Escape')
    else:
        page.go_back()
        page.wait_for_function('view !== "festival-saving"' if page.evaluate('view') == 'festival-saving' else '!document.querySelector("#dialog").open')


def screen(page):
    return page.evaluate('''()=>({view, hash:location.hash, tab:resultTab,
        dialog:document.querySelector('#dialog').open,
        main:document.querySelector('#main').innerHTML})''')


def settle(page, held, outcome, payload, done):
    page.wait_for_function('window.__raceDone === false')
    assert len(held) == 1
    held[0].fulfill(status=200 if outcome == 'success' else 503,
                    content_type='application/json', body=json.dumps(payload))
    page.wait_for_function(done)


@pytest.mark.parametrize('outcome', ['success', 'error'])
@pytest.mark.parametrize('transition', ['home', 'review', 'close', 'back'])
@pytest.mark.parametrize('boundary', ['write', 'readback'])
def test_delayed_attempt_save_does_not_reopen_departed_screen(candidate, server, outcome, transition, boundary):
    page = candidate
    page.evaluate('init();session.values=qaSampleValues("lab");view="anticipation";render()')
    pattern = '**/attempts' if boundary == 'write' else '**/attempts/fixture-attempt'
    held = hold(page, pattern)
    # Track settlement without replacing the production finish implementation.
    page.evaluate('window.__raceDone=false;window.__raceOriginal=finish;finish=function(){return window.__raceOriginal().finally(()=>window.__raceDone=true)};void 0')
    with page.expect_request(pattern):
        page.get_by_role('button', name='나의 마을 만나기', exact=True).click()
    page.wait_for_function('session.festival.saving')
    # Route.fetch exercises the fixture's real contract/scoring and write payload.
    assert len(held) == 1
    response = held[0].fetch().json()
    depart(page, transition)
    before = screen(page)
    settle(page, held, outcome, response, 'window.__raceDone')
    assert screen(page) == before
    assert page.evaluate('session.festival.saving') is False
    assert page.evaluate('session.festival.verified === true') is (outcome == 'success')
    assert all(w['csrf'] == 'fixture-csrf' for w in server['writes'])


@pytest.mark.parametrize('outcome', ['success', 'error'])
@pytest.mark.parametrize('transition', ['home', 'review', 'close', 'escape', 'back'])
@pytest.mark.parametrize('boundary', ['write', 'readback'])
def test_delayed_preference_save_does_not_reopen_departed_screen(candidate, server, outcome, transition, boundary):
    page = candidate
    complete(page)
    visit_three(page)
    page.evaluate('async()=>{await session.festival.presentation_queue}')
    page.get_by_role('button', name='전체 리포트 보기', exact=True).click()
    page.locator('#dialog .preference-card').nth(1).click()
    pattern = '**/preference' if boundary == 'write' else '**/attempts/fixture-attempt'
    held = hold(page, pattern)
    page.evaluate('window.__raceDone=false;window.__raceOriginal=festivalConfirmPreference;festivalConfirmPreference=function(){return window.__raceOriginal().finally(()=>window.__raceDone=true)};void 0')
    with page.expect_request(pattern):
        page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    page.wait_for_function('session.festival.submitting')
    assert len(held) == 1
    response = held[0].fetch().json()
    depart(page, transition)
    before = screen(page)
    settle(page, held, outcome, response, 'window.__raceDone')
    assert screen(page) == before
    assert page.evaluate('session.festival.submitting') is False
    assert page.evaluate('session.festival.acknowledged') is (outcome == 'success')
    if outcome == 'success':
        assert page.evaluate('session.festival.preference.selected_village_id') == server['attempt']['preference']['selected_village_id']
    assert all(w['csrf'] == 'fixture-csrf' for w in server['writes'])


@pytest.mark.parametrize('outcome', ['success', 'error'])
@pytest.mark.parametrize('transition', ['home', 'review', 'close', 'back'])
def test_delayed_restore_does_not_reopen_departed_screen(candidate, server, outcome, transition):
    page = candidate
    complete(page)
    page.evaluate('async()=>{await session.festival.presentation_queue}')
    response = json.loads(json.dumps(server['attempt']))
    page.evaluate('view="festival-saving";render()')
    held = hold(page, '**/attempts/fixture-attempt')
    with page.expect_request('**/attempts/fixture-attempt'):
        page.evaluate('window.__raceDone=false;festivalRestoreAttempt("fixture-attempt").finally(()=>window.__raceDone=true);void 0')
    depart(page, transition)
    before = screen(page)
    state = page.evaluate('JSON.stringify(session)')
    settle(page, held, outcome, response, 'window.__raceDone')
    assert screen(page) == before
    assert page.evaluate('JSON.stringify(session)') == state


def test_current_operations_still_open_results_report_and_restored_report(candidate, server):
    page = candidate
    complete(page)
    assert page.evaluate('view') == 'result'
    assert page.evaluate('session.festival.verified') is True
    visit_three(page)
    page.get_by_role('button', name='전체 리포트 보기', exact=True).click()
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    page.locator('.journey-report').wait_for()
    assert page.evaluate('session.festival.acknowledged') is True
    page.reload()
    page.wait_for_function('session?.festival?.verified === true')
    assert page.evaluate('view') == 'result'
    page.evaluate('printResult()')
    page.locator('.journey-report').wait_for()


@pytest.mark.parametrize('case', [
    'test_server_score_disagreement_never_displays_result',
    'test_student_attempt_failure_and_presentation_retry',
    'test_student_save_ack_failure_retry_dedup_and_exact_payload',
    'test_stale_presentation_queue_never_writes_after_new_session',
    'test_student_import_never_trusts_client_preference_ack',
])
def test_existing_safety_gates_against_candidate(candidate, server, case):
    # Reuse the reviewed assertions, but serve this task's source overlay.
    import test_momotown
    getattr(test_momotown, case)(candidate, server)
