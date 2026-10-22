"""Real Chromium clicks; file-only quest, locally rendered compass, external traffic blocked."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/exploration-story-v3'

@pytest.fixture
def browser_page():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(accept_downloads=True)
        context.route('http://**/*', lambda route: route.abort())
        context.route('https://**/*', lambda route: route.abort())
        page=context.new_page()
        yield page
        browser.close()

@pytest.mark.parametrize('width',[390,1440])
def test_quest_five_step_clicks(browser_page,width):
    page=browser_page
    page.set_viewport_size({'width':width,'height':900})
    page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
    page.get_by_role('button',name='결과 예시',exact=True).click()
    page.locator('.sample-choice').first.click()
    ids=['core','connections','second','third','compare']
    for i,tab in enumerate(ids):
        assert page.locator('#result-progress').inner_text()==f'{i+1} / 5'
        assert page.locator('#tab-'+tab).get_attribute('aria-selected')=='true'
        assert page.locator('#result-panel').get_attribute('aria-labelledby')=='tab-'+tab
        assert page.locator('#result-panel').get_attribute('data-step')==tab
        if i==0:
            assert page.locator('#result-panel .village-discovery').count()==1
            assert page.locator('#result-panel table').count()==0
        elif i==1: assert page.locator('#result-panel .study-connections').count()==1
        elif i in (2,3): assert page.locator('#result-panel .compact').count()==1
        else: assert page.locator('#result-panel .story-comparison').count()==1
        page.screenshot(path=str(OUT/f'quest-{width}-step-{i+1}.png'))
        if i<4:
            page.get_by_role('button',name='다음 단계',exact=True).click()
            assert page.evaluate('document.activeElement.id')=='result-panel'
    assert page.get_by_role('button',name='다음 단계',exact=True).is_disabled()
    for i in range(3,-1,-1):
        page.get_by_role('button',name='이전 단계',exact=True).click()
        assert page.locator('#result-progress').inner_text()==f'{i+1} / 5'
    page.get_by_role('tab',name='4. 세 번째 마을',exact=True).click()
    assert page.locator('#result-panel').get_attribute('data-step')=='third'
    page.get_by_role('tab',name='3. 두 번째 마을',exact=True).focus()
    page.keyboard.press('Home')
    assert page.locator('#tab-core').get_attribute('aria-selected')=='true'
    page.keyboard.press('End')
    assert page.locator('#tab-compare').get_attribute('aria-selected')=='true'

def test_intro_memory_warning_and_file_save(browser_page):
    page=browser_page
    page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
    assert page.locator('[data-story="greeting"]').count()==1
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    assert page.locator('.launch-intro').count()==1
    assert page.locator('#main .world-map, #main .v12-map').count()==0
    assert page.get_by_role('button',name='기록 저장·불러오기',exact=True).count()==1
    assert '파일로 저장' in page.locator('#main').inner_text()
    page.get_by_role('button',name='탐험 시작하기',exact=True).click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    assert page.locator('.chapter-screen').count()==1
    page.locator('.chapter-actions button').first.click()
    page.locator('input[type=radio]').first.check()
    assert page.evaluate("(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented;})()")
    page.get_by_role('button',name='기록 저장·불러오기',exact=True).first.click()
    with page.expect_download() as download:
        page.get_by_role('button',name='현재 기록 파일 저장',exact=True).click()
    target=OUT/'real-partial-record.json'
    download.value.save_as(target)
    record=json.loads(target.read_text(encoding='utf-8'))
    assert record['data_origin']=='LOCAL_USER_INPUT'
    assert len([x for x in record['responses'] if x['option_id'] is not None])==1
    assert not page.evaluate("(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented;})()")

@pytest.mark.parametrize('width',[390,1440])
def test_compass_five_questions_preserve_answers(browser_page, width, tmp_path):
    from test_launch import make_web, Identity
    from flask_login import login_user
    from jinja2 import ChoiceLoader, DictLoader
    app,client=make_web()
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'<!doctype html><meta name="viewport" content="width=device-width"><style>[hidden]{display:none!important}body{font:18px sans-serif;max-width:850px;margin:auto;padding:16px}label{display:block;padding:12px}button{padding:12px}</style>{% block content %}{% endblock %}'}),app.jinja_loader])
    app.jinja_env.globals['csrf_token']=lambda:'test-csrf'
    with app.test_request_context('/student/interest-mid/quiz'):
        login_user(Identity('admin'))
        html=app.view_functions['interest_mid.quiz']()
    file=tmp_path/'compass.html'
    file.write_text(html,encoding='utf-8')
    page=browser_page
    page.set_viewport_size({'width':width,'height':900})
    page.goto(file.as_uri())
    assert page.locator('[data-question]:visible').count()==5
    assert page.locator('input[name=csrf_token]').input_value()=='test-csrf'
    page.get_by_role('button',name='다음 문항',exact=True).click()
    assert page.locator('#compass-progress').inner_text()=='1 / 8 · 1–5번'
    for step in range(8):
        assert page.locator('[data-question]:visible').count()==5
        assert page.locator('#compass-progress').inner_text()==f'{step+1} / 8 · {step*5+1}–{step*5+5}번'
        for i in range(step*5,step*5+5): page.locator(f'input[name=q{i}]').first.check()
        page.screenshot(path=str(OUT/f'compass-{width}-page-{step+1}.png'))
        if step<7: page.get_by_role('button',name='다음 문항',exact=True).click()
    assert page.get_by_role('button',name='제출하고 결과 보기',exact=True).is_visible()
    page.get_by_role('button',name='이전 문항',exact=True).click()
    assert page.locator('input[name=q30]').first.is_checked()
    assert page.locator('input:checked').count()==40
    page.get_by_role('button',name='다음 문항',exact=True).click()
    # Capture real form serialization instead of submitting a file:// form.
    data=page.locator('form').evaluate('(f)=>Object.fromEntries(new FormData(f))')
    assert all(data[f'q{i}']=='0' for i in range(40))

@pytest.mark.parametrize('width',[390,1440])
def test_real_journey_sample_separation_export_import_print(browser_page,width):
    page=browser_page
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_viewport_size({'width':width,'height':900})
    page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
    page.get_by_role('button',name='탐험 시작하기',exact=True).click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    for i in range(32):
        if page.locator('.chapter-screen').count(): page.locator('.chapter-actions button').first.click()
        page.locator('input[type=radio]').nth(i%4).check()
        page.locator('#next').click()
    page.get_by_role('button',name='나의 마을 만나기',exact=True).click()
    real=page.evaluate('session.values.slice()')
    score=page.evaluate('JSON.stringify(session.result)')
    assert page.locator('#result-progress').inner_text()=='1 / 5'
    for tab in ['connections','second','third','compare']:
        page.locator('#tab-'+tab).click()
        assert page.locator('#result-panel').get_attribute('data-step')==tab

    with page.expect_download() as download:
        page.get_by_role('button',name='기록 파일 저장',exact=True).click()
    saved=OUT/f'real-record-{width}.json'
    download.value.save_as(saved)
    record=json.loads(saved.read_text(encoding='utf-8'))
    assert record['data_origin']=='LOCAL_USER_INPUT'
    assert len(record['responses'])==32
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    assert page.locator('.journey-report').count()==1
    assert page.locator('.journey-report .response-appendix').count()==1
    page.evaluate('window.print=()=>{window.printCalled=true}')
    page.locator('#include-appendix').check()
    page.get_by_role('button',name='인쇄 또는 PDF 저장',exact=True).click()
    assert page.evaluate('window.printCalled')
    assert page.locator('#print-root .response-appendix').get_attribute('open') is not None
    page.emulate_media(media='print')
    page.pdf(path=str(OUT/f'real-report-{width}.pdf'),format='A4',print_background=True)
    page.emulate_media(media='screen')
    page.get_by_role('button',name='결과로 돌아가기',exact=True).click()
    for index in range(4):
        page.get_by_role('button',name='결과 예시',exact=True).click()
        page.locator('.sample-choice').nth(index).click()
        assert '가상 예시' in page.locator('.banner').inner_text()
        assert page.evaluate('session.values')==real
        page.locator('#tab-compare').click()
        with page.expect_download() as download:
            page.get_by_role('button',name='기록 파일 저장',exact=True).click()
        target=OUT/f'sample-{width}-{index}.json'
        download.value.save_as(target)
        assert json.loads(target.read_text(encoding='utf-8'))['data_origin']=='SYNTHETIC_EXAMPLE'
    page.get_by_role('button',name='기록 저장·불러오기',exact=True).click()
    page.locator('#record-file').set_input_files(str(saved))
    # Importing a real record must explicitly confirm replacing in-memory input.
    page.get_by_role('button',name='불러오기',exact=True).click()
    assert page.evaluate('session.values')==real
    assert page.evaluate('JSON.stringify(session.result)')==score
    assert '가상 예시' not in page.locator('.banner').inner_text()
    page.screenshot(path=str(OUT/f'real-{width}-roundtrip.png'))
    page.locator('#record-file').set_input_files(str(OUT/f'sample-{width}-3.json'))
    page.wait_for_function("view==='sample'")
    assert '가상 예시' in page.locator('.banner').inner_text()
    assert page.evaluate('session.values')==real
    page.locator('#tab-compare').click()
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    assert '가상 예시' in page.locator('#main .report-origin').inner_text()
    page.locator('#include-appendix').uncheck()
    page.get_by_role('button',name='인쇄 또는 PDF 저장',exact=True).click()
    assert page.locator('#print-root .response-appendix').count()==0
    assert errors==[]

def test_canonical_form_and_scoring_equal_head(browser_page,tmp_path):
    import subprocess,hashlib
    page=browser_page
    original=subprocess.check_output(['git','-C',str(ROOT),'show','HEAD:app/interest_quest/protected/index.html'])
    baseline=tmp_path/'baseline.html'
    baseline.write_bytes(original)
    script="""(()=>({form:FORM, scores:Array.from({length:128},(_,seed)=>{let x=seed+1;const answers=FORM.items.map((q,i)=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return {item_id:q.id,option_id:q.options[(x>>>16)%4].id};});return InterestScoring.score(answers,FORM);})}))()"""
    page.goto(baseline.as_uri())
    expected=page.evaluate(script)
    page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
    actual=page.evaluate(script)
    assert actual==expected
    unique=len({json.dumps(s,sort_keys=True) for s in actual['scores']})
    assert unique==128
    data=json.dumps(actual,sort_keys=True,ensure_ascii=False).encode()
    (OUT/'scoring-equivalence.json').write_text(json.dumps({'baseline':'d4182ff:app/interest_quest/protected/index.html','canonical_form_equal':True,'score_cases':128,'unique_results':unique,'equal':True,'sha256':hashlib.sha256(data).hexdigest()},indent=2),encoding='utf-8')

def test_future_evidence_is_optional_not_repeated_long_page(browser_page):
    page=browser_page
    page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
    page.get_by_role('button',name='결과 예시',exact=True).click()
    page.locator('.sample-choice').first.click()
    page.locator('#tab-connections').click()
    assert page.locator('.study-connections').count()==1
    assert page.locator('#result-panel blockquote:visible').count()==0
    assert page.locator('.method,.inquiry-example9,.quest-select').count()==0
