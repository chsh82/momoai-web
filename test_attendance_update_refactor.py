# -*- coding: utf-8 -*-
"""app/teacher/routes.py의 update_attendance(PATCH)를
app/utils/course_utils.py의 apply_attendance_update로 리팩터한 뒤 동작이
완전히 동일한지 확인하는 회귀 스크립트(헤르메스 결석 처리 기능 작업 중
2026-10-12 리팩터).

실행: python test_attendance_update_refactor.py
"""
import uuid
from datetime import date, timedelta

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.notification import Notification
from app.models.parent_student import ParentStudent

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


def make_user(name, role, role_level):
    u = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
             name=name, role=role, role_level=role_level, is_active=True)
    u.set_password('test_password_only')
    db.session.add(u)
    db.session.flush()
    created_user_ids.append(u.user_id)
    return u


def make_student(name, teacher_id):
    s = Student(teacher_id=teacher_id, name=name, grade='초5',
                birth_date=date(2014, 1, 1), status='active')
    db.session.add(s)
    db.session.flush()
    created_student_ids.append(s.student_id)
    return s


def make_course(name, teacher_id, course_type='정규반'):
    c = Course(course_name=name, course_code=f'TESTA{uuid.uuid4().hex[:10]}',
               grade='초5', course_type=course_type, teacher_id=teacher_id,
               weekday=0, start_date=date.today() - timedelta(days=30),
               end_date=date.today() + timedelta(days=90), status='active')
    db.session.add(c)
    db.session.flush()
    created_course_ids.append(c.course_id)
    return c


with app.app_context():
    print("=" * 70)
    print("update_attendance 리팩터 회귀 확인 스크립트")
    print("=" * 70)

    teacher = make_user('_attref_teacher', 'teacher', 4)
    parent = make_user('_attref_parent', 'parent', 5)
    student = make_student('_attref_학생', teacher.user_id)
    db.session.add(ParentStudent(parent_id=parent.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='full', is_active=True))
    course = make_course('_attref_정규반', teacher.user_id)
    enrollment = CourseEnrollment(course_id=course.course_id, student_id=student.student_id, status='active')
    db.session.add(enrollment)
    db.session.flush()

    session1 = CourseSession(course_id=course.course_id, session_number=1,
                             session_date=date.today(), status='scheduled')
    session2 = CourseSession(course_id=course.course_id, session_number=2,
                             session_date=date.today() + timedelta(days=7), status='scheduled')
    session_pending = CourseSession(course_id=course.course_id, session_number=3,
                                    session_date=date.today() + timedelta(days=14), status='pending_review')
    db.session.add_all([session1, session2, session_pending])
    db.session.flush()

    att1 = Attendance(session_id=session1.session_id, student_id=student.student_id,
                      enrollment_id=enrollment.enrollment_id, status='present')
    att2 = Attendance(session_id=session2.session_id, student_id=student.student_id,
                      enrollment_id=enrollment.enrollment_id, status='present')
    att_pending = Attendance(session_id=session_pending.session_id, student_id=student.student_id,
                             enrollment_id=enrollment.enrollment_id, status='present')
    db.session.add_all([att1, att2, att_pending])
    db.session.commit()

    teacher_id, parent_id, student_id = teacher.user_id, parent.user_id, student.student_id
    att1_id, att2_id, att_pending_id = att1.attendance_id, att2.attendance_id, att_pending.attendance_id
    enrollment_id = enrollment.enrollment_id

login_as(teacher_id)

print("\n[1] 정상 결석 처리 - 상태 변경 + 학부모 알림 발송")
resp1 = client.patch(f'/teacher/api/attendance/{att1_id}', json={'status': 'absent', 'notes': '감기'})
data1 = resp1.get_json()
check(f"응답 200, success=True (실제: {resp1.status_code}, {data1.get('success')})",
      resp1.status_code == 200 and data1.get('success') is True)
check(f"status=absent로 응답 (실제: {data1.get('status')})", data1.get('status') == 'absent')

with app.app_context():
    a = Attendance.query.get(att1_id)
    check(f"DB에도 absent로 반영됨 (실제: {a.status})", a.status == 'absent')
    check("notes 반영됨", a.notes == '감기')
    check("checked_by가 teacher로 기록됨", a.checked_by == teacher_id)
    notifs = Notification.query.filter_by(user_id=parent_id, notification_type='attendance_absent').all()
    check(f"학부모 알림 1건 발송됨 (실제: {len(notifs)}건)", len(notifs) == 1)

    enr = CourseEnrollment.query.get(enrollment_id)
    # update_enrollment_attendance_stats는 attendance_checked=True인 세션만 집계 -
    # 이 세션들은 체크 안 했으니 0/0/0 그대로인 게 맞다(기존 동작 그대로 확인).
    check(f"attendance_checked 안 된 세션은 집계 제외(기존 동작 그대로, absent_sessions={enr.absent_sessions})",
          enr.absent_sessions == 0)

print("\n[2] 잘못된 상태값 → 400 (기존과 동일)")
resp2 = client.patch(f'/teacher/api/attendance/{att2_id}', json={'status': 'invalid_status'})
check(f"잘못된 status는 400 (실제: {resp2.status_code})", resp2.status_code == 400)
with app.app_context():
    a2 = Attendance.query.get(att2_id)
    check("상태가 안 바뀜(present 유지)", a2.status == 'present')

print("\n[3] pending_review 세션은 absent여도 알림 미발송(기존 동작)")
with app.app_context():
    before = Notification.query.filter_by(user_id=parent_id, notification_type='attendance_absent').count()
resp3 = client.patch(f'/teacher/api/attendance/{att_pending_id}', json={'status': 'absent'})
check(f"응답 200 (실제: {resp3.status_code})", resp3.status_code == 200)
with app.app_context():
    after = Notification.query.filter_by(user_id=parent_id, notification_type='attendance_absent').count()
    check(f"pending_review 세션은 알림 추가 발송 안 됨 (이전 {before}건 -> 이후 {after}건)", after == before)
    a_pending = Attendance.query.get(att_pending_id)
    check("상태는 그래도 absent로 바뀜(알림만 안 감)", a_pending.status == 'absent')

print("\n[4] absent_makeup 자동전환 - 다른 보강 수업에 active 등록돼 있으면 absent 대신 absent_makeup")
with app.app_context():
    makeup_course = make_course('_attref_보강', teacher.user_id, course_type='보강(정규반)')
    makeup_session = CourseSession(course_id=makeup_course.course_id, session_number=1,
                                   session_date=date.today() + timedelta(days=1), status='scheduled')
    db.session.add(makeup_session)
    db.session.flush()
    db.session.add(CourseEnrollment(course_id=makeup_course.course_id, student_id=student_id, status='active'))
    # att2를 다시 present로 되돌려서 재사용
    a2 = Attendance.query.get(att2_id)
    a2.status = 'present'
    db.session.commit()

resp4 = client.patch(f'/teacher/api/attendance/{att2_id}', json={'status': 'absent'})
data4 = resp4.get_json()
check(f"응답에서 absent_makeup으로 변환됨 (실제: {data4.get('status')})", data4.get('status') == 'absent_makeup')
with app.app_context():
    a2_after = Attendance.query.get(att2_id)
    check(f"DB에도 absent_makeup 반영됨 (실제: {a2_after.status})", a2_after.status == 'absent_makeup')

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    Attendance.query.filter(Attendance.student_id == student_id).delete(synchronize_session=False)
    CourseSession.query.filter(CourseSession.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    CourseEnrollment.query.filter(CourseEnrollment.student_id == student_id).delete(synchronize_session=False)
    Course.query.filter(Course.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    Notification.query.filter(Notification.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    ParentStudent.query.filter(ParentStudent.student_id == student_id).delete(synchronize_session=False)
    Student.query.filter(Student.student_id == student_id).delete(synchronize_session=False)
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
