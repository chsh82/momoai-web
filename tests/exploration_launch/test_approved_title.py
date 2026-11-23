"""Approved display-only title; real protected artifact in Chromium."""
from pathlib import Path
from test_story_v3 import page

TITLE = '전공마을 탐험'
SUBTITLE = '호기심으로 시작하는 관심 전공 탐색하기'
OUT = Path(__file__).resolve().parents[2]/'reports/major-village-title-20261116'

def test_approved_title_and_subtitle_on_entry(page):
    assert page.title() == TITLE
    assert page.locator('.brand strong').inner_text() == TITLE
    assert page.locator('.brand small').inner_text() == SUBTITLE
    page.get_by_role('button', name='안내 건너뛰기', exact=True).click()
    assert page.locator('.launch-intro h1').inner_text() == TITLE
    assert SUBTITLE in page.locator('.launch-intro').inner_text()
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT/'entry-desktop.png'), full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'entry-mobile.png'), full_page=True)

def test_approved_name_on_crumb_report_print_and_menu(page):
    from v02_helpers import open_report
    assert TITLE in page.evaluate('crumb("결과")')
    page.evaluate('enableLocalStoryQA();showSample("lab")')
    for tab in ['core','connections','bridge','second','third','compare']:
        page.evaluate('(tab)=>setTab(tab)', tab)
        assert page.locator('.brand strong').inner_text() == TITLE
    open_report(page)
    assert TITLE in page.locator('.journey-report .report-heading').inner_text()
    assert SUBTITLE in page.locator('.journey-report .report-heading').inner_text()
    for old in ['모모아이 전공마을 탐색','모모의 이야기 탐험단','모모타운 축제']:
        assert old not in page.locator('.brand').inner_text()
        assert old not in page.locator('.journey-report .report-heading').inner_text()
    page.screenshot(path=str(OUT/'report.png'), full_page=True)
    page.pdf(path=str(OUT/'native-report.pdf'), format='A4', print_background=True)
    assert TITLE in page.locator('#print-root .report-heading').inner_text()
    assert SUBTITLE in page.locator('#print-root .report-heading').inner_text()
    assert TITLE in page.locator('.footer').inner_text()
    base=(Path(__file__).resolve().parents[2]/'templates/base.html').read_text(encoding='utf8')
    assert '<span class="font-medium">전공마을 탐험</span>' in base

def test_all_32_choices_survive_previous_next(page):
    page.get_by_role('button', name='안내 건너뛰기', exact=True).click()
    page.get_by_role('button', name='초대받은 여행 떠나기', exact=True).click()
    page.get_by_role('button', name='첫 장면으로 가기 →', exact=True).click()
    page.locator('.chapter-actions button').first.click()
    selected=[]
    for index in range(32):
        assert page.evaluate('session.cursor') == index
        radios=page.locator('input[type=radio]')
        assert radios.count() == 4
        choice=radios.nth(index%4)
        selected.append(choice.get_attribute('value'))
        choice.check()
        if index:
            page.locator('button[onclick="previous()"]').click()
            assert page.evaluate('session.cursor') == index-1
            assert page.locator('input[type=radio]:checked').get_attribute('value') == selected[index-1]
            page.locator('#next').click()
            if page.locator('.chapter-screen').count():
                page.locator('.chapter-actions button').first.click()
            assert page.locator('input[type=radio]:checked').get_attribute('value') == selected[index]
        assert page.evaluate('session.values')[:index+1] == selected
        page.locator('#next').click()
        if page.locator('.chapter-screen').count():
            page.locator('.chapter-actions button').first.click()
    assert page.evaluate('view') == 'anticipation'
    assert page.evaluate('session.values') == selected
    page.screenshot(path=str(OUT/'all32-review.png'),full_page=True)
