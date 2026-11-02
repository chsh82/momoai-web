"""Two actual HTTP requests and independent SQLite sessions, stale initial reads."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from flask_sqlalchemy.query import Query
from conftest import login
from test_approval import approval_payload, counts
from app.models.makeup_request import MakeupClassRequest
import pytest


@pytest.mark.parametrize('mode',['direct','normal','parent-race'])
def test_concurrent_different_dates_cannot_create_two_courses(makeup,monkeypatch,mode):
    app,db,tables,client,item=makeup
    from datetime import date,time
    if mode != 'direct':
        item.teacher_confirmed=True
        item.teacher_proposed_date=date(2026,11,3)
        item.teacher_proposed_time=time(15,20)
        db.session.commit()
    app.config['MOMOBOT_PARENT_WIDGET_ENABLED']=True
    barrier=Barrier(2)
    original=Query.get_or_404
    def stale_read(self, ident, *a, **kw):
        result=original(self,ident,*a,**kw)
        if isinstance(result,MakeupClassRequest):
            barrier.wait(timeout=15)
        return result
    monkeypatch.setattr(Query,'get_or_404',stale_read)
    before=counts(db,tables)
    def submit(day):
        with app.app_context():
            c=app.test_client()
            login(c)
            payload=approval_payload(c)
            if mode == 'parent-race' and day == '2026-11-03':
                login(c,'parent')
                return c.post('/widget/makeup/direct-synthetic/confirm-schedule').status_code
            if mode == 'normal':
                payload['approval_mode']='normal'
            payload['makeup_date']=day
            return c.post('/admin/makeup-requests/direct-synthetic/approve',data=payload).status_code
    # Release main thread's read transaction; workers use separate connections.
    db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(submit,['2026-11-02','2026-11-03']))
    if mode == 'parent-race':
        assert results[0]==302 and results[1] in (200,500), results
        # Existing widget returns controlled JSON 500 when it loses the race.
    else:
        assert results==[302,302]
    item=db.session.get(MakeupClassRequest,'direct-synthetic')
    assert item.status=='approved'
    assert counts(db,tables)['courses']==before['courses']+1
    assert counts(db,tables)['course_sessions']==before['course_sessions']+1
