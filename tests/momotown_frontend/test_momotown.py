"""Isolated real Chromium tests; fixture HTTP is never the live app."""
import json
import os
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads((ROOT/'tests/momotown_frontend/approved-plan-v02.json').read_text(encoding='utf8'))
HTML = ROOT/'app/interest_quest/protected/index.html'
OUT = ROOT/'reports/exploration-v4/momotown-v02-implementation/frontend'
FRAME = '1.0.0-draft1+interest-only-momotown-v02'
@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        page.set_default_navigation_timeout(120000)
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        yield page
        assert errors == []
        browser.close()

@pytest.fixture
def server():
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    from threading import Thread
    state={'mode':'admin_preview','display_name':None,'fail_context':False,'writes':[],'attempt':None,'fail_preference':False,'mismatch':False,'fail_attempt':False,'fail_presentation':False}
    canonical=json.JSONDecoder().raw_decode(HTML.read_text(encoding='utf8').split('const FORM=',1)[1])[0]
    def analysis(answers):
        offered={d['id']:0 for d in canonical['domains']}; counts=dict(offered)
        for q,answer in zip(canonical['items'],answers):
            for o in q['options']: offered[o['domain_id']]+=1
            selected=next(o for o in q['options'] if o['id']==answer)
            counts[selected['domain_id']]+=1
        domains=[{'domain_id':d['id'],'selected_count':counts[d['id']],'offered_count':offered[d['id']],'comparison_units':counts[d['id']]*(210//offered[d['id']]),'display_order':i} for i,d in enumerate(canonical['domains'])]
        reps=[d['domain_id'] for d in sorted(domains,key=lambda d:(-d['comparison_units'],d['display_order'])) if d['selected_count']][:3]
        if state['mismatch']: domains[0]['selected_count']+=1
        return {'domains':domains,'representatives':reps}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def respond(self,payload,status=200):
            self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())
        def do_POST(self):
            import time
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['writes'].append({'path':self.path,'payload':payload,'csrf':self.headers.get('X-CSRFToken')})
            if state['mode']!='student': return self.respond({'error':'fixture forbids admin writes'},403)
            if self.path.endswith('/attempts'):
                if state['fail_attempt']: return self.respond({'error':'fixture failure'},503)
                if not state['attempt'] or state['attempt'].get('request_id')!=payload['request_id']:
                    a=analysis(payload['answers'])
                    state['attempt']={'attempt_id':'fixture-attempt','analysis_revision':'fixture-rev-1','analysis':a,'presented_villages':a['representatives'],'preference':None,'presentations':[],'form_version':FRAME,'copy_version':'momotown-festival-v02','answers':payload['answers'],'request_id':payload['request_id']}
                return self.respond(state['attempt'])
            if self.path.endswith('/presentation'):
                if state['fail_presentation']: return self.respond({'error':'fixture presentation failure'},503)
                a=state['attempt']; row=next((x for x in a['presentations'] if x['domain_id']==payload['domain_id']),None)
                if row is None: row={'domain_id':payload['domain_id'],'shown_sections':[]};a['presentations'].append(row)
                row['shown_sections']=sorted(set(row['shown_sections']+payload['sections']))
                return self.respond({'presentations':a['presentations']})
            if self.path.endswith('/preference'):
                time.sleep(.15)
                if state['fail_preference']: return self.respond({'error':'<img src=x onerror=alert(1)>'},503)
                a=state['attempt']
                if len(a['presentations'])!=3 or any(len(x['shown_sections'])!=2 for x in a['presentations']): return self.respond({'error':'not presented'},409)
                a['preference']={**payload,'displayed_villages_in_order':a['presented_villages'],'origin':'STUDENT','revision':1}
                return self.respond({'preference':a['preference'],'analysis':a['analysis']})
            return self.respond({'error':'not found'},404)
        def do_GET(self):
            if '/attempts/' in self.path:
                return self.respond(state['attempt'] or {},200 if state['attempt'] else 404)
            if self.path.endswith('/context'):
                payload={'mode':state['mode'],'display_name':state['display_name'],'csrf_token':'fixture-csrf','form_version':FRAME,'copy_version':'momotown-festival-v02'}
                data=json.dumps(payload).encode()
                self.send_response(503 if state['fail_context'] else 200)
                self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            else:
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(HTML.read_bytes())
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    state['url']=f'http://127.0.0.1:{http.server_port}/student/interest-quest/'
    yield state
    http.shutdown();http.server_close();thread.join()

def test_identity_is_authenticated_escaped_or_unnamed(page,server):
    server.update(mode='student',display_name='<img src=x onerror=alert(1)>민수')
    page.goto(server['url'])
    page.wait_for_function('window.festivalIdentity?.mode === "student"')
    assert server['display_name'] in page.locator('#main').inner_text()
    assert page.locator('#main img[src=x]').count() == 0
    assert page.locator('input[type=text]').count() == 0
    server.update(mode='admin_preview',display_name='ADMIN SHOULD NEVER APPEAR')
    page.reload()
    page.wait_for_function('window.festivalIdentity?.mode === "admin_preview"')
    assert 'ADMIN SHOULD NEVER APPEAR' not in page.locator('#main').inner_text()
    assert '관리자 미리보기' in page.locator('#main').inner_text()
    assert server['writes'] == []

def test_http_context_failure_blocks_and_retries(page,server):
    server['fail_context']=True
    page.goto(server['url'])
    page.get_by_role('button',name='신원 확인 다시 시도',exact=True).wait_for()
    page.evaluate('init()')
    assert page.evaluate('session') is None
    assert page.locator('.chapter-screen').count()==0
    server['fail_context']=False
    page.get_by_role('button',name='신원 확인 다시 시도',exact=True).click()
    page.wait_for_function('window.festivalIdentity?.mode === "admin_preview"')
    assert '모모타운 축제' in page.locator('#main').inner_text()

def test_local_file_is_explicit_unnamed_no_network(page):
    requests=[]
    page.on('request',lambda r: requests.append(r.url) if r.url.startswith('http') else None)
    local(page)
    assert page.evaluate('window.festivalIdentity?.mode')=='LOCAL_ADMIN_PREVIEW'
    assert '로컬 관리자 미리보기' in page.locator('#main').inner_text()
    assert requests==[]

def complete(page):
    page.evaluate('''async()=>{init();session.values=qaSampleValues('lab');await finish();}''')

def visit_three(page):
    for tab in ['connections','second','third','compare']:
        page.get_by_role('tab').filter(has_text={'connections':'학과·직업·공부','second':'두 번째 마을','third':'세 번째 마을','compare':'비교와 리포트'}[tab]).click()

def test_preference_requires_real_panels_and_preserves_report(page):
    local(page);complete(page)
    assert page.get_by_role('tab').count()==6
    before=page.evaluate('reportHtml(reportModel(session))')
    page.evaluate('setTab("compare");printResult()')
    assert page.evaluate('view')=='result'
    assert '아직 만나지 않은' in page.locator('#dialog').inner_text()
    assert page.locator('#dialog .preference-card').count()==0
    page.evaluate('closeDialog()')
    visit_three(page)
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    cards=page.locator('#dialog .preference-card')
    assert cards.count()==3
    assert page.locator('#dialog input:not([type=radio])').count()==0
    assert page.locator('#dialog textarea').count()==0
    assert page.locator('#dialog .preference-card[aria-pressed=true]').count()==0
    assert page.get_by_role('button',name='선택하고 리포트 보기',exact=True).is_disabled()
    assert cards.evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().width)')[0:1]*3 == cards.evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().width)')
    for position in [1,2]:
        if position==2:
            page.evaluate('session.festival.preference=null;session.festival.acknowledged=false;view="result";resultTab="compare";render();printResult()')
        cards.nth(position).click()
        page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
        page.locator('.journey-report').wait_for()
        assert page.evaluate('reportHtml(reportModel(session))')==before
        assert page.locator('.journey-report .preference-card').count()==0
        assert page.locator('.report-village-story').count()==3
        assert page.locator('.report-map-place').count()==9
    OUT.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(OUT/'report.png'),full_page=True)

def test_all_report_entrypoints_gate_and_edit_invalidates(page):
    local(page);complete(page)
    page.evaluate('printUnified()')
    assert page.locator('#dialog').is_visible()
    assert page.locator('#print-root').inner_html()==''
    page.evaluate('closeDialog();view="report";render()')
    assert page.locator('.journey-report').count()==0
    page.evaluate('closeDialog();view="result";resultTab="core";render()')
    visit_three(page)
    page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(1).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.evaluate('backToReview();session.cursor=0;view="question";render();choose(FORM.items[0].options.find(o=>o.id!==session.values[0]).id)')
    assert page.evaluate('session.festival?.preference ?? null') is None
    assert page.evaluate('session.festival?.attempt_id ?? null') is None
    assert page.evaluate('session.result') is None

def student(page,server):
    server.update(mode='student',display_name='테스트 학생')
    page.goto(server['url'])
    page.wait_for_function('window.festivalIdentity?.mode === "student"')

def test_student_save_ack_failure_retry_dedup_and_exact_payload(page,server):
    import uuid
    student(page,server);complete(page)
    assert server['attempt'] is not None
    assert page.evaluate('view')=='result'
    before=page.evaluate('reportHtml(reportModel(session))')
    visit_three(page)
    page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(2).click()
    server['fail_preference']=True
    page.evaluate('festivalConfirmPreference();festivalConfirmPreference()')
    page.wait_for_function('!session.festival.submitting')
    assert page.evaluate('view')=='result'
    assert page.locator('#festival-save-status').inner_text()
    assert page.locator('#festival-save-status').evaluate('(e)=>e===document.activeElement')
    assert page.locator('#dialog .preference-card[aria-pressed=true]').count()==1
    assert page.locator('#dialog img[src=x]').count()==0
    server['fail_preference']=False
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    assert page.evaluate('reportHtml(reportModel(session))')==before
    assert all(w['csrf']=='fixture-csrf' for w in server['writes'])
    attempts=[w['payload'] for w in server['writes'] if w['path'].endswith('/attempts')]
    assert len(attempts)==1
    assert set(attempts[0])=={'request_id','form_version','answers'}
    uuid.UUID(attempts[0]['request_id'])
    assert attempts[0]['form_version']==FRAME
    assert len(attempts[0]['answers'])==32
    prefs=[w['payload'] for w in server['writes'] if w['path'].endswith('/preference')]
    assert len(prefs)==2
    assert prefs[0]==prefs[1]
    assert set(prefs[0])=={'request_id','analysis_revision','selected_village_id'}
    assert prefs[0]['selected_village_id']==server['attempt']['presented_villages'][2]
    assert page.evaluate('session.festival.acknowledged') is True
    assert page.evaluate('localStorage.length')==0

def test_server_score_disagreement_never_displays_result(page,server):
    server['mismatch']=True
    student(page,server);complete(page)
    assert page.locator('[role=tab]').count()==0
    assert '서버' in page.locator('#main').inner_text()
    assert page.locator('[role=alert]').count()>0

def test_student_attempt_failure_and_presentation_retry(page,server):
    server['fail_attempt']=True
    student(page,server);complete(page)
    assert page.locator('[role=tab]').count()==0
    server['fail_attempt']=False
    page.get_by_role('button',name='결과 저장 다시 시도',exact=True).click()
    page.get_by_role('tab').first.wait_for()
    server['fail_presentation']=True
    visit_three(page)
    page.evaluate('printResult()')
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.wait_for_function('!session.festival.submitting')
    assert page.evaluate('view')=='result'
    server['fail_presentation']=False
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    attempts=[w['payload'] for w in server['writes'] if w['path'].endswith('/attempts')]
    assert len(attempts)==2 and attempts[0]==attempts[1]

def test_http_admin_completes_preview_without_student_writes(page,server):
    page.goto(server['url']);page.wait_for_function('window.festivalIdentity?.mode === "admin_preview"')
    complete(page);visit_three(page);page.evaluate('printResult()')
    assert '관리자 미리보기' in page.locator('#dialog').inner_text()
    page.locator('#dialog .preference-card').nth(1).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    assert server['writes']==[]

def download_record(page):
    with page.expect_download() as info:
        page.evaluate('exportRecord()')
    return json.loads(Path(info.value.path()).read_text(encoding='utf8'))

def import_record(page,raw):
    page.evaluate('async(raw)=>{await readFile(new File([JSON.stringify(raw)],"fixture.json",{type:"application/json"}));if(pendingImport)applyImport();}',raw)

def test_frame_and_preference_snapshot_export_import_validation(page):
    local(page);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(1).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    raw=download_record(page)
    assert raw['form_version']==raw['response_frame_version']==FRAME
    assert raw['copy_version']=='momotown-festival-v02'
    assert raw['preference_snapshot']['preference']['selected_village_id']==page.evaluate('festivalCandidates(session)[1]')
    assert 'display_name' not in json.dumps(raw)
    page.evaluate('session=null;goHome()')
    import_record(page,raw)
    assert page.evaluate('session.response_frame_version')==FRAME
    again=download_record(page)
    assert again['preference_snapshot']['preference']==raw['preference_snapshot']['preference']
    page.evaluate('session=null')
    raw['preference_snapshot']['presented_villages'].reverse()
    import_record(page,raw)
    assert page.evaluate('session') is None
    assert page.locator('#toast').inner_text()

def test_prior_frames_preserved_not_relabelled_or_auto_compared(page):
    local(page);complete(page)
    raw=download_record(page)
    canonical=page.evaluate('FORM.form_version')
    for frame in [canonical,canonical+'+response-frame-v1.2']:
        old={**raw,'form_version':frame,'response_frame_version':frame,'copy_version':None,'preference_snapshot':None}
        page.evaluate('session=null;goHome()')
        import_record(page,old)
        assert page.evaluate('session.response_frame_version')==frame
        assert download_record(page)['form_version']==frame
        page.evaluate('printResult()')
        assert page.locator('.journey-report').count()==0
        assert '이전 안내' in page.locator('#dialog').inner_text()
        page.evaluate('closeDialog()')
        page.evaluate('session.cursor=0;view="question";render()')
        assert page.locator('#scene-title').inner_text()!=PLAN['scenes'][0]['title']

def test_student_refresh_restores_only_server_acknowledged_snapshot(page,server):
    student(page,server);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(2).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    saved=download_record(page)
    assert 'attempt=' in page.url
    page.reload()
    page.wait_for_function('session?.festival?.verified===true')
    assert page.evaluate('session.festival.preference.selected_village_id')==server['attempt']['preference']['selected_village_id']
    page.evaluate('printResult()')
    page.locator('.journey-report').wait_for()
    assert download_record(page)['preference_snapshot']['preference']==saved['preference_snapshot']['preference']

def test_student_import_never_trusts_client_preference_ack(page,server):
    student(page,server);complete(page)
    raw=download_record(page)
    assert raw['preference_snapshot']['attempt_id']
    raw['preference_snapshot']['preference']={'selected_village_id':server['attempt']['presented_villages'][0],'analysis_revision':'fixture-rev-1'}
    raw['preference_snapshot']['seen']={id:['intro','study'] for id in server['attempt']['presented_villages']}
    page.evaluate('session=null;goHome()')
    import_record(page,raw)
    page.wait_for_function('session?.festival?.verified===true')
    page.evaluate('printResult()')
    assert page.locator('.journey-report').count()==0
    assert page.evaluate('session.festival.acknowledged') is False

def test_stale_pending_session_is_not_latest_active_attempt(page):
    local(page);complete(page)
    assert page.evaluate('''()=>{const old=session,f=festivalState(old);init();return festivalStillActive(old,f)}''') is False

def test_final_transition_and_authenticated_name_not_every_question(page,server):
    student(page,server)
    page.evaluate('init();session.cursor=8;view="pause";render()')
    assert server['display_name'] in page.locator('#main').inner_text()
    page.evaluate('session.cursor=31;session.values=qaSampleValues("lab");view="anticipation";render()')
    assert PLAN['chapters'][3]['closing'] in page.locator('#main').inner_text()
    page.evaluate('view="question";render()')
    assert server['display_name'] not in page.locator('#question-title').inner_text()

def test_anonymous_and_missing_student_link_fail_closed(page,server):
    for mode,name in [('anonymous',None),('student',None),('student','')]:
        server.update(mode=mode,display_name=name)
        page.goto(server['url'])
        page.get_by_role('button',name='신원 확인 다시 시도',exact=True).wait_for()
        page.evaluate('init()')
        assert page.evaluate('session') is None
        assert page.locator('.story-greeting').count()==0
    assert server['writes']==[]

def test_new_preference_choice_after_error_gets_new_idempotency_key(page,server):
    student(page,server);complete(page);visit_three(page);page.evaluate('printResult()')
    server['fail_preference']=True
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.wait_for_function('!session.festival.submitting')
    server['fail_preference']=False
    page.locator('#dialog .preference-card').nth(2).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    prefs=[w['payload'] for w in server['writes'] if w['path'].endswith('/preference')]
    assert len(prefs)==2
    assert prefs[0]['selected_village_id']!=prefs[1]['selected_village_id']
    assert prefs[0]['request_id']!=prefs[1]['request_id']

def test_mixed_prior_frame_and_new_snapshot_rejected(page):
    local(page);complete(page)
    raw=download_record(page)
    raw['form_version']=page.evaluate('FORM.form_version')
    page.evaluate('session=null;goHome()')
    import_record(page,raw)
    assert page.evaluate('session') is None

def test_storage_copy_is_mode_accurate_and_synthetic_never_student_write(page,server):
    student(page,server)
    page.evaluate('goHome();showManagement()')
    assert '32개 응답을 모두 고른 뒤' in page.locator('#dialog').inner_text()
    assert '서버 저장 성공' in page.locator('#dialog').inner_text()
    page.evaluate('closeDialog();session=null')
    raw=page.evaluate('''()=>{const s=qaSampleSession('lab');s.response_frame_version=FESTIVAL_FRAME;return festivalRecord(s)}''')
    import_record(page,raw)
    assert server['writes']==[]
    assert page.evaluate('session') is None

def test_local_qa_samples_use_new_frame_without_real_writes(page):
    local(page)
    page.evaluate('enableLocalStoryQA();showSample("lab")')
    assert page.evaluate('sampleSession.response_frame_version')==FRAME
    assert page.evaluate('sampleSession.origin')=='SYNTHETIC_EXAMPLE'

@pytest.mark.parametrize('width',[320,390,768,1440])
def test_responsive_menu_six_tabs_and_preference_dialog(page,width):
    page.set_viewport_size({'width':width,'height':900})
    local(page)
    menu=page.get_by_role('button',name='메뉴',exact=True)
    assert menu.get_attribute('aria-expanded')=='false'
    menu.click();assert menu.get_attribute('aria-expanded')=='true'
    page.keyboard.press('Escape');assert menu.get_attribute('aria-expanded')=='false'
    complete(page)
    assert page.get_by_role('tab').all_inner_texts()==['1. 핵심 마을 발견','2. 학과·직업·공부','3. 함께 만날 마을','4. 두 번째 마을','5. 세 번째 마을','6. 비교와 리포트']
    visit_three(page);page.evaluate('printResult()')
    assert page.locator('#dialog').is_visible()
    assert page.locator('#dialog .preference-card').count()==3
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    cards=page.locator('#dialog .preference-card')
    cards.first.focus();page.keyboard.press('Space')
    assert cards.first.get_attribute('aria-pressed')=='true'
    OUT.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(OUT/f'preference-{width}.png'),full_page=True)

def test_print_map_artwork_graph_reference_appendix_preserved(page):
    local(page);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').nth(1).click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.locator('.journey-report').wait_for()
    assert page.locator('.journey-report .report-village-story').count()==3
    assert page.locator('.journey-report .career-scene').count()==6
    assert page.locator('.journey-report .school-stage').count()==9
    assert page.locator('.journey-report .report-map-place').count()==9
    assert page.locator('.journey-report .interest-bar').count()==9
    assert page.locator('.journey-report .report-references a').count()>0
    assert page.locator('.journey-report .report-village-story').nth(2).evaluate('(e)=>e.nextElementSibling.classList.contains("report-map-summary")')
    page.evaluate('window.__printed=0;window.print=()=>window.__printed++;printUnified()')
    assert page.evaluate('window.__printed')==1
    assert page.locator('#print-root .response-appendix').count()==0
    page.locator('#include-appendix').check()
    page.evaluate('printUnified()')
    assert page.locator('#print-root .response-appendix[open]').count()==1
    assert page.locator('#print-root .response-appendix p').count()==32
    assert PLAN['scenes'][28]['options'][1]['proposed_text'] in page.evaluate('reportHtml(reportModel(session))') or page.evaluate('session.values[28]')!=PLAN['scenes'][28]['options'][1]['source_option_id']
    page.emulate_media(media='print')
    assert not page.locator('.report-toolbar').is_visible()
    OUT.mkdir(parents=True,exist_ok=True)
    page.pdf(path=str(OUT/'festival-report-with-appendix.pdf'),format='A4',print_background=True)

def test_canonical_data_engine_and_39_art_files_unchanged():
    import hashlib
    import subprocess
    current=HTML.read_text(encoding='utf8')
    baseline=subprocess.check_output(['git','show','1443f97:app/interest_quest/protected/index.html'],cwd=ROOT).decode('utf8')
    def declaration(text,key):
        tail=text.split('const '+key+'=',1)[1]
        _,end=json.JSONDecoder().raw_decode(tail)
        return tail[:end]
    for key in ['FORM','V12']:
        assert declaration(current,key)==declaration(baseline,key)
    engine_start='/* Pure activity-interest scorer'
    engine_end='/* Read-only editorial bridge.'
    assert current.split(engine_start,1)[1].split(engine_end,1)[0]==baseline.split(engine_start,1)[1].split(engine_end,1)[0]
    base=HTML.parent
    # The approved name-only release supersedes the plan's old display hashes.
    # Pin the real reviewed live baseline; never compare against moving HEAD.
    display_baseline='d31fcaf40ff8ed5904d965cddf026599a8b6ae9f'
    for name in ['story-v3.js','story-v3.css','story-v4-content.json','story-assets/v4-image-slots.json']:
        accepted=subprocess.check_output(['git','show',display_baseline+':app/interest_quest/protected/'+name],cwd=ROOT).decode('utf8').replace(chr(13)+chr(10),chr(10))
        assert (base/name).read_text(encoding='utf8')==accepted
    slots=json.loads((base/'story-assets/v4-image-slots.json').read_text(encoding='utf8'))['slots']
    integrated=[s for s in slots if s['status']=='INTEGRATED_FILE_VERIFIED']
    assert len(integrated)==39
    for s in integrated:
        assert hashlib.sha256((base/s['display_source']).read_bytes()).hexdigest()==s['display_sha256']
    canonical=json.loads(declaration(current,'FORM'))
    normalized=json.loads((base/'momotown-v02.json').read_text(encoding='utf8'))
    for q,scene in zip(canonical['items'],normalized['scenes']):
        assert q['id']==scene['source_item_id']
        assert q['chapter']==scene['chapter']
        assert [(o['id'],o['domain_id'],o['weight']) for o in q['options']]==[(o['source_option_id'],o['domain_id'],o['weight']) for o in scene['options']]
    assert [sum(s['chapter']==i for s in normalized['scenes']) for i in range(1,5)]==[8]*4

def test_stale_presentation_queue_never_writes_after_new_session(page,server):
    student(page,server);complete(page)
    page.evaluate('async()=>{await session.festival.presentation_queue}')
    before=len(server['writes'])
    page.evaluate('''async()=>{const old=session,f=festivalState(old);f.seen[festivalCandidates(old)[1]]=['intro','study'];init();await festivalFlushPresentations(old,f)}''')
    assert len(server['writes'])==before

def test_first_study_missing_even_after_second_third_requires_route(page):
    local(page);complete(page)
    page.evaluate('setTab("second");setTab("third");setTab("compare");printResult()')
    assert page.locator('#dialog .preference-card').count()==0
    page.get_by_role('button',name='연구소마을 공부 보기',exact=True).click()
    assert page.locator('#result-panel').get_attribute('data-step')=='connections'
    page.evaluate('setTab("compare");printResult()')
    assert page.locator('#dialog .preference-card').count()==3

def test_starting_new_visit_clears_previous_print_material(page):
    local(page);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.evaluate('window.print=()=>{};printUnified();init()')
    assert page.locator('#print-root').inner_html()==''

@pytest.mark.parametrize('kind',['full','partial','legacy'])
def test_browser_beforeprint_after_import_cannot_print_previous_report(page,kind):
    local(page);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    raw=download_record(page)
    page.evaluate('window.print=()=>{};printUnified()')
    assert page.locator('#print-root .journey-report').count()==1
    if kind=='partial':
        raw=page.evaluate('''()=>{const s={...session,values:session.values.map((v,i)=>i?null:v),cursor:1,result:null};return festivalRecord(s)}''')
    elif kind=='legacy':
        raw.update(form_version=page.evaluate('FORM.form_version'),response_frame_version=page.evaluate('FORM.form_version'),copy_version=None,preference_snapshot=None)
    import_record(page,raw)
    assert page.locator('#print-root').inner_html()==''
    # CDP printToPDF fires Chromium's genuine beforeprint, not a synthetic event
    # or the application's gated printUnified entry point.
    page.evaluate('window.__beforePrint=0;addEventListener("beforeprint",()=>window.__beforePrint++)')
    page.pdf()
    assert page.evaluate('window.__beforePrint')==1
    assert page.locator('#print-root').inner_html()==''
    assert not page.evaluate('festivalAllowed(session)')


@pytest.mark.parametrize('outcome',['success','error'])
@pytest.mark.parametrize('transition',['new_visit','import','context'])
def test_delayed_restore_cannot_mutate_newer_answered_visit(page,server,outcome,transition):
    student(page,server);complete(page)
    page.evaluate('async()=>{await session.festival.presentation_queue}')
    raw=page.evaluate('''()=>festivalRecord({...session,values:session.values.map((v,i)=>i?null:v),cursor:1,result:null})''')
    response=json.loads(json.dumps(server['attempt']))
    held=[]
    page.route('**/attempts/fixture-attempt',lambda route:held.append(route))
    with page.expect_request('**/attempts/fixture-attempt'):
        page.evaluate('window.__restoreDone=false;festivalRestoreAttempt("fixture-attempt").finally(()=>window.__restoreDone=true);void 0')
    page.evaluate('init();view="question";render();choose(FORM.items[0].options[1].id)')
    assert len(held)==1
    if transition=='import':
        import_record(page,raw)
    elif transition=='context':
        page.evaluate('async()=>{await loadFestivalContext()}')
    before=page.evaluate('({values:[...session.values],view,festival:session.festival,hash:location.hash})')
    held[0].fulfill(status=200 if outcome=='success' else 503,content_type='application/json',body=json.dumps(response if outcome=='success' else {'error':'delayed fixture failure'}))
    page.wait_for_function('window.__restoreDone')
    assert page.evaluate('({values:[...session.values],view,festival:session.festival,hash:location.hash})')==before
    assert page.locator('.option').count()==4


@pytest.mark.parametrize('change',['cached_html','answers','acknowledgement'])
def test_native_beforeprint_revalidates_current_fingerprint_and_ack(page,change):
    local(page);complete(page);visit_three(page);page.evaluate('printResult()')
    page.locator('#dialog .preference-card').first.click()
    page.get_by_role('button',name='선택하고 리포트 보기',exact=True).click()
    page.evaluate('window.print=()=>{};printUnified();document.querySelector("#print-root").innerHTML="<p>STALE PRINT CACHE</p>"')
    if change=='answers':
        page.evaluate('session.values[0]=FORM.items[0].options.find(o=>o.id!==session.values[0]).id')
    elif change=='acknowledgement':
        page.evaluate('session.festival.acknowledged=false')
    page.pdf()
    assert 'STALE PRINT CACHE' not in page.locator('#print-root').inner_text()
    assert page.locator('#print-root .journey-report').count()==(1 if change=='cached_html' else 0)


@pytest.mark.parametrize('outcome',['success','error'])
@pytest.mark.parametrize('change',['context','identity','answers','import'])
def test_restore_guard_rejects_changes_without_another_init(page,server,outcome,change):
    student(page,server);complete(page)
    page.evaluate('async()=>{await session.festival.presentation_queue}')
    raw=page.evaluate('''()=>festivalRecord({...session,values:session.values.map((v,i)=>i?null:v),cursor:1,result:null})''')
    response=json.loads(json.dumps(server['attempt']))
    page.evaluate('init();view="question";render();choose(FORM.items[0].options[1].id)')
    held=[]
    page.route('**/attempts/fixture-attempt',lambda route:held.append(route))
    with page.expect_request('**/attempts/fixture-attempt'):
        page.evaluate('window.__restoreDone=false;festivalRestoreAttempt("fixture-attempt").finally(()=>window.__restoreDone=true);void 0')
    if change=='context':
        page.evaluate('async()=>{await loadFestivalContext()}')
    elif change=='identity':
        page.evaluate('window.festivalIdentity={...window.festivalIdentity,csrf_token:"new-fixture-identity"}')
    elif change=='answers':
        page.evaluate('choose(FORM.items[0].options[2].id)')
    else:
        import_record(page,raw)
    before=page.evaluate('({values:[...session.values],view,festival:session.festival,hash:location.hash})')
    assert len(held)==1
    held[0].fulfill(status=200 if outcome=='success' else 503,content_type='application/json',body=json.dumps(response if outcome=='success' else {}))
    page.wait_for_function('window.__restoreDone')
    assert page.evaluate('({values:[...session.values],view,festival:session.festival,hash:location.hash})')==before


def local(page):
    page.goto(HTML.as_uri())

def test_exact_approved_copy_in_real_question_screens(page):
    local(page)
    assert '모모타운 축제' in page.locator('#main').inner_text()
    canonical = page.evaluate('JSON.stringify(FORM)')
    page.evaluate('init()')
    assert page.evaluate('session.response_frame_version') == FRAME
    seen=[]
    for i,scene in enumerate(PLAN['scenes']):
        page.evaluate('(i)=>{session.cursor=i;view="question";render(false)}',i)
        assert page.locator('#scene-title').inner_text() == scene['title']
        assert page.locator('#scene-copy').inner_text() == scene['scene']
        assert page.locator('.festival-dialogue').inner_text() == scene['dialogue']
        assert page.locator('#question-title').inner_text() == scene['question']
        assert page.locator('.option .word').all_inner_texts() == [o['proposed_text'] for o in scene['options']]
        seen.append(page.locator('#question-title').inner_text())
    assert len(set(seen)) == 32
    for i,c in enumerate(PLAN['chapters']):
        page.evaluate('(i)=>{session.cursor=i*8;view="pause";render(false)}',i)
        assert c['title'] in page.locator('#main').inner_text()
        assert c['intro'] in page.locator('#main').inner_text()
    assert page.evaluate('JSON.stringify(FORM)') == canonical
    assert page.locator('input[type=text]').count() == 0
    OUT.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(OUT/'chapter-four.png'),full_page=True)
