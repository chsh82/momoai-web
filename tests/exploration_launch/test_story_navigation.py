from test_story_v3 import page,ROOT,OUT
import pytest

def test_public_navigation_has_no_internal_method_and_intro_roadmap(page):
    assert page.locator('button[onclick*="showMethod"]').count()==0
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    assert page.locator('.story-roadmap li').count()==5
    page.get_by_role('button',name='모모의 초대 다시 보기',exact=True).click()
    assert page.locator('[data-story="greeting"]').count()==1
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    for name in ['마을 전체 지도','이야기 친구 만나기']:
        page.get_by_role('button',name=name,exact=True).first.click()
        assert page.get_by_role('button',name='첫 화면으로',exact=True).is_visible()
        assert page.get_by_role('button',name='탐험 시작하기',exact=True).is_visible()
        assert '자료 출처와 결과 계산 방법' not in page.locator('body').inner_text()
        page.go_back()
        assert page.locator('.launch-intro').count()==1

@pytest.mark.parametrize('width',[320,390,768,1440])
def test_no_body_overflow_all_primary_views(page,width):
    page.set_viewport_size({'width':width,'height':900})
    page.emulate_media(reduced_motion='reduce')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(OUT/f'intro-{width}.png'),full_page=True)
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.evaluate('enableLocalStoryQA();showSamples()')
    page.locator('.sample-choice').first.click()
    for i in range(6):
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        for b in page.locator('.launch-pager button').all():
            assert b.bounding_box()['height']>=44
        if i<5: page.get_by_role('button',name='다음 단계',exact=True).click()
    # Chromium CSS zoom verifies 200% reflow, not OS/browser chrome zoom.
    page.evaluate('document.body.style.zoom="2"')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
