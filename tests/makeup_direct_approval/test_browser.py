"""Opt-in Chromium functional regressions, synthetic Flask/SQLite only.
Run MOMOAI_TEST_MODE=1 MOMOAI_MAKEUP_BROWSER=1 with the guarded TMPDIR.
Browser HTTP is fulfilled through the real Flask test client; external requests
are intercepted. Actual rebuilt repository CSS in a reduced integration shell.
"""
import os
import socket
from datetime import date, time
from urllib.parse import urlsplit
import pytest
from conftest import login, ROOT
from pathlib import Path
_LOCAL_CONNECT = socket.socket.connect
pytestmark = pytest.mark.skipif(os.environ.get('MOMOAI_MAKEUP_BROWSER') != '1',
    reason='Set MOMOAI_MAKEUP_BROWSER=1 for isolated Chromium checks')


def test_chromium_direct_modal_validation_reset_and_real_post(makeup, monkeypatch):
    def loopback_only(sock, address):
        assert address[0] in ('127.0.0.1', '::1', 'localhost'), 'external network forbidden'
        return _LOCAL_CONNECT(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', loopback_only)
    from playwright.sync_api import sync_playwright
    app, db, tables, client, item = makeup
    login(client, 'manager')
    item.student.name = "Synthetic O'Neil"
    from app.models.makeup_request import MakeupClassRequest
    normal = MakeupClassRequest(request_id='normal-synthetic', student_id='s',
        requested_course_id='c-a', requested_by='pupil', status='pending',
        teacher_confirmed=True, teacher_proposed_date=date(2026,11,3),
        teacher_proposed_time=time(15,20))
    db.session.add(normal)
    db.session.commit()
    posts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
        page = browser.new_page(viewport={'width':1280,'height':900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        def transport(route):
            request = route.request
            parts = urlsplit(request.url)
            if parts.hostname != 'makeup.synthetic.invalid':
                route.fulfill(status=200, body='', content_type='text/javascript')
                return
            path = parts.path + ('?' + parts.query if parts.query else '')
            if request.method == 'POST':
                posts.append(path)
            response = client.open(path, method=request.method,
                data=request.post_data or None,
                content_type=request.headers.get('content-type'))
            headers = {k:v for k,v in response.headers.items()
                if k.lower() not in ('content-length','set-cookie')}
            route.fulfill(status=response.status_code, headers=headers, body=response.data)
        page.route('**/*', transport)
        page.goto('http://makeup.synthetic.invalid/admin/makeup-requests', wait_until='domcontentloaded')
        # Actual rebuilt local CSS; no demonstration-only style injection.
        page.wait_for_function("getComputedStyle(document.querySelector('#approveModal')).display === 'none'")
        direct = page.get_by_role('button',name='관리자 직접 승인',exact=True)
        for width,label in [(1280,'desktop'),(390,'mobile')]:
            page.set_viewport_size({'width':width,'height':900})
            direct.scroll_into_view_if_needed()
            colors=direct.evaluate('(e)=>({bg:getComputedStyle(e).backgroundColor,fg:getComputedStyle(e).color,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})')
            assert colors['bg'] == 'rgb(180, 83, 9)', colors
            assert colors['fg'] == 'rgb(255, 255, 255)' and colors['w'] > 100 and colors['h'] > 25, colors
            page.screenshot(path=str(ROOT/'reports/makeup-direct-approval'/('button-'+label+'.png')),full_page=True)
        direct.click()
        assert page.locator('#approvalMode').input_value() == 'direct'
        assert page.locator('#directConfirmed').evaluate('(e)=>e.required')
        assert page.locator('#makeup_time_hour').evaluate('(e)=>e.required')
        assert page.locator('#proposeToParentButton').is_disabled()
        page.locator('#makeup_date').fill('2026-11-02')
        page.locator('#makeup_time_hour').select_option('14')
        page.locator('#makeup_time_minute').select_option('20')
        assert page.locator('#approveForm').evaluate('(e)=>e.checkValidity()') is False
        page.locator('#approveForm button[type=submit]').click()
        assert posts == []
        page.locator('#directConfirmed').check()
        page.screenshot(path=str(ROOT/'reports/makeup-direct-approval/confirmation-mobile.png'))
        page.locator('#admin_notes').fill('Browser synthetic note')
        # Opening a confirmed request after direct mode must reset all state.
        page.evaluate('closeApproveModal()')
        page.get_by_role('button',name='승인',exact=True).click()
        assert page.locator('#approvalMode').input_value() == 'normal'
        assert page.locator('#admin_notes').input_value() == ''
        assert not page.locator('#directConfirmed').is_checked()
        assert not page.locator('#directConfirmed').evaluate('(e)=>e.required')
        assert not page.locator('#makeup_time_hour').evaluate('(e)=>e.required')
        assert page.locator('#proposeToParentButton').is_enabled()
        assert page.locator('#makeup_date').input_value() == '2026-11-03'
        assert page.locator('#makeup_time_hour').input_value() == '15'
        page.evaluate('closeApproveModal()')
        page.get_by_role('button',name='관리자 직접 승인',exact=True).click()
        assert page.locator('#makeup_date').input_value() == ''
        page.locator('#makeup_date').fill('2026-11-02')
        page.locator('#makeup_time_hour').select_option('14')
        page.locator('#makeup_time_minute').select_option('20')
        page.locator('#directConfirmed').check()
        page.locator('#approveForm button[type=submit]').click()
        page.wait_for_url('http://makeup.synthetic.invalid/admin/makeup-requests')
        assert posts == ['/admin/makeup-requests/direct-synthetic/approve']
        db.session.expire_all()
        assert item.status == 'approved' and not item.teacher_confirmed
        assert item.created_makeup_course.start_time == time(14,20)
        assert normal.status == 'pending'
        assert not errors, errors
        browser.close()


def test_stale_teacher_extraction_cannot_modify_direct_confirmation(makeup, monkeypatch):
    def loopback_only(sock, address):
        assert address[0] in ('127.0.0.1', '::1', 'localhost'), 'external network forbidden'
        return _LOCAL_CONNECT(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', loopback_only)
    from playwright.sync_api import sync_playwright
    app, db, tables, client, item = makeup
    login(client, 'master')
    html = client.get('/admin/makeup-requests').get_data(as_text=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
        page = browser.new_page()
        page.route('**/*', lambda route: route.fulfill(status=200, body='', content_type='text/javascript'))
        page.set_content(html, wait_until='domcontentloaded')
        page.evaluate("""() => {
            showApproveModal('teacher-A', 'Synthetic A', 'Synthetic course', '', true, '', '');
            window.fetch = () => new Promise(resolve => {window.finishExtraction = resolve});
            window.extraction = extractProposedTime();
            closeApproveModal();
            showApproveModal('direct-synthetic', 'Synthetic B', 'Synthetic course', '', false, '', '', true);
            document.getElementById('makeup_date').value = '2026-11-02';
            setHmSelect('makeup_time', '14:20');
            document.getElementById('directConfirmed').checked = true;
        }""")
        page.evaluate("""async () => {
            window.finishExtraction({json:async()=>({found:true,date:'2026-12-15',time:'18:30',note:'stale A'})});
            await window.extraction;
        }""")
        assert page.locator('#approvalMode').input_value() == 'direct'
        assert page.locator('#directConfirmed').is_checked()
        assert page.locator('#makeup_date').input_value() == '2026-11-02'
        assert page.locator('#makeup_time_hour').input_value() == '14'
        assert page.locator('#makeup_time_minute').input_value() == '20'
        assert 'stale A' not in page.locator('#extractNote').inner_text()
        browser.close()
