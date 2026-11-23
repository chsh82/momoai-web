import json
import pytest
from playwright.sync_api import sync_playwright,expect
from conftest import BASE,ROOT,create
OUT=ROOT/'reports/result-library-20261121'


def test_open_layer_account_switch_cannot_save_previous_accounts_draft(live):
    app,c,origin=live
    from pathlib import Path
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.goto(origin+'/host/search')
        page.locator('#entry').click()
        page.wait_for_function("document.querySelector('#interest-layer iframe').contentWindow.festivalIdentity?.identity_key==='u1'")
        frame=page.frames[1]
        frame.evaluate('init();session.values=qaSampleValues("lab")')
        page.request.get(origin+'/__fixture_login/u2')
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/attempts')) as response:
            frame.evaluate('void finish()')
        assert response.value.status==409
        assert not Path(app.config['MOMOTOWN_FEEDBACK_DB']).exists()
        frame.evaluate('void loadFestivalContext()')
        frame.wait_for_function("window.festivalIdentity?.identity_key==='u2'")
        assert frame.evaluate('session===null || session.values.every(v=>v===null)')
        browser.close()


def test_parent_reopen_revalidates_revoked_child_link(live):
    from conftest import db,ParentStudent
    app,c,origin=live;saved=create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        page.goto(origin+'/__fixture_login/p1');page.goto(origin+'/host/parent')
        page.locator('#child-entry').click()
        frame=page.frame_locator('#interest-layer iframe')
        frame.get_by_role('link',name='격리 학생 <태그>').click()
        frame.locator('[data-attempt]').get_by_role('link',name='레포트 보기').click()
        expect(frame.locator('#stored-report')).to_contain_text(saved['attempt_id'])
        page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
        with app.app_context():
            db.session.get(ParentStudent,'r1').is_active=False;db.session.commit()
        page.locator('#child-entry').click()
        expect(frame.get_by_role('heading',name='자녀 탐색 결과')).to_be_visible()
        expect(frame.locator('#stored-report')).to_have_count(0)
        expect(frame.get_by_role('status')).to_contain_text('조회 가능한 자녀가 없어요')
        browser.close()



def test_escape_cancels_pending_layer_open(live):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.goto(origin+'/host/search')
        held=[]
        page.route('**'+BASE+'/context',lambda route:held.append((route,route.fetch())))
        page.locator('#entry').click()
        expect(page.locator('#interest-layer-status')).to_contain_text('확인')
        page.keyboard.press('Escape')
        assert held
        route,response=held.pop();route.fulfill(response=response)
        page.wait_for_timeout(100)
        expect(page.locator('#interest-layer')).not_to_be_visible()
        browser.close()


def test_report_header_returns_to_retained_draft_and_warns_on_refresh(live):
    app,c,origin=live;create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1')
        page.wait_for_function("window.festivalIdentity?.mode==='student'")
        page.evaluate('init();continueJourney()')
        page.locator('.option').first.click()
        answers=page.evaluate('session.values')
        page.evaluate('momoOpenStoredResults()')
        page.frame_locator('#dialog iframe').get_by_role('link',name='닫기 · 모모아이로 돌아가기',exact=True).click()
        expect(page.locator('#dialog')).not_to_be_visible()
        assert page.evaluate('session.values')==answers
        assert page.evaluate('view')=='question'
        with page.expect_event('dialog') as prompt:
            page.evaluate('setTimeout(()=>location.reload(),0)')
        assert prompt.value.type=='beforeunload'
        prompt.value.dismiss()
        assert page.evaluate('session.values')==answers
        browser.close()


def test_completed_in_same_page_gets_latest_report_entry(live):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1')
        page.wait_for_function("window.festivalIdentity?.mode==='student'")
        page.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();await session.festival.presentation_queue;goHome();}')
        expect(page.get_by_role('button',name='최신 저장 결과 바로 보기',exact=True)).to_be_visible()
        assert '기록은 현재 페이지에만' not in page.locator('#main').inner_text()
        browser.close()


def test_student_start_library_and_safe_direct_return(live):
    app,c,origin=live
    saved=create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1')
        page.wait_for_function("window.festivalIdentity?.mode==='student'")
        expect(page.locator('#momo-return')).to_be_visible()
        expect(page.locator('#saved-results-entry')).to_contain_text('내 결과 보기')
        page.get_by_role('button',name='최신 저장 결과 바로 보기',exact=True).click()
        inner=page.frame_locator('#dialog iframe')
        expect(inner.locator('#stored-report')).to_contain_text(saved['attempt_id'])
        page.locator('#dialog').press('Escape')
        page.goto(origin+BASE+'/?return_to=https://example.invalid/evil')
        page.wait_for_function("window.festivalIdentity?.mode==='student'")
        assert page.locator('#momo-return').get_attribute('href')=='/'
        page.goto(origin+BASE+'/?return_to=%2Fstudent%2F%3Fq%3Dkept')
        page.wait_for_function("window.festivalIdentity?.mode==='student'")
        assert page.locator('#momo-return').get_attribute('href')=='/student/?q=kept'
        browser.close()


def test_layer_return_draft_inner_escape_and_account_isolation(live):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.goto(origin+'/__fixture_login/u1')
        assert page.request.get(origin+BASE+'/context').json().get('identity_key')=='u1'
        for host in ('courses','search'):
            page.goto(origin+'/host/'+host+'?q=kept')
            page.locator('#filter').fill(host)
            page.locator('#entry').scroll_into_view_if_needed()
            scroll=page.evaluate('scrollY')
            page.locator('#entry').click()
            expect(page.locator('#interest-layer')).to_have_attribute('open','')
            frame=page.frame_locator('#interest-layer iframe[data-exploration]')
            frame.locator('#main').wait_for()
            page.wait_for_function("document.querySelector('#interest-layer iframe').contentWindow.festivalIdentity?.mode==='student'")
            child=page.frames[1]
            child.evaluate('init();continueJourney()')
            frame.locator('.option').first.click()
            values=child.evaluate('session.values')
            child.evaluate("showManagement()")
            frame.locator('#dialog').press('Escape')
            expect(frame.locator('#dialog')).not_to_be_visible()
            expect(page.locator('#interest-layer')).to_be_visible()
            page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
            expect(page.locator('#interest-layer')).not_to_be_visible()
            assert page.evaluate('document.activeElement.id')=='entry'
            assert abs(page.evaluate('scrollY')-scroll)<2
            assert page.locator('#filter').input_value()==host
            assert page.url.endswith('/host/'+host+'?q=kept')
            page.locator('#entry').click()
            expect(page.locator('#interest-layer')).to_be_visible()
            assert page.frames[1].evaluate('session.values')==values
            page.screenshot(path=str(OUT/('layer-'+host+'-desktop.png')))
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(OUT/'layer-mobile.png'))
            assert page.locator('#interest-layer').bounding_box()['width']<=390
            assert page.locator('.interest-layer-chrome p').evaluate('(p)=>p.getBoundingClientRect().bottom<=p.parentElement.parentElement.getBoundingClientRect().bottom')
            assert not frame.locator('#momo-return').is_visible()
            page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
            page.set_viewport_size({'width':1440,'height':1000})
        # Same browser cookie changes while the original parent page stays mounted.
        page.request.get(origin+'/__fixture_login/u2')
        page.locator('#entry').click()
        expect(page.locator('#interest-layer')).to_be_visible()
        page.wait_for_function("document.querySelector('#interest-layer iframe').contentWindow.festivalIdentity?.identity_key==='u2'")
        assert page.frames[1].evaluate('session===null || session.values.every(v=>v===null)')
        browser.close()
