"""Hold actual blueprint responses, never synthesize a successful API contract."""
import pytest
from playwright.sync_api import sync_playwright,expect
from conftest import BASE,create

def open_layer(page,origin,hash=''):
    page.goto(origin+'/__fixture_login/u1')
    page.goto(origin+'/host/search')
    if hash:page.locator('#entry').evaluate('(a,hash)=>a.hash=hash',hash)
    page.locator('#entry').click()
    expect(page.locator('#interest-layer')).to_be_visible()
    page.wait_for_function("document.querySelector('#interest-layer iframe').contentWindow.festivalIdentity?.mode==='student'")
    return next(f for f in page.frames if BASE+'/' in f.url)

@pytest.mark.parametrize('boundary',['post','readback'])
@pytest.mark.parametrize('failure',[False,True])
def test_close_while_saving_never_reopens_outer_or_navigates(live,boundary,failure):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page();frame=open_layer(page,origin)
        held=[]
        def intercept(route):
            wanted=route.request.method==('POST' if boundary=='post' else 'GET')
            if wanted and not held:held.append((route,route.fetch()))
            else:route.continue_()
        page.route('**'+BASE+'/attempts'+('' if boundary=='post' else '/*'),intercept)
        frame.evaluate('init();session.values=qaSampleValues("lab");void finish()')
        frame.wait_for_function('session?.festival?.saving===true')
        for _ in range(100):
            if held:break
            page.wait_for_timeout(20)
        assert held
        page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
        expect(page.locator('#interest-layer')).not_to_be_visible()
        before=frame.evaluate('view')
        route,response=held[0]
        if failure:route.fulfill(status=503,content_type='application/json',body='{"error":"fixture transport failure after real server request"}')
        else:route.fulfill(response=response)
        frame.wait_for_function('session.festival.saving===false')
        assert frame.evaluate('view')==before
        assert not frame.locator('#dialog').is_visible()
        expect(page.locator('#interest-layer')).not_to_be_visible()
        assert page.url.endswith('/host/search')
        if not failure:
            assert frame.evaluate('session.festival.verified') is True
            page.locator('#entry').click()
            expect(page.locator('#interest-layer')).to_be_visible()
            expect(frame.get_by_role('tab').first).to_be_visible()
        browser.close()

@pytest.mark.parametrize('boundary',['post','readback'])
@pytest.mark.parametrize('failure',[False,True])
def test_preference_close_keeps_server_ack_without_late_report_navigation(live,boundary,failure):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page();frame=open_layer(page,origin)
        frame.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();}')
        for text in ('학과·직업·공부','두 번째 마을','세 번째 마을','비교와 리포트'):
            frame.get_by_role('tab').filter(has_text=text).click()
        frame.evaluate('async()=>await session.festival.presentation_queue')
        frame.evaluate('printResult()')
        frame.locator('#dialog .preference-card').first.click()
        attempt=frame.evaluate('session.festival.attempt_id');held=[]
        target=BASE+'/attempts/'+attempt+('/preference' if boundary=='post' else '')
        page.route('**'+target,lambda route:held.append((route,route.fetch())))
        frame.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
        for _ in range(100):
            if held:break
            page.wait_for_timeout(20)
        assert held
        page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
        before=frame.evaluate('view');route,response=held[0]
        if failure:route.fulfill(status=503,body='fixture failure after actual server response')
        else:route.fulfill(response=response)
        # A readback route is one-shot: no extra mutations should be needed to resume.
        frame.wait_for_function('session.festival.submitting===false')
        assert frame.evaluate('view')==before
        expect(page.locator('#interest-layer')).not_to_be_visible()
        if not failure:assert frame.evaluate('session.festival.acknowledged') is True
        page.unroute('**'+target)
        page.locator('#entry').click()
        expect(page.locator('#interest-layer')).to_be_visible()
        expect(frame.locator('#festival-confirm')).to_be_enabled()
        frame.locator('#dialog').press('Escape')
        expect(page.locator('#interest-layer')).to_be_visible()
        browser.close()


@pytest.mark.parametrize('failure',[False,True])
def test_close_while_restoring_discards_late_payload(live,failure):
    app,c,origin=live;saved=create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page();held=[]
        page.route('**'+BASE+'/attempts/'+saved['attempt_id'],lambda r:held.append((r,r.fetch())))
        frame=open_layer(page,origin,'attempt='+saved['attempt_id'])
        for _ in range(100):
            if held:break
            page.wait_for_timeout(20)
        assert held
        page.get_by_role('button',name='닫기 · 모모아이로 돌아가기',exact=True).click()
        before=frame.evaluate('JSON.stringify([session,view,location.hash])')
        route,response=held[0]
        if failure:route.fulfill(status=503,body='unavailable')
        else:route.fulfill(response=response)
        page.wait_for_timeout(100)
        assert frame.evaluate('JSON.stringify([session,view,location.hash])')==before
        expect(page.locator('#interest-layer')).not_to_be_visible()
        browser.close()
