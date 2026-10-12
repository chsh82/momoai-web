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


def confirm(thread_id):
    return client.post(f'/admin/hermes/thread/{thread_id}/confirm').get_json()


def cancel(thread_id):
    return client.post(f'/admin/hermes/thread/{thread_id}/cancel').get_json()


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
    """parse_hermes_command를 모킹한다(단일 액션) - 실제 Anthropic 호출을 하지 않는다."""
    base = {
        'action_type': action_type, 'confidence': 'high', 'unclear_reason': None,
        'student_name': None, 'course_hint': None, 'teacher_name': None,
        'date': None, 'time': None, 'status': None, 'reason': None,
    }
    base.update(overrides)

    def _mock(text, today=None):
        return {'actions': [dict(base)], '_usage': None}
    return _mock


def fake_parse_multi(*action_overrides):
    """parse_hermes_command를 모킹한다(복합 액션 - 여러 개 액션 리스트)."""
    base = {
        'action_type': 'unrecognized', 'confidence': 'high', 'unclear_reason': None,
        'student_name': None, 'course_hint': None, 'teacher_name': None,
        'date': None, 'time': None, 'status': None, 'reason': None,
    }
    actions = []
    for overrides in action_overrides:
        a = dict(base)
        a.update(overrides)
        actions.append(a)

    def _mock(text, today=None):
        return {'actions': actions, '_usage': None}
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

print("\n[1] schedule_makeup 정상 경로 - 확인 전엔 아무 것도 안 만들고, 확인해야 생성+알림")
makeup_date = (date.today() + timedelta(days=14))
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_김민준', date=makeup_date.isoformat(), time='17:00',
)
resp = client.post('/admin/hermes/message', json={'text': f'_hermes_김민준 학생 {makeup_date} 5시 보강'})
data = resp.get_json()
check("응답 status 200", resp.status_code == 200)
check(f"응답 status=pending_confirmation (실제: {data.get('status')})", data.get('status') == 'pending_confirmation')

with app.app_context():
    before1 = Course.query.filter(Course.course_name.like('%_hermes_김민준%'),
                                  Course.course_id != source_course_id).count()
    check(f"확인 전엔 보강 Course가 생성되지 않음 (실제: {before1}건)", before1 == 0)

confirm_data = confirm(data['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm_data.get('status')})", confirm_data.get('status') == 'success')

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

print("\n[1b] 같은 thread를 두 번 확인해도 한 번만 실행됨(중복 확인 방지)")
confirm_data_2 = confirm(data['thread_id'])
check(f"두 번째 confirm은 '이미 처리됨' 응답 (실제: {confirm_data_2.get('reply_text')})",
      '이미 처리' in (confirm_data_2.get('reply_text') or ''))
with app.app_context():
    dup_count = Course.query.filter(Course.course_name.like('%_hermes_김민준%'),
                                    Course.course_id != source_course_id).count()
    check(f"보강 Course가 여전히 1건(중복 생성 안 됨, 실제: {dup_count}건)", dup_count == 1)

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
    student3_id, course3_id = student3.student_id, course3.course_id
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_박서연', date=None,
)
resp3 = client.post('/admin/hermes/message', json={'text': '_hermes_박서연 학생 보강 잡아줘'})
data3 = resp3.get_json()
check(f"응답 status=needs_clarification (실제: {data3.get('status')})",
      data3.get('status') == 'needs_clarification')
check("날짜를 물어보는 질문", '날짜' in (data3.get('reply_text') or ''))
check(f"clarification.type=date로 날짜 선택 UI 힌트 포함 (실제: {data3.get('clarification')})",
      (data3.get('clarification') or {}).get('type') == 'date')

print("\n[3b] GET /admin/hermes/thread/<id>에서도 clarification 힌트가 복원됨")
resp3b = client.get(f"/admin/hermes/thread/{data3['thread_id']}")
items3b = resp3b.get_json().get('items', [])
check("스레드 재조회 시에도 마지막 항목에 clarification.type=date 포함",
      items3b and (items3b[-1].get('clarification') or {}).get('type') == 'date')

print("\n[3c] 활성 수업이 여러 개면 clarification.type=course_choice로 버튼 선택 힌트 제공")
with app.app_context():
    student3c = make_student('_hermes_한지민', teacher_id)
    course3c_a = make_course('_hermes_영어정규반A', teacher_id)
    course3c_b = make_course('_hermes_영어정규반B', teacher_id)
    db.session.add(CourseEnrollment(course_id=course3c_a.course_id, student_id=student3c.student_id, status='active'))
    db.session.add(CourseEnrollment(course_id=course3c_b.course_id, student_id=student3c.student_id, status='active'))
    db.session.commit()
    student3c_id = student3c.student_id
    course3c_a_id, course3c_b_id = course3c_a.course_id, course3c_b.course_id

hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_한지민', date=makeup_date.isoformat(),
)
resp3c = client.post('/admin/hermes/message', json={'text': '_hermes_한지민 학생 보강 잡아줘'})
data3c = resp3c.get_json()
check(f"응답 status=needs_clarification (실제: {data3c.get('status')})",
      data3c.get('status') == 'needs_clarification')
clar3c = data3c.get('clarification') or {}
check(f"clarification.type=course_choice (실제: {clar3c.get('type')})", clar3c.get('type') == 'course_choice')
option_ids = {o.get('course_id') for o in clar3c.get('options', [])}
check(f"options에 수업 2개 모두 포함됨 (실제: {option_ids})",
      {course3c_a_id, course3c_b_id} <= option_ids)

print("\n[3d] 결석 날짜를 안 주면 수업 요일 기준 이번주 날짜를 추정해 제안함")
with app.app_context():
    student3d = make_student('_hermes_오지훈', teacher_id)
    course3d = make_course('_hermes_사회정규반', teacher_id)  # make_course 기본값 weekday=0(월요일)
    db.session.add(CourseEnrollment(course_id=course3d.course_id, student_id=student3d.student_id, status='active'))
    this_monday = date.today() - timedelta(days=date.today().weekday())
    session3d = CourseSession(course_id=course3d.course_id, session_number=1,
                              session_date=this_monday, status='scheduled')
    db.session.add(session3d)
    db.session.commit()

hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_오지훈', status='absent', date=None,
)
resp3d = client.post('/admin/hermes/message', json={'text': '_hermes_오지훈 학생 이번주 수업 결석 예정'})
data3d = resp3d.get_json()
check(f"응답 status=needs_clarification (실제: {data3d.get('status')})",
      data3d.get('status') == 'needs_clarification')
clar3d = data3d.get('clarification') or {}
check(f"clarification.type=date (실제: {clar3d.get('type')})", clar3d.get('type') == 'date')
check(f"이번주 월요일 날짜를 제안함 (실제: {clar3d.get('suggested_date')}, 기대: {this_monday.isoformat()})",
      clar3d.get('suggested_date') == this_monday.isoformat())
check("안내 문구에 '월요일' 포함", '월요일' in (data3d.get('reply_text') or ''))

print("\n[3e] 추정 날짜에 실제 세션이 없으면(휴강 등) 추측하지 않고 평범한 날짜 질문만")
with app.app_context():
    student3e = make_student('_hermes_배수지', teacher_id)
    course3e = make_course('_hermes_과학정규반B', teacher_id)  # weekday=0이지만 이번주 세션을 안 만들어둠
    db.session.add(CourseEnrollment(course_id=course3e.course_id, student_id=student3e.student_id, status='active'))
    db.session.commit()

hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_배수지', status='absent', date=None,
)
resp3e = client.post('/admin/hermes/message', json={'text': '_hermes_배수지 학생 이번주 결석 예정'})
data3e = resp3e.get_json()
clar3e = data3e.get('clarification') or {}
check(f"clarification.type=date, suggested_date는 없음(세션 없어 추측 안 함) (실제: {clar3e})",
      clar3e.get('type') == 'date' and 'suggested_date' not in clar3e)

print("\n[4] teacher(role_level 4)도 접근 가능하지만, 담당 범위 밖 학생은 못 봄")
teacher2 = None
with app.app_context():
    teacher2 = make_user('_hermes_teacher2', 'teacher', 4)
    db.session.commit()
    teacher2_id, teacher2_name = teacher2.user_id, teacher2.name
login_as(teacher2_id)
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_김민준', date=makeup_date.isoformat(),
)
resp4 = client.post('/admin/hermes/message', json={'text': '_hermes_김민준 학생 보강'})
check(f"teacher 권한으로도 200 (실제: {resp4.status_code})", resp4.status_code == 200)
data4 = resp4.get_json()
check(f"응답 status=needs_clarification (실제: {data4.get('status')})",
      data4.get('status') == 'needs_clarification')
check("담당 수업에 등록되어 있지 않다는 범위 안내",
      '담당하는 수업에 등록되어 있지 않습니다' in (data4.get('reply_text') or ''))

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
check(f"응답 status=pending_confirmation (실제: {data5.get('status')})", data5.get('status') == 'pending_confirmation')
with app.app_context():
    check("확인 전엔 Attendance 레코드가 없음",
          Attendance.query.filter_by(session_id=session5_id, student_id=student5_id).first() is None)

confirm5 = confirm(data5['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm5.get('status')})", confirm5.get('status') == 'success')

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
check(f"응답 status=pending_confirmation (실제: {data6.get('status')})", data6.get('status') == 'pending_confirmation')
with app.app_context():
    from app.models.absence_notice import AbsenceNotice
    check("확인 전엔 AbsenceNotice가 없음",
          AbsenceNotice.query.filter_by(student_id=student5_id, course_id=course5_id).first() is None)

confirm6 = confirm(data6['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm6.get('status')})", confirm6.get('status') == 'success')

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

print("\n[8] schedule_makeup - 다른 강사 지정(teacher_name)")
with app.app_context():
    teacher3 = make_user('_hermes_teacher3', 'teacher', 4)
    db.session.commit()
    teacher3_id, teacher3_name = teacher3.user_id, teacher3.name

hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_김민준', course_hint='_hermes_국어정규반',
    date=makeup_date.isoformat(), time='18:00', teacher_name=teacher3_name,
)
resp8 = client.post('/admin/hermes/message', json={'text': f'_hermes_김민준 학생 {makeup_date} 6시 {teacher3_name} 강사와 보강'})
data8 = resp8.get_json()
check(f"응답 status=pending_confirmation (실제: {data8.get('status')})", data8.get('status') == 'pending_confirmation')
check(f"미리보기에 지정 강사 이름 포함 (실제: {teacher3_name in (data8.get('reply_text') or '')})",
      teacher3_name in (data8.get('reply_text') or ''))

confirm8 = confirm(data8['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm8.get('status')})", confirm8.get('status') == 'success')
check(f"confirm 응답에도 지정 강사 이름 포함 (실제: {teacher3_name in (confirm8.get('reply_text') or '')})",
      teacher3_name in (confirm8.get('reply_text') or ''))

with app.app_context():
    mc2 = Course.query.filter(Course.course_name.like('%_hermes_김민준%'), Course.teacher_id == teacher3_id).first()
    check("지정한 강사로 보강 Course가 생성됨", mc2 is not None)
    if mc2:
        created_course_ids.append(mc2.course_id)
created_user_ids.append(teacher3_id)

print("\n[9] schedule_makeup - 강사 이름을 못 찾으면 needs_clarification(실행 안 함)")
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_김민준', course_hint='_hermes_국어정규반',
    date=makeup_date.isoformat(), teacher_name='존재하지않는강사',
)
with app.app_context():
    before9 = Course.query.filter(Course.course_name.like('%_hermes_김민준%')).count()
resp9 = client.post('/admin/hermes/message', json={'text': '_hermes_김민준 학생 보강(존재하지않는강사 강사)'})
data9 = resp9.get_json()
check(f"응답 status=needs_clarification (실제: {data9.get('status')})",
      data9.get('status') == 'needs_clarification')
check("강사를 찾을 수 없다는 안내", '찾을 수 없습니다' in (data9.get('reply_text') or ''))
with app.app_context():
    after9 = Course.query.filter(Course.course_name.like('%_hermes_김민준%')).count()
    check(f"실행되지 않아 Course가 추가되지 않음 (이전 {before9}건 -> 이후 {after9}건)", before9 == after9)

print("\n[10] 복합 명령 - 결석 처리 + 보강 일정을 한 번에(둘 다 실행)")
with app.app_context():
    student10 = make_student('_hermes_최선우', teacher_id)
    course10 = make_course('_hermes_복합수업', teacher_id)
    db.session.add(CourseEnrollment(course_id=course10.course_id, student_id=student10.student_id, status='active'))
    session10 = CourseSession(course_id=course10.course_id, session_number=1,
                              session_date=date.today(), status='scheduled')
    db.session.add(session10)
    db.session.commit()
    student10_id, course10_id, session10_id = student10.student_id, course10.course_id, session10.session_id

makeup_date10 = date.today() + timedelta(days=10)
hermes_agent.parse_hermes_command = fake_parse_multi(
    {'action_type': 'mark_absence', 'student_name': '_hermes_최선우',
     'date': date.today().isoformat(), 'status': 'absent'},
    {'action_type': 'schedule_makeup', 'student_name': '_hermes_최선우',
     'date': makeup_date10.isoformat(), 'time': '20:00'},
)
resp10 = client.post('/admin/hermes/message', json={'text': '_hermes_최선우 학생 오늘 결석 후 다음주 보강'})
data10 = resp10.get_json()
check(f"응답 status=pending_confirmation (실제: {data10.get('status')})", data10.get('status') == 'pending_confirmation')
check(f"미리보기에 결석+보강 두 계획 모두 포함(줄바꿈 2개 이상): {(data10.get('reply_text') or '').count(chr(10))}건",
      (data10.get('reply_text') or '').count('\n') >= 2)
with app.app_context():
    check("확인 전엔 결석 처리가 안 됨",
          Attendance.query.filter_by(session_id=session10_id, student_id=student10_id).first() is None)
    check("확인 전엔 보강 Course도 안 생김",
          Course.query.filter(Course.course_name.like('%_hermes_최선우%'),
                              Course.course_id != course10_id).count() == 0)

confirm10 = confirm(data10['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm10.get('status')})", confirm10.get('status') == 'success')

with app.app_context():
    att10 = Attendance.query.filter_by(session_id=session10_id, student_id=student10_id).first()
    # 결석 처리(액션1) 후 보강 일정 생성(액션2)이 enroll_student_to_course의
    # _mark_recent_absent_as_makeup()을 거쳐 방금 그 결석을 소급으로
    # absent_makeup으로 바꾼다 - 결석+보강 복합 명령의 의도된 상호작용.
    check(f"결석 처리 실제 반영됨(보강 연결로 absent_makeup까지 전환, 실제: {att10.status if att10 else None})",
          att10 is not None and att10.status in ('absent', 'absent_makeup'))
    mc10 = Course.query.filter(Course.course_name.like('%_hermes_최선우%'), Course.course_id != course10_id).first()
    check("보강 Course도 실제 생성됨", mc10 is not None)
    if mc10:
        created_course_ids.append(mc10.course_id)
    logs10 = HermesCommandLog.query.filter_by(thread_id=data10.get('thread_id')).all()
    check(f"HermesCommandLog가 액션 2개만큼 2건 기록됨 (실제: {len(logs10)}건)", len(logs10) == 2)

print("\n[11] 복합 명령 - 한 액션이 모호하면 둘 다 실행 안 함(전부 검증 후 전부 실행)")
with app.app_context():
    before11_att = Attendance.query.filter_by(student_id=student10_id).count()
    before11_course = Course.query.filter(Course.course_name.like('%_hermes_최선우%')).count()

hermes_agent.parse_hermes_command = fake_parse_multi(
    {'action_type': 'mark_absence', 'student_name': '_hermes_최선우',
     'date': date.today().isoformat(), 'status': 'absent'},
    {'action_type': 'schedule_makeup', 'student_name': '존재하지않는학생',
     'date': makeup_date10.isoformat()},
)
resp11 = client.post('/admin/hermes/message', json={'text': '_hermes_최선우 학생 오늘 결석 후 존재하지않는학생 보강'})
data11 = resp11.get_json()
check(f"응답 status=needs_clarification (실제: {data11.get('status')})",
      data11.get('status') == 'needs_clarification')
with app.app_context():
    after11_att = Attendance.query.filter_by(student_id=student10_id).count()
    after11_course = Course.query.filter(Course.course_name.like('%_hermes_최선우%')).count()
    check(f"결석 처리가 실행되지 않음(Attendance 개수 불변: {before11_att} -> {after11_att})",
          before11_att == after11_att)
    check(f"보강도 생성되지 않음(Course 개수 불변: {before11_course} -> {after11_course})",
          before11_course == after11_course)

print("\n[12] 취소(cancel) - pending_confirmation을 취소하면 아무것도 실행 안 됨")
hermes_agent.parse_hermes_command = fake_parse(
    'mark_absence', student_name='_hermes_박서연', date=date.today().isoformat(), status='absent',
)
with app.app_context():
    student3_session = CourseSession(course_id=course3_id, session_number=1,
                                     session_date=date.today(), status='scheduled')
    db.session.add(student3_session)
    db.session.commit()
    student3_session_id = student3_session.session_id

resp12 = client.post('/admin/hermes/message', json={'text': '_hermes_박서연 학생 오늘 결석'})
data12 = resp12.get_json()
check(f"응답 status=pending_confirmation (실제: {data12.get('status')})", data12.get('status') == 'pending_confirmation')

cancel12 = cancel(data12['thread_id'])
check(f"cancel 응답 status=cancelled (실제: {cancel12.get('status')})", cancel12.get('status') == 'cancelled')
with app.app_context():
    check("취소했으니 Attendance가 생성되지 않음",
          Attendance.query.filter_by(session_id=student3_session_id, student_id=student3_id).first() is None)
    log12 = HermesCommandLog.query.filter_by(thread_id=data12['thread_id']).first()
    check(f"로그 status=cancelled로 기록됨 (실제: {log12.status if log12 else None})",
          log12 is not None and log12.status == 'cancelled')

print("\n[12b] 취소된 thread를 다시 confirm해도 '이미 처리됨'(실행 안 됨)")
confirm12b = confirm(data12['thread_id'])
check(f"이미 처리된 thread confirm은 실패 응답 (실제: {confirm12b.get('reply_text')})",
      '이미 처리' in (confirm12b.get('reply_text') or ''))
with app.app_context():
    check("여전히 Attendance 생성 안 됨",
          Attendance.query.filter_by(session_id=student3_session_id, student_id=student3_id).first() is None)

print("\n[13] GET /admin/hermes/threads - 최근 스레드 목록")
resp13 = client.get('/admin/hermes/threads')
data13 = resp13.get_json()
check(f"응답 200 (실제: {resp13.status_code})", resp13.status_code == 200)
check("threads 키가 리스트", isinstance(data13.get('threads'), list))
check(f"스레드 목록에 항목이 있음 (실제: {len(data13.get('threads', []))}건)", len(data13.get('threads', [])) > 0)
if data13.get('threads'):
    sample = data13['threads'][0]
    check("각 항목에 thread_id/preview/status/status_label/time 키가 있음",
          all(k in sample for k in ('thread_id', 'preview', 'status', 'status_label', 'time')))

print("\n[14] GET /admin/hermes/thread/<id> - 스레드 상세")
resp14 = client.get(f"/admin/hermes/thread/{data10['thread_id']}")
data14 = resp14.get_json()
check(f"응답 200 (실제: {resp14.status_code})", resp14.status_code == 200)
items14 = data14.get('items', [])
check(f"복합 명령 스레드라 항목 2개(액션 2개) (실제: {len(items14)}건)", len(items14) == 2)
check("각 항목이 같은 raw_text를 공유(한 번 입력했으므로)",
      len({it['raw_text'] for it in items14}) == 1)
check("각 항목에 agent_text가 채워져 있음(결과 요약)",
      all(it.get('agent_text') for it in items14))

print("\n[15] 존재하지 않는 thread_id는 404")
resp15 = client.get('/admin/hermes/thread/not-a-real-thread-id')
check(f"존재하지 않는 스레드는 404 (실제: {resp15.status_code})", resp15.status_code == 404)

created_student_ids.append(student10_id)
created_course_ids.append(course10_id)

created_student_ids.append(student5_id)
created_user_ids.append(parent5_id)
created_course_ids.append(course5_id)

print("\n[16] teacher 본인 담당 학생/수업은 정상 처리됨(위임 없이)")
with app.app_context():
    student16 = make_student('_hermes_정하늘', teacher_id)
    course16 = make_course('_hermes_과학정규반', teacher_id)
    db.session.add(CourseEnrollment(course_id=course16.course_id, student_id=student16.student_id, status='active'))
    db.session.commit()
    student16_id, course16_id = student16.student_id, course16.course_id

login_as(teacher_id)
makeup_date16 = date.today() + timedelta(days=15)
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_정하늘', date=makeup_date16.isoformat(), time='17:00',
)
resp16 = client.post('/admin/hermes/message', json={'text': '_hermes_정하늘 학생 보강 잡아줘'})
data16 = resp16.get_json()
check(f"teacher 본인 담당 학생은 pending_confirmation까지 정상 진행 (실제: {data16.get('status')})",
      data16.get('status') == 'pending_confirmation')

confirm16 = confirm(data16['thread_id'])
check(f"confirm 응답 status=success (실제: {confirm16.get('status')})", confirm16.get('status') == 'success')
with app.app_context():
    mc16 = Course.query.filter(Course.course_name.like('%_hermes_정하늘%'), Course.course_id != course16_id).first()
    check("teacher 본인 담당 보강 Course가 실제 생성됨", mc16 is not None)
    if mc16:
        created_course_ids.append(mc16.course_id)

print("\n[17] teacher가 다른 강사에게 위임 시도하면 거부(관리자만 가능)")
hermes_agent.parse_hermes_command = fake_parse(
    'schedule_makeup', student_name='_hermes_정하늘', course_hint='_hermes_과학정규반',
    date=makeup_date16.isoformat(), teacher_name=teacher2_name,
)
resp17 = client.post('/admin/hermes/message', json={'text': f'_hermes_정하늘 학생 {teacher2_name} 강사와 보강'})
data17 = resp17.get_json()
check(f"응답 status=needs_clarification (실제: {data17.get('status')})",
      data17.get('status') == 'needs_clarification')
check("관리자만 위임 가능하다는 안내",
      '관리자만' in (data17.get('reply_text') or ''))

login_as(admin_id)

print("\n[18] manager/staff는 master_admin과 동일하게 전체 범위(위임도 가능)")
with app.app_context():
    manager = make_user('_hermes_manager', 'manager', 2)
    staff = make_user('_hermes_staff', 'staff', 3)
    db.session.commit()
    manager_id, staff_id = manager.user_id, staff.user_id

for role_label, role_user_id in (('manager', manager_id), ('staff', staff_id)):
    login_as(role_user_id)
    hermes_agent.parse_hermes_command = fake_parse(
        'schedule_makeup', student_name='_hermes_정하늘', course_hint='_hermes_과학정규반',
        date=makeup_date16.isoformat(), teacher_name=teacher2_name,
    )
    resp18 = client.post('/admin/hermes/message', json={'text': f'_hermes_정하늘 학생 {teacher2_name} 강사와 보강'})
    data18 = resp18.get_json()
    check(f"{role_label}은 teacher 담당 학생도 바로 pending_confirmation (실제: {data18.get('status')})",
          data18.get('status') == 'pending_confirmation')
    check(f"{role_label}은 위임(teacher_name)도 미리보기에 반영됨",
          teacher2_name in (data18.get('reply_text') or ''))
    cancel18 = cancel(data18['thread_id'])
    check(f"{role_label} 테스트는 취소로 정리(실행 안 함, 실제: {cancel18.get('status')})",
          cancel18.get('status') == 'cancelled')

login_as(admin_id)

created_student_ids.append(student16_id)
created_course_ids.append(course16_id)
created_user_ids.extend([manager_id, staff_id])

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    from app.models.absence_notice import AbsenceNotice
    HermesCommandLog.query.filter(HermesCommandLog.admin_user_id.in_(created_user_ids)).delete(synchronize_session=False)
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
