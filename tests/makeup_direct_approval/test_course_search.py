"""Actual live course route and HTML, synthetic records only."""
from datetime import date, datetime, time
import re
import pytest
from conftest import login
from app.models import Course, CourseEnrollment


def seed(db):
    for cid, status, day, year in [('active-old','active',3,2021),('active-new','active',2,2022),('ended-new','completed',0,2025),('ended-old','completed',1,2024)]:
        db.session.add(Course(course_id=cid,course_code='MATCH-'+cid,course_name='MATCH '+cid,teacher_id='teacher-a',grade='초4',course_type='정규반',status=status,weekday=day,start_time=time(10),start_date=date(2021,1,1),end_date=date(2026,12,31),created_at=datetime(year,1,1)))
        db.session.add(CourseEnrollment(course_id=cid,student_id='s',status='active'))
    db.session.commit()


def order(client, **params):
    response=client.get('/admin/courses',query_string=params)
    assert response.status_code==200
    return re.findall(r'href="/admin/courses/(active-old|active-new|ended-new|ended-old)"',response.get_data(as_text=True))


@pytest.mark.parametrize('search',['MATCH','Synthetic teacher-a',"O'Neil",'초4','정규반'])
@pytest.mark.parametrize('sort,expected',[('newest',['active-new','active-old','ended-new','ended-old']),('weekday',['active-new','active-old','ended-new','ended-old'])])
def test_search_active_first_in_actual_html(makeup,search,sort,expected):
    app,db,_,client,_=makeup
    seed(db);login(client)
    assert order(client,search=search,sort=sort)==expected


@pytest.mark.parametrize('sort,expected',[('newest',['ended-new','ended-old','active-new','active-old']),('weekday',['ended-new','ended-old','active-new','active-old'])])
def test_non_search_order_unchanged(makeup,sort,expected):
    app,db,_,client,_=makeup
    seed(db);login(client)
    assert order(client,sort=sort)==expected


def test_text_filters_and_student_merge_semantics_preserved(makeup):
    app,db,_,client,_=makeup
    seed(db);login(client)
    assert order(client,search='MATCH',status='completed')==['ended-new','ended-old']
    assert order(client,search='MATCH',weekday='3',teacher='teacher-a',grade='초4',course_type='정규반')==['active-old']
    # Live intentionally includes enrolled classes irrespective of text filters.
    assert order(client,search="O'Neil",status='completed',grade='초99')==['active-new','active-old','ended-new','ended-old']
    # Student and course name overlap must not duplicate cards.
    db.session.query(Course).filter(Course.course_id.like('active-%')).update({'course_name':"O'Neil"},synchronize_session=False)
    db.session.commit()
    assert order(client,search="O'Neil")==['active-new','active-old','ended-new','ended-old']


def test_search_requires_manager(makeup):
    app,db,_,client,_=makeup
    login(client,'teacher-a')
    assert client.get('/admin/courses?search=MATCH').status_code==403
