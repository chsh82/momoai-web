from pathlib import Path
import hashlib
from playwright.sync_api import sync_playwright
from conftest import BASE,ROOT,create,backend
OUT=ROOT/'reports/result-library-20261121'

def test_read_only_library_parent_parity_and_native_pdf(live,monkeypatch):
    app,c,origin=live
    old=create(app);create(app,1)
    before=Path(app.config['MOMOTOWN_FEEDBACK_DB']).read_bytes()
    monkeypatch.setattr(backend,'analyze',lambda *a:(_ for _ in ()).throw(AssertionError('read path must never score')))
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.goto(origin+'/__fixture_login/u1')
        response=page.goto(origin+BASE+'/reports')
        assert response.status==200
        assert page.get_by_role('heading',name='내 탐색 결과').is_visible()
        assert page.locator('[data-attempt]').count()==2
        page.locator('[data-attempt="'+old['attempt_id']+'"]').get_by_role('link',name='레포트 보기').click()
        assert page.get_by_text('이전 회차',exact=True).is_visible()
        assert page.get_by_text('선호마을 미확정',exact=True).is_visible()
        assert page.get_by_text('응답 완료 · 서버 저장 확인',exact=True).is_visible()
        assert page.locator('[data-domain]').count()==9
        student_text=page.locator('#stored-report').inner_text()
        page.screenshot(path=str(OUT/'student-report-desktop.png'))
        page.pdf(path=str(OUT/'student-read-only-report.pdf'),format='A4',print_background=True)
        page.goto(origin+'/__fixture_login/p1')
        page.goto(origin+BASE+'/children')
        page.get_by_role('link',name='격리 학생 <태그>').click()
        page.locator('[data-attempt="'+old['attempt_id']+'"]').get_by_role('link',name='레포트 보기').click()
        assert page.locator('#stored-report').inner_text()==student_text
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'parent-report-mobile.png'))
        page.pdf(path=str(OUT/'parent-read-only-report.pdf'),format='A4',print_background=True)
        browser.close()
    assert Path(app.config['MOMOTOWN_FEEDBACK_DB']).read_bytes()==before
    import pymupdf
    with pymupdf.open(OUT/'student-read-only-report.pdf') as pdf:
        text=''.join(page.get_text() for page in pdf)
    assert '선호마을 미확정' in text
    assert '응답 완료' in text
    assert old['attempt_id'] in text
