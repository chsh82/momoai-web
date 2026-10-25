"""Story v3: real local Chromium, no application factory or network."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/exploration-v4/art-integration/regression'
OUT.mkdir(exist_ok=True,parents=True)
@pytest.fixture
def page():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(accept_downloads=True)
        context.route('http://**/*',lambda r:r.abort())
        context.route('https://**/*',lambda r:r.abort())
        page=context.new_page()
        # Large self-contained data images on a shared Windows host: allow load,
        # without weakening any DOM, scoring, provenance or network assertions.
        page.set_default_navigation_timeout(120000)
        errors=[]; attempted=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:attempted.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
        yield page
        assert errors==[],errors
        assert attempted==[],attempted
        browser.close()
def test_greeting_home_and_preserved_answers(page):
    assert page.locator('[data-story="greeting"]').count()==1
    for _ in range(3): page.get_by_role('button',name='다음 이야기',exact=True).click()
    page.get_by_role('button',name='초대장 펼치기',exact=True).click()
    assert page.locator('.launch-intro').count()==1
    page.get_by_role('button',name='탐험 시작하기',exact=True).first.click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    page.locator('.chapter-actions button').first.click()
    page.locator('input[type=radio]').first.check()
    answers=page.evaluate('session.values')
    page.get_by_role('button',name='첫 화면으로',exact=True).click()
    assert page.evaluate('session.values')==answers
    assert page.locator('[data-story="greeting"]').count()==0
    page.evaluate('enableLocalStoryQA();showSamples()')
    assert page.get_by_role('button',name='탐험 시작하기',exact=True).count()==1
    page.get_by_role('button',name='첫 화면으로',exact=True).click()
    assert page.evaluate('session.values')==answers
