"""Atomicity and existing parent communication over real models."""
import pytest
from conftest import login
from test_approval import approval_payload, counts
from app.models import Course, Notification
from app.models.conversation import ConversationMessage
from app.models.makeup_request import MakeupClassRequest

def test_parent_request_gets_thread_and_existing_notifications(makeup):
    app, db, tables, client, item = makeup
    login(client)
    client.post('/admin/makeup-requests/direct-synthetic/approve', data=approval_payload(client))
    db.session.expire_all()
    assert item.parent_conversation_id
    messages=ConversationMessage.query.filter_by(conversation_id=item.parent_conversation_id).all()
    assert any('보강 일정이 확정' in m.body for m in messages)
    recipients={n.user_id for n in Notification.query.filter_by(notification_type='makeup_approved')}
    assert recipients == {'parent','teacher-a'}
    assert all('mw=makeup:direct-synthetic' in n.link_url for n in Notification.query.filter_by(notification_type='makeup_approved',user_id='parent'))

def test_failure_after_notification_creation_rolls_back_everything(makeup, monkeypatch):
    app,db,tables,client,item=makeup
    login(client)
    payload=approval_payload(client)
    before=counts(db,tables)
    original=Notification.create_notification
    calls=[]
    def fail_after_first(**kw):
        calls.append(kw)
        value=original(**kw)
        raise RuntimeError('synthetic failure after first notification')
    monkeypatch.setattr(Notification,'create_notification',staticmethod(fail_after_first))
    client.post('/admin/makeup-requests/direct-synthetic/approve',data=payload)
    db.session.expire_all()
    assert calls
    assert counts(db,tables)==before
    assert item.status=='pending' and item.created_makeup_course_id is None
    assert item.parent_conversation_id is None
    assert item.admin_response_by is None

@pytest.mark.parametrize('status',['cancelled','rejected'])
def test_terminal_requests_are_never_reopened(makeup,status):
    app,db,tables,client,item=makeup
    login(client)
    item.status=status
    db.session.commit()
    before=counts(db,tables)
    client.post('/admin/makeup-requests/direct-synthetic/approve',data=approval_payload(client))
    db.session.expire_all()
    assert item.status==status and counts(db,tables)==before


def test_existing_parent_schedule_acceptance_keeps_ack(makeup):
    from datetime import date, time
    app,db,tables,client,item=makeup
    # Regression for the existing opt-in widget; never enable production gate.
    app.config['MOMOBOT_PARENT_WIDGET_ENABLED']=True
    item.teacher_confirmed=True
    item.teacher_proposed_date=date(2026,11,3)
    item.teacher_proposed_time=time(15,20)
    db.session.commit()
    login(client,'parent')
    response=client.post('/widget/makeup/direct-synthetic/confirm-schedule')
    assert response.status_code==200, response.get_data(as_text=True)
    db.session.expire_all()
    assert item.status=='approved'
    assert item.parent_confirmed_at is not None
