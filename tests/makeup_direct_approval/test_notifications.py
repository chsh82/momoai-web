"""Notification transactions keep existing helpers but never publish partial work."""
import sqlite3
from conftest import login
from test_approval import approval_payload, counts
from app.models import Notification
from app.utils.notification_transaction import notification_transaction
import pytest


def test_push_only_after_committed_request_is_visible_to_another_connection(makeup,monkeypatch):
    app,db,tables,client,item=makeup
    login(client)
    payload=approval_payload(client)
    from app.utils import push_utils
    observations=[]
    def push(**kw):
        from contextlib import closing
        with closing(sqlite3.connect(db.engine.url.database)) as c:
            row=c.execute('SELECT status, created_makeup_course_id FROM makeup_class_requests WHERE request_id=?',('direct-synthetic',)).fetchone()
        observations.append(row)
        assert row[0]=='approved' and row[1]
    monkeypatch.setattr(push_utils,'send_push_to_user',push)
    client.post('/admin/makeup-requests/direct-synthetic/approve',data=payload)
    db.session.expire_all()
    assert item.status=='approved'
    assert observations and all(r[0]=='approved' and r[1] for r in observations)
    assert 'pending_notification_pushes' not in db.session.info


def test_commit_failure_rolls_back_and_sends_no_push(makeup,monkeypatch):
    app,db,tables,client,item=makeup
    login(client)
    payload=approval_payload(client)
    before=counts(db,tables)
    pushes=[]
    from app.utils import push_utils
    monkeypatch.setattr(push_utils,'send_push_to_user',lambda **kw:pushes.append(kw))
    real_commit=db.session.commit
    def fail(): raise RuntimeError('synthetic final commit failure')
    monkeypatch.setattr(db.session,'commit',fail)
    client.post('/admin/makeup-requests/direct-synthetic/approve',data=payload)
    monkeypatch.setattr(db.session,'commit',real_commit)
    db.session.expire_all()
    assert counts(db,tables)==before and not pushes
    assert item.status=='pending' and item.parent_conversation_id is None
    assert 'pending_notification_pushes' not in db.session.info


def test_push_failure_keeps_committed_approval(makeup,monkeypatch):
    app,db,tables,client,item=makeup
    login(client)
    payload=approval_payload(client)
    from app.utils import push_utils
    def fail(**kw): raise RuntimeError('synthetic push failure')
    monkeypatch.setattr(push_utils,'send_push_to_user',fail)
    assert client.post('/admin/makeup-requests/direct-synthetic/approve',data=payload).status_code==302
    db.session.expire_all()
    assert item.status=='approved'
    assert Notification.query.filter_by(user_id='parent',notification_type='makeup_approved').count()==1


def test_legacy_notification_still_commits_when_no_caller_transaction(makeup):
    app,db,tables,client,item=makeup
    Notification.create_notification(user_id='parent',notification_type='synthetic',title='Synthetic',message='Synthetic')
    db.session.rollback()
    assert Notification.query.filter_by(notification_type='synthetic').count()==1


def test_nested_transaction_refused_and_flag_cleaned(makeup):
    app,db,tables,client,item=makeup
    with pytest.raises(RuntimeError,match='Nested'):
        with notification_transaction():
            with notification_transaction(): pass
    assert 'pending_notification_pushes' not in db.session.info
