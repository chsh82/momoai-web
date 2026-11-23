"""Real Chromium -> real Flask blueprint; no synthetic API responses."""
import json,sqlite3
from contextlib import closing
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from conftest import BASE,ROLES,ROOT
OUT=ROOT/'reports/major-village-members-20261116'
@pytest.fixture(scope='module')
def chromium():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);yield browser;browser.close()
@pytest.fixture
def page(chromium,live):
    ctx=chromium.new_context();page=ctx.new_page();page.set_default_timeout(8000)
    ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(live['origin']+'/') else route.abort())
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    yield page
    ctx.close();assert not errors

def choose_report(page):
    for text in ('학과·직업·공부','두 번째 마을','세 번째 마을','비교와 리포트'):
        page.get_by_role('tab').filter(has_text=text).click()
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    page.locator('#dialog .preference-card').nth(1).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()

@pytest.mark.parametrize('role',[r for r in ROLES if r!='student'])
def test_real_nonstudent_trial_report_json_native_pdf_without_any_post(page,live,role):
    page.goto(live['origin']+'/__login/'+role)
    mode='admin_preview' if role in ('admin','master_admin') else 'member_preview'
    page.wait_for_function('window.festivalIdentity.mode === '+json.dumps(mode))
    if mode=='member_preview':
        assert '회원 체험' in page.locator('#main').inner_text()
        assert '서버에 저장하지 않아요' in page.locator('#main').inner_text()
        assert '관리자' not in page.locator('#main').inner_text()
        page.evaluate('showManagement()')
        assert '서버에 저장하지 않아요' in page.locator('#dialog').inner_text()
        page.evaluate('closeDialog()')
    page.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();}')
    page.get_by_role('tab').first.wait_for();choose_report(page)
    if mode=='member_preview':
        assert '회원 체험' in page.locator('.journey-report').inner_text()
        assert page.evaluate('session.festival.preference.origin')=='MEMBER_PREVIEW'
    with page.expect_download() as download:page.evaluate('exportRecord()')
    export=OUT/(role+'-record.json');download.value.save_as(str(export));raw=json.loads(export.read_text(encoding='utf8'))
    assert raw['schema']=='momo-interest-record-v1'
    assert len(raw['responses'])==32 and raw['preference_snapshot']['attempt_id'] is None
    page.pdf(path=str(OUT/(role+'-native-report.pdf')),format='A4',print_background=True)
    if mode=='member_preview':
        import pymupdf
        with pymupdf.open(OUT/(role+'-native-report.pdf')) as pdf:
            text=''.join(p.get_text() for p in pdf)
            assert '회원 체험' in text and '서버에 저장하지 않아요' in text
    assert page.locator('#print-root .journey-report').count()==1
    assert not live['writes'] and not live['db'].exists()
    page.screenshot(path=str(OUT/(role+'-report.png')),full_page=True)
    page.reload();page.wait_for_function('window.festivalIdentity.mode === '+json.dumps(mode))
    page.evaluate('async(raw)=>{await readFile(new File([JSON.stringify(raw)],"fixture.json",{type:"application/json"}));if(pendingImport)await applyImport();}',raw)
    page.get_by_role('tab').first.wait_for()
    # Imported local snapshots never falsely grant an acknowledgement.
    assert page.evaluate('session.festival.acknowledged') is False
    choose_report(page)
    assert page.evaluate('session.values')==raw['preference_snapshot']['answers']
    assert not live['writes'] and not live['db'].exists()

@pytest.mark.parametrize('role',ROLES)
@pytest.mark.parametrize('active',[True,False])
def test_chromium_real_whole_sidebar_role_branches(chromium,live,role,active):
    with chromium.new_context(java_script_enabled=False) as ctx:
        ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(live['origin']+'/') else route.abort())
        page=ctx.new_page();page.goto(live['origin']+'/__login/'+role+('' if active else ':inactive'))
        page.goto(live['origin']+'/__sidebar')
        assert page.locator('a[href="'+BASE+'/"]').count()==int(active)
        if active:assert '전공마을 탐험' in page.locator('a[href="'+BASE+'/"]').inner_text()
        assert page.locator('a[href="/student/interest-mid/"]').count()==int(role=='admin')
        if not active:
            for suffix in ('/','/context','/attempts/00000000-0000-4000-8000-000000000000','/feedback.json'):
                assert page.request.get(live['origin']+BASE+suffix).status==403
            assert page.request.post(live['origin']+BASE+'/attempts',data={}).status==403


def test_student_persistence_and_crossstudent_denial_with_member_only_gate(page,live):
    page.goto(live['origin']+'/__login/student');page.wait_for_function('window.festivalIdentity.mode === "student"')
    page.evaluate('async()=>{init();session.values=qaSampleValues("lab");await finish();}')
    page.get_by_role('tab').first.wait_for();choose_report(page)
    attempt=page.evaluate('session.festival.attempt_id')
    data=page.request.get(live['origin']+BASE+'/attempts/'+attempt).json()
    assert data['preference']['selected_display_position']==2
    with closing(sqlite3.connect(live['db'])) as db:
        assert db.execute('SELECT student_id,origin FROM attempts').fetchall()==[('s1','STUDENT')]
        before=db.execute('SELECT * FROM preferences').fetchall()
    page.goto(live['origin']+'/__login/student:other');page.wait_for_function('window.festivalIdentity.mode === "student"')
    token=page.request.get(live['origin']+BASE+'/context').json()['csrf_token']
    target=live['origin']+BASE+'/attempts/'+attempt
    assert page.request.get(target).status==404
    assert page.request.post(target+'/presentation',data={'analysis_revision':data['analysis_revision'],'domain_id':data['presented_villages'][0],'sections':['intro']},headers={'X-CSRFToken':token}).status==404
    import uuid
    assert page.request.post(target+'/preference',data={'request_id':str(uuid.uuid4()),'analysis_revision':data['analysis_revision'],'selected_village_id':data['presented_villages'][0]},headers={'X-CSRFToken':token}).status==404
    with closing(sqlite3.connect(live['db'])) as db:assert db.execute('SELECT * FROM preferences').fetchall()==before
