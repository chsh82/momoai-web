"""LOGIC-01: release real POST/readback only AFTER same draft was reopened."""
import pytest
from playwright.sync_api import sync_playwright,expect
from conftest import BASE
from test_async import open_layer
from test_reviewfix_security import shot

def hold(page,target,method):
    held=[];writes=[]
    def intercept(route):
        if route.request.method=='POST':writes.append(route.request.post_data)
        if route.request.method==method and not held:held.append((route,route.fetch()))
        else:route.continue_()
    page.route('**'+target,intercept)
    return held,writes

def wait_held(page,held):
    for _ in range(100):
        if held:return
        page.wait_for_timeout(20)
    assert held

def release(held,failure):
    route,response=held[0]
    if failure:route.fulfill(status=503,body='fixture transport failure after real server request')
    else:route.fulfill(response=response)

@pytest.mark.parametrize('preference',[False,True])
@pytest.mark.parametrize('boundary',['post','readback'])
@pytest.mark.parametrize('failure',[False,True])
def test_reopened_pending_operation_reconciles_completion(live,preference,boundary,failure):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();frame=open_layer(page,origin)
        if preference:
            frame.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();}')
            for text in ('학과·직업·공부','두 번째 마을','세 번째 마을','비교와 리포트'):
                frame.get_by_role('tab').filter(has_text=text).click()
            frame.evaluate('async()=>await session.festival.presentation_queue')
            frame.evaluate('printResult()');frame.locator('.preference-card').first.click()
            attempt=frame.evaluate('session.festival.attempt_id')
            target=BASE+'/attempts/'+attempt+('/preference' if boundary=='post' else '')
        else:target=BASE+'/attempts'+('' if boundary=='post' else '/*')
        held,writes=hold(page,target,'POST' if boundary=='post' else 'GET')
        if preference:frame.locator('#festival-confirm').click()
        else:frame.evaluate('init();session.values=qaSampleValues("lab");void finish()')
        wait_held(page,held)
        page.locator('#interest-layer-close').click();page.locator('#entry').click()
        expect(page.locator('#interest-layer')).to_be_visible()
        release(held,failure)
        frame.wait_for_function('!session.festival.saving&&!session.festival.submitting')
        if preference:
            expect(frame.locator('#festival-confirm')).to_be_enabled()
            assert frame.evaluate('!!session.festival.acknowledged') is (not failure)
        elif failure:expect(frame.get_by_role('button',name='결과 저장 다시 시도',exact=True)).to_be_enabled()
        else:expect(frame.get_by_role('tab').first).to_be_visible()
        if failure:
            expect(frame.locator('#festival-save-status' if preference else '#festival-attempt-status')).to_contain_text('서버 저장')
        assert len(writes)==(1 if boundary=='post' else 0), 'resume must not retry writes'
        shot(page,f'resume-{preference}-{boundary}-{failure}')
        browser.close()

@pytest.mark.parametrize('departure',['close','home','new'])
def test_reopened_request_cannot_navigate_after_subsequent_departure(live,departure):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();frame=open_layer(page,origin)
        held,writes=hold(page,BASE+'/attempts','POST')
        frame.evaluate('init();session.values=qaSampleValues("lab");void finish()');wait_held(page,held)
        page.locator('#interest-layer-close').click();page.locator('#entry').click()
        expect(page.locator('#interest-layer')).to_be_visible()
        if departure=='close':page.locator('#interest-layer-close').click()
        elif departure=='home':frame.evaluate('goHome()')
        else:frame.evaluate('init()')
        before=frame.evaluate('JSON.stringify([view,session?.values,location.hash])')
        release(held,False);page.wait_for_timeout(350)
        assert frame.evaluate('JSON.stringify([view,session?.values,location.hash])')==before
        if departure=='close':expect(page.locator('#interest-layer')).not_to_be_visible()
        assert len(writes)==1
        browser.close()
