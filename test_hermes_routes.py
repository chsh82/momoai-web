# -*- coding: utf-8 -*-
"""헤르메스(/admin/hermes) 라우트 HTTP 레벨 확인 스크립트.

이 저장소의 기존 관례(test_mileage_essay_type.py 등)를 그대로 따른다 -
app.test_client() 하나로 실제 로그인(session_transaction) 후 실제 DB에
반영되는지 확인하고, 끝에 테스트 데이터를 전부 삭제한다. Anthropic 호출은
모킹해서 실제 API 비용이 들지 않게 한다.

실행: python test_hermes_routes.py
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
from app.models.hermes_log import HermesCommandLog
from app.models.api_usage_log import ApiUsageLog
import app.utils.hermes_agent as hermes_agent

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
    c = Course(course_name=name, course_code=f'TESTC{uuid.uuid4().hex[:10]}',
               grade='초5', course_type=course_type, teacher_id=teacher_id,
               weekday=0, start_time=None, end_time=None,
               start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=90),
               status='active')
    db.session.add(c)
    db.session.flush()
    created_course_ids.append(c.course_id)
    return c


def fake_parse(action_type, **overrides):
    """parse_hermes_command를 모킹한다 - 실제 Anthropic 호출을 하지 않는다."""
    base = {
        'action_type': action_type, 'confidence': 'high', 'unclear_reason': None,
        'student_name': None, 'course_hint': None, 'date': None, 'time': None,
        'status': None, 'reason': None, '_usage': None,
    }
    base.update(overrides)

    def _mock(text, today=None):
        return dict(base)
    return _mock


with app.app_context():
    print("=" * 70)
    print("헤르메스(/admin/hermes) 라우트 확인 스크립트")
    print("=" * 70)

    admin = make_user('_hermes_admin', 'master_admin', 1)
    teacher = make_user('_hermes_teacher', 'teacher', 4)
    parent = make_user('_hermes_parent', 'parent', 5)
    student = make_student('_hermes_김민준', teacher.user_id)
    from app.models.parent_student import ParentStudent
    db.session.add(ParentStudent(parent_id=parent.user_id, student_id=student.student_id,
                                 relation_type='parent', permission_level='full', is_active=True))
    source_course = make_course('_hermes_국어정규반', teacher.user_id)
    db.session.add(CourseEnrollment(course_id=source_course.course_id,
                                    student_id=student.student_id, status='active'))
    db.session.commit()

    admin_id, teacher_id = admin.user_id, teacher.user_id
    parent_id, student_id = parent.user_id, student.student_id
    source_course_id = source_course.course_id

login_as(admin_id)

print("\n[1] schedule_makeup 정상 경로 - 보강 수업 생성 + 알림 발송")
makeup_date = (date.today() + timedelta(days=14))
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_김민준', date=makeup_date.isoformat(), time='17:00',
)
resp = client.post('/admin/hermes/message', json={'text': f'_hermes_김민준 학생 {makeup_date} 5시 보강'})
data = resp.get_json()
check("응답 status 200", resp.status_code == 200)
check(f"응답 status=success (실제: {data.get('status')})", data.get('status') == 'success')

with app.app_context():
    makeup_courses = Course.query.filter(Course.course_name.like('%_hermes_김민준%'),
                                         Course.course_id != source_course_id).all()
    check(f"보강 Course 1건 생성됨 (실제: {len(makeup_courses)}건)", len(makeup_courses) == 1)
    if makeup_courses:
        mc = makeup_courses[0]
        created_course_ids.append(mc.course_id)
        sessions = CourseSession.query.filter_by(course_id=mc.course_id).all()
        check(f"보강 CourseSession 1건 생성됨 (실제: {len(sessions)}건)", len(sessions) == 1)
        enrolled = CourseEnrollment.query.filter_by(course_id=mc.course_id, student_id=student_id).first()
        check("학생이 보강 수업에 등록됨", enrolled is not None)

        notifs = Notification.query.filter(
            Notification.user_id.in_([parent_id, teacher_id]),
            Notification.notification_type.in_(['enrollment_applied', 'makeup_student_joining']),
        ).all()
        check(f"학부모/강사 알림 생성됨 (실제: {len(notifs)}건)", len(notifs) >= 1)

    log = HermesCommandLog.query.filter_by(thread_id=data.get('thread_id')).first()
    check("HermesCommandLog status=success로 기록됨", log is not None and log.status == 'success')
    check("HermesCommandLog에 생성된 course_id가 연결됨",
          log is not None and log.related_entity_id == (makeup_courses[0].course_id if makeup_courses else None))

print("\n[2] 학생 이름을 못 찾으면 needs_clarification으로 응답(실행 안 함)")
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='존재하지않는학생이름', date=makeup_date.isoformat(),
)
resp2 = client.post('/admin/hermes/message', json={'text': '존재하지않는학생이름 학생 보강 잡아줘'})
data2 = resp2.get_json()
check(f"응답 status=needs_clarification (실제: {data2.get('status')})",
      data2.get('status') == 'needs_clarification')
check("명확화 질문에 '찾을 수 없습니다' 포함", '찾을 수 없습니다' in (data2.get('reply_text') or ''))

with app.app_context():
    before_count = Course.query.filter_by(teacher_id=teacher_id).count()
    check(f"실행되지 않아 Course가 더 생기지 않음 (현재 총 {before_count}건, 보강+원수업=2건이어야 함)",
          before_count == 2)

print("\n[3] 날짜 없이 보강 요청하면 needs_clarification")
# 1번 테스트에서 이미 보강수업에 등록돼 수업이 2개가 된 학생이라 전용 학생을 새로 씀
# (course_hint 없이 활성 수업이 2개면 "어느 수업?" 질문이 먼저 나가 날짜 질문까지
# 도달하지 못함 - 그건 그것대로 맞는 동작이라 여기서 다시 검증하지 않는다).
with app.app_context():
    student3 = make_student('_hermes_박서연', teacher_id)
    course3 = make_course('_hermes_수학정규반', teacher_id)
    db.session.add(CourseEnrollment(course_id=course3.course_id, student_id=student3.student_id, status='active'))
    db.session.commit()
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_박서연', date=None,
)
resp3 = client.post('/admin/hermes/message', json={'text': '_hermes_박서연 학생 보강 잡아줘'})
data3 = resp3.get_json()
check(f"응답 status=needs_clarification (실제: {data3.get('status')})",
      data3.get('status') == 'needs_clarification')
check("날짜를 물어보는 질문", '날짜' in (data3.get('reply_text') or ''))

print("\n[4] master_admin이 아니면 403")
teacher2 = None
with app.app_context():
    teacher2 = make_user('_hermes_teacher2', 'teacher', 4)
    db.session.commit()
    teacher2_id = teacher2.user_id
login_as(teacher2_id)
resp4 = client.post('/admin/hermes/message', json={'text': '아무 말'})
check(f"teacher 권한으로는 302/403 (실제: {resp4.status_code})", resp4.status_code in (302, 403))

login_as(admin_id)

print("\n[5] mark_absence 정상 경로(오늘) - 출결 레코드 생성+결석 처리+알림")
with app.app_context():
    student5 = make_student('_hermes_이정기', teacher_id)
    parent5 = make_user('_hermes_parent5', 'parent', 5)
    from app.models.parent_student import ParentStudent as PS5
    db.session.add(PS5(parent_id=parent5.user_id, student_id=student5.student_id,
                       relation_type='parent', permission_level='full', is_active=True))
    course5 = make_course('_hermes_영어정규반', teacher_id)
    db.session.add(CourseEnrollment(course_id=course5.course_id, student_id=student5.student_id, status='active'))
    session5 = CourseSession(course_id=course5.course_id, session_number=1,
                             session_date=date.today(), status='scheduled')
    db.session.add(session5)
    db.session.commit()
    student5_id, parent5_id, course5_id, session5_id = (
        student5.student_id, parent5.user_id, course5.course_id, session5.session_id)

hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_이정기', date=date.today().isoformat(), status='absent',
)
resp5 = client.post('/admin/hermes/message', json={'text': '_hermes_이정기 학생 오늘 결석 처리'})
data5 = resp5.get_json()
check(f"응답 status=success (실제: {data5.get('status')})", data5.get('status') == 'success')

with app.app_context():
    att5 = Attendance.query.filter_by(session_id=session5_id, student_id=student5_id).first()
    check("Attendance 레코드가 새로 생성됨", att5 is not None)
    check(f"status=absent로 반영됨 (실제: {att5.status if att5 else None})",
          att5 is not None and att5.status == 'absent')
    notif5 = Notification.query.filter_by(user_id=parent5_id, notification_type='attendance_absent').first()
    check("학부모 알림 생성됨", notif5 is not None)

print("\n[6] mark_absence - 미래 날짜는 결석 예고(AbsenceNotice)로 처리")
tomorrow = date.today() + timedelta(days=1)
hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_이정기', date=tomorrow.isoformat(),
    status='absent', reason='가족 여행',
)
resp6 = client.post('/admin/hermes/message', json={'text': '_hermes_이정기 학생 내일 가족여행으로 결석 처리'})
data6 = resp6.get_json()
check(f"응답 status=success (실제: {data6.get('status')})", data6.get('status') == 'success')
with app.app_context():
    from app.models.absence_notice import AbsenceNotice
    notice = AbsenceNotice.query.filter_by(student_id=student5_id, course_id=course5_id).first()
    check("AbsenceNotice가 생성됨", notice is not None)
    if notice:
        check(f"notice_type=absent (실제: {notice.notice_type})", notice.notice_type == 'absent')
        check(f"사유가 반영됨 (실제: {notice.reason})", notice.reason == '가족 여행')
        check(f"날짜가 내일로 반영됨 (실제: {notice.absence_date})", notice.absence_date == tomorrow)
    teacher_notif = Notification.query.filter_by(user_id=teacher_id, notification_type='absence_notice').first()
    check("담당 강사에게 결석예고 알림 발송됨", teacher_notif is not None)

print("\n[6b] mark_absence - 미래 날짜 + excused는 거부(교사 판단 영역)")
hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_이정기', date=tomorrow.isoformat(), status='excused',
)
resp6b = client.post('/admin/hermes/message', json={'text': '_hermes_이정기 학생 내일 인정결석'})
data6b = resp6b.get_json()
check(f"응답 status=needs_clarification (실제: {data6b.get('status')})",
      data6b.get('status') == 'needs_clarification')
check("excused는 미래 지정 불가 안내", 'excused' in (data6b.get('reply_text') or '') or '인정결석' in (data6b.get('reply_text') or ''))

print("\n[6c] mark_absence - 미래 날짜 + 사유 없으면 재질문")
hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_이정기', date=tomorrow.isoformat(), status='absent', reason=None,
)
resp6c = client.post('/admin/hermes/message', json={'text': '_hermes_이정기 학생 내일 결석'})
data6c = resp6c.get_json()
check(f"응답 status=needs_clarification (실제: {data6c.get('status')})",
      data6c.get('status') == 'needs_clarification')
check("사유를 물어보는 질문", '사유' in (data6c.get('reply_text') or ''))

print("\n[7] mark_absence - 해당 날짜에 세션이 없으면 needs_clarification")
hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_이정기',
    date=(date.today() - timedelta(days=3)).isoformat(), status='absent',
)
resp7 = client.post('/admin/hermes/message', json={'text': '_hermes_이정기 학생 3일전 결석 처리'})
data7 = resp7.get_json()
check(f"응답 status=needs_clarification (실제: {data7.get('status')})",
      data7.get('status') == 'needs_clarification')
check("세션을 찾을 수 없다는 안내 포함", '찾을 수 없습니다' in (data7.get('reply_text') or ''))

created_student_ids.append(student5_id)
created_user_ids.append(parent5_id)
created_course_ids.append(course5_id)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    from app.models.absence_notice import AbsenceNotice
    HermesCommandLog.query.filter(HermesCommandLog.admin_user_id == admin_id).delete(synchronize_session=False)
    AbsenceNotice.query.filter(AbsenceNotice.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    Attendance.query.filter(Attendance.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    CourseEnrollment.query.filter(CourseEnrollment.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    CourseSession.query.filter(CourseSession.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    Course.query.filter(Course.course_id.in_(created_course_ids)).delete(synchronize_session=False)
    Notification.query.filter(Notification.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    ApiUsageLog.query.filter(ApiUsageLog.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    from app.models.parent_student import ParentStudent as PS
    PS.query.filter(PS.student_id.in_(created_student_ids)).delete(synchronize_session=False)
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
