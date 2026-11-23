"""LOGIC-02: actual new-journey anchor, parent draft confirmation and host entry."""
import pytest
from playwright.sync_api import sync_playwright,expect
from conftest import BASE,create
from test_async import open_layer
from test_reviewfix_security import shot

@pytest.mark.parametrize('accept',[False,True])
def test_library_new_uses_parent_confirmation_not_nested_exploration(live,accept):
    app,c,origin=live;create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.wait_for_function("festivalIdentity.identity_key==='u1'")
        page.evaluate('init();session.values[0]=FORM.items[0].options[0].id')
        old=page.evaluate('JSON.stringify(session.values)');dialogs=[]
        page.on('dialog',lambda d:(dialogs.append(d.type), d.accept() if accept else d.dismiss()))
        page.evaluate('momoOpenStoredResults()')
        child=page.frame_locator('#dialog iframe')
        child.get_by_role('link',name='새로 탐험하기',exact=True).click();page.wait_for_timeout(200)
        assert dialogs==['confirm'], 'actual library anchor must delegate to the parent draft guard'
        if accept:
            expect(page.locator('#dialog')).not_to_be_visible()
            assert page.evaluate('session.values.every(v=>v===null)')
        else:
            assert page.evaluate('JSON.stringify(session.values)')==old
            expect(child.get_by_role('heading',name='내 탐색 결과',exact=True)).to_be_visible()
        assert not any(f.url.split('?')[0].endswith(BASE+'/') for f in page.frames[1:])
        shot(page,'new-journey-'+str(accept));browser.close()

def test_standalone_library_new_is_normal_navigation(live):
    app,c,origin=live
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(origin+'/__fixture_login/u1');page.goto(origin+BASE+'/reports')
        page.get_by_role('link',name='새로 탐험하기',exact=True).click()
        page.wait_for_function("window.festivalIdentity?.identity_key==='u1'")
        assert page.url.split('?')[0]==origin+BASE+'/'
        assert len(page.frames)==1
        browser.close()

@pytest.mark.parametrize('retained',[False,True])
@pytest.mark.parametrize('accept',[False,True])
def test_host_direct_library_new_routes_to_single_guarded_exploration(live,retained,accept):
    app,c,origin=live;create(app)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        if retained:
            exploration=open_layer(page,origin)
            exploration.evaluate('init();session.values[0]=FORM.items[0].options[0].id')
            old=exploration.evaluate('JSON.stringify(session.values)')
            page.locator('#interest-layer-close').click()
        else:
            page.goto(origin+'/__fixture_login/u1');page.goto(origin+'/host/search')
        page.locator('#child-entry').evaluate('(a,path)=>a.href=path',BASE+'/reports')
        page.locator('#child-entry').click()
        library=page.frame_locator('#interest-layer iframe:not([hidden])')
        expect(library.get_by_role('heading',name='내 탐색 결과',exact=True)).to_be_visible()
        dialogs=[];page.on('dialog',lambda d:(dialogs.append(d.type),d.accept() if accept else d.dismiss()))
        library.get_by_role('link',name='새로 탐험하기',exact=True).click();page.wait_for_timeout(300)
        assert dialogs==(['confirm'] if retained else [])
        if retained and not accept:
            assert exploration.evaluate('JSON.stringify(session.values)')==old
            expect(library.get_by_role('heading',name='내 탐색 결과',exact=True)).to_be_visible()
        else:
            visible=page.locator('#interest-layer iframe:not([hidden])')
            assert visible.get_attribute('data-exploration') is not None
            exploration=next(f for f in page.frames[1:] if f.url.split('?')[0]==origin+BASE+'/')
            exploration.wait_for_function('session?.values.every(v=>v===null)')
        assert all(len(f.child_frames)==0 for f in page.frames[1:])
        shot(page,f'host-new-{retained}-{accept}');browser.close()
