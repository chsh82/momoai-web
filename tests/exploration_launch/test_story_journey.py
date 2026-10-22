from test_story_v3 import page, ROOT, OUT
import pytest
@pytest.mark.parametrize('width',[390,1440])
def test_full_journey_reveal_and_new_five_steps(page,width):
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_viewport_size({'width':width,'height':950})
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    page.get_by_role('button',name='탐험 시작하기',exact=True).first.click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    for i in range(32):
        if page.locator('.chapter-screen').count():
            page.screenshot(path=str(OUT/f'chapter-{width}-{i//8+1}.png'),full_page=True)
            page.locator('.chapter-actions button').first.click()
        page.locator('input[type=radio]').nth(i%4).check()
        page.locator('#next').click()
    assert page.locator('[data-story="anticipation"]').count()==1
    assert page.locator('.review-grid').count()==0
    page.get_by_role('button',name='나의 마을 만나기',exact=True).click()
    for i,step in enumerate(['core','connections','second','third','compare']):
        assert page.locator('#result-progress').inner_text()==f'{i+1} / 5'
        assert page.locator('#result-panel').get_attribute('data-step')==step
        assert page.locator('.method,.quest-select').count()==0
        assert page.locator('#main a[href^="http"]').count()==0
        if i==0:
            assert page.locator('#result-panel .village-discovery').count()==1
            assert page.locator('#result-panel table').count()==0
        page.screenshot(path=str(OUT/f'result-{width}-{i+1}.png'),full_page=True)
        if i<4: page.get_by_role('button',name='다음 단계',exact=True).click()
    page.get_by_role('button',name='선택한 응답 수정',exact=True).click()
    page.get_by_role('button',name='1번 수정',exact=True).click()
    page.locator('input[type=radio]').nth(1).check()
    page.locator('#next').click()
    page.get_by_role('button',name='수정한 결과 보기',exact=True).first.click()
    assert page.evaluate('JSON.stringify(session.result)===JSON.stringify(InterestScoring.score(responseRows(session),FORM))')
    assert errors==[]
