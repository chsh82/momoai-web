# -*- coding: utf-8 -*-
"""보강 신청 제출의 permission_level(view_only) 체크 확인 스크립트.

2026-10-13(모모봇 개발 D1): app/refund_request/routes.py의 환불 요청과
같은 패턴으로, app/parent_portal/routes.py의 보강 신청 제출에도
permission_level='view_only' 체크가 빠져 있던 문제를 고쳤다(디스커버리
보고서 3.1절에서 발견한 항목). test_refund_request_permission.py와
동일한 관례를 따른다.

실행: python test_makeup_request_permission.py
"""
import uuid
from datetime import date, timedelta

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.course import Course
from app.models.parent_student import ParentStudent
from app.models.makeup_request import MakeupClassRequest

app = create_app('development')
client = app.test_client()
failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


def login_as(user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = user_id
        sess['_fresh'] = True


created_user_ids = []
created_student_ids = []
created_course_ids = []
created_request_ids = []

with app.app_context():
    print("=" * 70)
    print("보강 신청 view_only 권한 체크 확인 스크립트")
    print("=" * 70)

    teacher = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                   name='_makeupperm_teacher', role='teacher', role_level=4, is_active=True)
    teacher.set_password('test_password_only')
    db.session.add(teacher)
    db.session.flush()
    created_user_ids.append(teacher.user_id)

    student = Student(teacher_id=teacher.user_id, name='_makeupperm_student', grade='초5',
                       birth_date=date(2014, 1, 1), status='active')
    db.session.add(student)
    db.session.flush()
    created_student_ids.append(student.student_id)

    course = Course(course_name='_makeupperm_course', course_code=f'TESTC{uuid.uuid4().hex[:10]}',
                     grade='초5', course_type='정규반', teacher_id=teacher.user_id,
                     weekday=0, start_time=None, end_time=None,
                     start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=90),
                     status='active', makeup_class_allowed=True)
    db.session.add(course)
    db.session.flush()
    created_course_ids.append(course.course_id)

    parent_view_only = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                             name='_makeupperm_parent_view', role='parent', role_level=5, is_active=True)
    parent_view_only.set_password('test_password_only')
    db.session.add(parent_view_only)
    db.session.flush()
    created_user_ids.append(parent_view_only.user_id)
    db.session.add(ParentStudent(parent_id=parent_view_only.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='view_only', is_active=True))

    parent_full = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                        name='_makeupperm_parent_full', role='parent', role_level=5, is_active=True)
    parent_full.set_password('test_password_only')
    db.session.add(parent_full)
    db.session.flush()
    created_user_ids.append(parent_full.user_id)
    db.session.add(ParentStudent(parent_id=parent_full.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='full', is_active=True))

    db.session.commit()
    student_id = student.student_id
    course_id = course.course_id
    parent_view_only_id = parent_view_only.user_id
    parent_full_id = parent_full.user_id

print("\n[1] view_only 보호자는 보강수업 목록 조회는 그대로 가능")
login_as(parent_view_only_id)
resp1 = client.get(f'/parent/makeup-classes/{student_id}')
check(f"보강수업 목록 조회 200 (실제: {resp1.status_code})", resp1.status_code == 200)

print("\n[2] view_only 보호자는 보강 신청 제출이 차단됨(DB에 생성 안 됨)")
resp2 = client.post(f'/parent/makeup-classes/{student_id}/request/{course_id}',
                    data={'reason': '_makeupperm 사유'}, follow_redirects=True)
check(f"요청 응답 200 (실제: {resp2.status_code})", resp2.status_code == 200)
html2 = resp2.get_data(as_text=True)
check("'조회 권한만 있어' 안내 문구 노출", '조회 권한만 있어' in html2)
with app.app_context():
    blocked = MakeupClassRequest.query.filter_by(
        student_id=student_id, requested_course_id=course_id, requested_by=parent_view_only_id,
    ).first()
    check("view_only 보호자의 MakeupClassRequest가 생성되지 않음", blocked is None)

print("\n[3] full 권한 보호자는 보강 신청 제출이 정상 동작")
login_as(parent_full_id)
resp3 = client.post(f'/parent/makeup-classes/{student_id}/request/{course_id}',
                    data={'reason': '_makeupperm 정상 사유'}, follow_redirects=True)
check(f"요청 응답 200 (실제: {resp3.status_code})", resp3.status_code == 200)
with app.app_context():
    created = MakeupClassRequest.query.filter_by(
        student_id=student_id, requested_course_id=course_id, requested_by=parent_full_id,
    ).first()
    check("full 보호자의 MakeupClassRequest는 정상 생성됨", created is not None)
    if created:
        created_request_ids.append(created.request_id)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    MakeupClassRequest.query.filter(MakeupClassRequest.request_id.in_(created_request_ids)).delete(synchronize_session=False)
    Course.query.filter(Course.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    ParentStudent.query.filter(ParentStudent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    Student.query.filter(Student.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    User.query.filter(User.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    db.session.commit()
    print("  삭제 완료")

print("\n" + "=" * 70)
if failures:
    print(f"결과: FAIL {len(failures)}건")
    for f in failures:
        print(f"  - {f}")
else:
    print("결과: 전체 PASS")
print("=" * 70)
