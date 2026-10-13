# -*- coding: utf-8 -*-
"""환불 요청 제출의 permission_level(view_only) 체크 확인 스크립트.

2026-10-13: ParentStudent.permission_level이 결제/환불 쪽 어디에서도
검사되지 않아, 조회 전용(view_only) 보호자도 환불 요청을 제출할 수 있던
문제를 고쳤다 - 이 스크립트는 그 수정이 실제로 동작하는지 확인한다.
test_hermes_routes.py와 같은 관례(app.test_client() + session_transaction
로그인, 실제 DB에 반영되는지 확인 후 전부 삭제)를 따른다.

실행: python test_refund_request_permission.py
"""
import uuid
from datetime import date, timedelta

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.course import Course, CourseEnrollment
from app.models.payment import Payment
from app.models.parent_student import ParentStudent
from app.models.refund_request import RefundRequest

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
created_enrollment_ids = []
created_payment_ids = []
created_request_ids = []

with app.app_context():
    print("=" * 70)
    print("환불 요청 view_only 권한 체크 확인 스크립트")
    print("=" * 70)

    teacher = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                   name='_refundperm_teacher', role='teacher', role_level=4, is_active=True)
    teacher.set_password('test_password_only')
    db.session.add(teacher)
    db.session.flush()
    created_user_ids.append(teacher.user_id)

    student = Student(teacher_id=teacher.user_id, name='_refundperm_student', grade='초5',
                       birth_date=date(2014, 1, 1), status='active')
    db.session.add(student)
    db.session.flush()
    created_student_ids.append(student.student_id)

    course = Course(course_name='_refundperm_course', course_code=f'TESTC{uuid.uuid4().hex[:10]}',
                     grade='초5', course_type='정규반', teacher_id=teacher.user_id,
                     weekday=0, start_time=None, end_time=None,
                     start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=90),
                     status='active')
    db.session.add(course)
    db.session.flush()
    created_course_ids.append(course.course_id)

    enrollment = CourseEnrollment(course_id=course.course_id, student_id=student.student_id, status='active')
    db.session.add(enrollment)
    db.session.flush()
    created_enrollment_ids.append(enrollment.enrollment_id)

    payment = Payment(enrollment_id=enrollment.enrollment_id, course_id=course.course_id,
                       student_id=student.student_id, amount=100000, status='completed')
    db.session.add(payment)
    db.session.flush()
    created_payment_ids.append(payment.payment_id)

    parent_view_only = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                             name='_refundperm_parent_view', role='parent', role_level=5, is_active=True)
    parent_view_only.set_password('test_password_only')
    db.session.add(parent_view_only)
    db.session.flush()
    created_user_ids.append(parent_view_only.user_id)
    db.session.add(ParentStudent(parent_id=parent_view_only.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='view_only', is_active=True))

    parent_full = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                        name='_refundperm_parent_full', role='parent', role_level=5, is_active=True)
    parent_full.set_password('test_password_only')
    db.session.add(parent_full)
    db.session.flush()
    created_user_ids.append(parent_full.user_id)
    db.session.add(ParentStudent(parent_id=parent_full.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='full', is_active=True))

    db.session.commit()
    payment_id = payment.payment_id
    parent_view_only_id = parent_view_only.user_id
    parent_full_id = parent_full.user_id

print("\n[1] view_only 보호자는 결제 내역 조회는 그대로 가능")
login_as(parent_view_only_id)
resp1 = client.get('/parent/payments')
check(f"결제 목록 조회 200 (실제: {resp1.status_code})", resp1.status_code == 200)

print("\n[2] view_only 보호자는 환불 요청 제출이 차단됨(DB에 생성 안 됨)")
resp2 = client.post(f'/refund-request/new/{payment_id}', data={'reason': '_refundperm 사유'}, follow_redirects=True)
check(f"요청 응답 200 (실제: {resp2.status_code})", resp2.status_code == 200)
html2 = resp2.get_data(as_text=True)
check("'조회 권한만 있어' 안내 문구 노출", '조회 권한만 있어' in html2)
with app.app_context():
    blocked = RefundRequest.query.filter_by(payment_id=payment_id, requester_id=parent_view_only_id).first()
    check("view_only 보호자의 RefundRequest가 생성되지 않음", blocked is None)

print("\n[3] full 권한 보호자는 환불 요청 제출이 정상 동작")
login_as(parent_full_id)
resp3 = client.post(f'/refund-request/new/{payment_id}', data={'reason': '_refundperm 정상 사유'}, follow_redirects=True)
check(f"요청 응답 200 (실제: {resp3.status_code})", resp3.status_code == 200)
with app.app_context():
    created = RefundRequest.query.filter_by(payment_id=payment_id, requester_id=parent_full_id).first()
    check("full 보호자의 RefundRequest는 정상 생성됨", created is not None)
    if created:
        created_request_ids.append(created.request_id)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    RefundRequest.query.filter(RefundRequest.request_id.in_(created_request_ids)).delete(synchronize_session=False)
    Payment.query.filter(Payment.payment_id.in_(created_payment_ids)).delete(synchronize_session=False)
    CourseEnrollment.query.filter(CourseEnrollment.enrollment_id.in_(created_enrollment_ids)).delete(synchronize_session=False)
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
