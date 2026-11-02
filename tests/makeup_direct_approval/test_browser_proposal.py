"""Existing secondary form action must still POST the real parent proposal."""
import os
import socket
from datetime import date,time
from urllib.parse import urlsplit
from pathlib import Path
import pytest
from conftest import login
from app.models.conversation import ConversationMessage
from app.models import Notification
_LOCAL_CONNECT=socket.socket.connect
pytestmark=pytest.mark.skipif(os.environ.get('MOMOAI_MAKEUP_BROWSER')!='1',reason='Explicit browser opt-in')

def test_normal_mode_proposal_real_post_and_parent_readback(makeup,monkeypatch):
    def loopback(sock,address):
        assert address[0] in ('127.0.0.1','localhost','::1')
        return _LOCAL_CONNECT(sock,address)
    monkeypatch.setattr(socket.socket,'connect',loopback)
    from playwright.sync_api import sync_playwright
    app,db,tables,client,item=makeup
    login(client)
    item.teacher_confirmed=True
    item.teacher_proposed_date=date(2026,11,3)
    item.teacher_proposed_time=time(15,20)
    db.session.commit()
    posts=[]
    def transport(route):
        req=route.request
        u=urlsplit(req.url)
        assert u.hostname=='makeup.synthetic.invalid'
        path=u.path+('?' + u.query if u.query else '')
        if req.method=='POST': posts.append((path,req.post_data))
        r=client.open(path,method=req.method,data=req.post_data or None,content_type=req.headers.get('content-type'))
        route.fulfill(status=r.status_code,headers={k:v for k,v in r.headers.items() if k.lower() not in ('content-length','set-cookie')},body=r.data)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('MOMOAI_CHROME','C:/Program Files/Google/Chrome/Application/chrome.exe'))
        page=browser.new_page()
        page.route('**/*',transport)
        page.goto('http://makeup.synthetic.invalid/admin/makeup-requests',wait_until='networkidle')
        page.get_by_role('button',name='승인',exact=True).click()
        assert page.locator('#approvalMode').input_value()=='normal'
        page.locator('#makeup_date').fill('2026-11-05')
        page.locator('#makeup_time_hour').select_option('16')
        page.locator('#makeup_time_minute').select_option('30')
        page.locator('#proposeToParentButton').click()
        page.wait_for_url('http://makeup.synthetic.invalid/admin/makeup-requests')
        assert len(posts)==1 and posts[0][0].endswith('/propose-to-parent'),posts
        assert 'csrf_token=' in posts[0][1] and 'approval_mode=normal' in posts[0][1]
        db.session.expire_all()
        assert item.status=='pending' and item.created_makeup_course_id is None
        assert item.teacher_proposed_date==date(2026,11,5)
        assert item.teacher_proposed_time==time(16,30)
        assert item.parent_conversation_id
        assert any('진행할까요' in m.body for m in ConversationMessage.query.filter_by(conversation_id=item.parent_conversation_id))
        assert Notification.query.filter_by(user_id='parent',notification_type='dm').count()==1
        browser.close()
