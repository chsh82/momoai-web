"""Real Chromium -> real blueprints/CSRF -> guarded disposable SQLite.

Only base chrome is reduced. Browser networking restricted to fixture loopback;
no real users, login endpoint, credentials, pushes or model API calls.
"""
import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
import socket
NATIVE_CONNECT=socket.socket.connect
import threading
from pathlib import Path
from conftest import kernel
from test_essay_delivery import data,web


def test_browser_student_parent_submission_and_admin_reference_forward(web,monkeypatch):
    from playwright.sync_api import sync_playwright,expect
    from werkzeug.serving import make_server
    from app.models import Essay,Notification
    from app.models.essay import EssayTeacherGrant
    def local_connect(sock,address):
        assert address[0] in ('127.0.0.1','localhost','::1'), 'external socket forbidden'
        return NATIVE_CONNECT(sock,address)
    monkeypatch.setattr(socket.socket,'connect',local_connect)
    server=make_server('127.0.0.1',0,web.app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    out=Path(__file__).resolve().parents[2]/'reports/essay-delivery/browser';out.mkdir(parents=True,exist_ok=True)
    serializer=web.app.session_interface.get_signing_serializer(web.app)
    def actor(context,uid):
        context.clear_cookies()
        context.add_cookies([{'name':web.app.config['SESSION_COOKIE_NAME'],
            'value':serializer.dumps({'_user_id':uid,'_fresh':True}),'url':origin}])
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('MOMOAI_TEST_CHROMIUM',
                'C:/Users/aproa/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
            context=browser.new_context(viewport={'width':1100,'height':900})
            context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            page=context.new_page()
            for uid,path,title in [('pupil','/student/essays/new','Browser pupil'),('parent','/parent/essays/submit','Browser parent')]:
                actor(context,uid)
                page.goto(origin+path)
                page.locator('[name=title]').fill(title)
                page.locator('[name=content]').fill('Synthetic browser essay')
                page.locator('[name=essay_type][value=basic]').check()
                page.locator('[name=makeup_session_id]').select_option('session-makeup')
                page.screenshot(path=str(out/(uid+'-makeup.png')),full_page=True)
                page.get_by_role('button',name='보강 수업에 제출',exact=True).click()
                page.wait_for_url('**/student/essays' if uid=='pupil' else '**/parent/essays/s')
                web.db.session.expire_all()
                e=Essay.query.filter_by(title=title).one()
                assert (e.user_id,e.course_id,e.session_id)==('makeup','makeup','session-makeup')
            actor(context,'admin');page.goto(origin+'/essays/')
            page.locator('input[name=essay_id][value=one]').check()
            page.locator('input[name=essay_id][value=two]').check()
            page.get_by_role('button',name='선택한 글 강사에게 전달',exact=True).click()
            page.locator('[name=teacher_id]').select_option('reader')
            page.locator('[name=mode]').select_option('reference')
            page.locator('[name=reason]').fill('Browser approved forwarding')
            assert EssayTeacherGrant.query.count()==0
            page.screenshot(path=str(out/'admin-forward-preview.png'),full_page=True)
            page.get_by_role('button',name='선택한 글 강사에게 전달 확정',exact=True).click()
            page.wait_for_load_state('networkidle')
            web.db.session.expire_all()
            assert EssayTeacherGrant.query.count()==2
            assert Notification.query.filter_by(user_id='reader',notification_type='essay_forwarded').count()==2
            actor(context,'reader');page.goto(origin+'/essays/one/view_submission')
            expect(page.get_by_text('열람/참고 전용',exact=False)).to_be_visible()
            assert page.locator('form').count()==0
            page.reload()
            expect(page.get_by_text('preserve original',exact=True)).to_be_visible()
            page.screenshot(path=str(out/'reader-read-only.png'),full_page=True)
            # Legitimate correction forms and JSON fetches retain CSRF, with
            # actual server persistence/readback rather than mocked responses.
            actor(context,'regular'); page.goto(origin+'/essays/two/view_submission')
            page.on('dialog', lambda dialog: dialog.accept())
            page.locator('#edit-text-btn').click()
            page.locator('#text-editor').fill('Browser corrected original')
            with page.expect_response(lambda r: '/update-original-text' in r.url and r.request.method == 'PATCH') as saved:
                page.locator('#save-text-btn').click()
            assert saved.value.status == 200
            assert saved.value.request.headers.get('x-csrftoken')
            web.db.session.expire_all(); assert web.essay('two').original_text == 'Browser corrected original'
            page.reload()
            expect(page.locator('#original-text-display')).to_have_text('Browser corrected original')
            page.goto(origin+'/essays/two/manual-correction')
            page.locator('[name=correction_content]').fill('Browser legitimate manual correction')
            with page.expect_response(lambda r: '/manual-correction' in r.url and r.request.method == 'POST') as saved:
                page.locator('button[name=action][value=save]').click()
            assert saved.value.status == 302
            web.db.session.expire_all()
            from app.models.essay import EssayVersion
            version = EssayVersion.query.filter_by(essay_id='two').one()
            assert 'Browser legitimate manual correction' in version.html_content
            response = page.goto(origin+'/essays/two/report-frame')
            assert response.status == 200
            expect(page.get_by_text('Browser legitimate manual correction',exact=True)).to_be_visible()
            page.reload()
            expect(page.get_by_text('Browser legitimate manual correction',exact=True)).to_be_visible()
            page.screenshot(path=str(out/'legitimate-manual-correction.png'),full_page=True)
            context.close();browser.close()
    finally:
        server.shutdown();thread.join(timeout=10)
