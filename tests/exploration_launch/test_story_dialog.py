from test_story_v3 import page

def test_modal_auxiliary_navigation_is_accessible(page):
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    page.get_by_role('button',name='마을 지도 둘러보기',exact=True).click()
    page.locator('.map-pin').first.click()
    dialog=page.locator('#dialog')
    assert dialog.get_by_role('button',name='첫 화면으로',exact=True).count()==1
    assert dialog.get_by_role('button',name='탐험 시작하기',exact=True).count()==1
    dialog.get_by_role('button',name='첫 화면으로',exact=True).click()
    assert not dialog.is_visible()
    assert page.locator('.launch-intro').count()==1
