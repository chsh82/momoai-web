"""Independent review SEC-01: real Chromium, actual cookie changes and HTML routes."""
from pathlib import Path
import os
from uuid import uuid4
import pytest
from playwright.sync_api import sync_playwright, expect
from conftest import BASE, create, backend, store

OUT=Path(os.environ.get('RESULT_LIBRARY_EVIDENCE', Path(__file__).resolve().parents[2]/'reports/reviewfix-20261121/assets'))

def shot(page,name):
    OUT.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(OUT/(name+'.png')))

def seed_other(app):
    with app.app_context():
        answers=[q['options'][1]['id'] for q in backend.canonical_form()['items']]
        return store.create('s2',dict(request_id=str(uuid4()),form_version=backend.FORM_VERSION,answers=answers),backend.analyze(answers))

def test_old_draft_cannot_open_replacement_accounts_library(live):
    app,c,origin=live;create(app);other=seed_other(app)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.wait_for_function("festivalIdentity.identity_key==='u1'")
        page.evaluate('init();session.values[0]=FORM.items[0].options[0].id')
        page.request.get(origin+'/__fixture_login/u2')
        page.evaluate('momoOpenStoredResults()')
        page.wait_for_timeout(400)
        assert page.locator('#dialog iframe').count()==0, 'old A shell must never embed current B library'
        assert page.evaluate('session===null')
        assert page.locator('#print-root').inner_html()==''
        shot(page,'account-switch-blocked')
        browser.close()

@pytest.mark.parametrize('navigation',['detail','print','page','new'])
def test_already_open_report_navigation_stays_bound_after_cookie_switch(live,navigation):
    app,c,origin=live
    for _ in range(21):saved=create(app)
    seed_other(app)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.wait_for_function("festivalIdentity.identity_key==='u1'")
        page.evaluate('momoOpenStoredResults()')
        frame=page.frame_locator('#dialog iframe')
        expect(frame.locator('[data-attempt]').first).to_be_visible()
        if navigation=='print':
            frame.get_by_role('link',name='레포트 보기').first.click()
            expect(frame.locator('#stored-report')).to_be_visible()
            link=None  # The detail route also serves /print; print button itself uses native print.
        elif navigation=='detail':link=frame.get_by_role('link',name='레포트 보기').first
        elif navigation=='page':link=frame.get_by_role('link',name='다음 페이지')
        else:link=frame.get_by_role('link',name='새로 탐험하기',exact=True)
        child=next(f for f in page.frames if f.parent_frame==page.main_frame)
        href=link.evaluate('(a)=>a.href').removeprefix(origin) if link else child.url.removeprefix(origin)
        assert 'expected_identity=u1' in href, 'every HTML navigation must preserve the original account binding'
        page.request.get(origin+'/__fixture_login/u2')
        response=page.request.get(origin+href)
        assert response.status==409
        # Force native iframe navigation as well (new journey is normally intercepted).
        child=next(f for f in page.frames if f.parent_frame==page.main_frame)
        assert child.goto(origin+href).status==409
        assert child.locator('[data-attempt],#stored-report').count()==0
        shot(page,'bound-navigation-'+navigation)
        browser.close()

def test_stale_context_check_cannot_open_after_close(live):
    app,c,origin=live;create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();held=[]
        page.goto(origin+'/__fixture_login/u1');page.wait_for_function("festivalIdentity.identity_key==='u1'")
        page.route('**'+BASE+'/context',lambda r:held.append((r,r.fetch())))
        page.evaluate('void momoOpenStoredResults()')
        for _ in range(100):
            if held:break
            page.wait_for_timeout(20)
        assert held, 'library opening must recheck authenticated identity'
        page.evaluate('closeDialog()')
        held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
        assert page.locator('#dialog iframe').count()==0
        browser.close()
