#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""마일리지 적립 시작일(2026-08-31, KST) 게이트 확인 스크립트

app/services/mileage_rules.py의 MILEAGE_START_DATE 하나만 참조 지점을
바꾸면 게이트를 통째로 걷어낼 수 있는지 확인하는 게 목적이다(2026-08-30
9/1 -> 8/31로 앞당김).
확인 항목:
  1) 8월 30일(KST) 활동 -> award_points()가 예외 없이 None 반환, 행 생성 안 됨
  2) 8월 31일(KST) 활동 -> 정상 적립
  3) UTC 기준 8/30이지만 KST로 환산하면 8/31인 경계 시각 -> 정상 적립
     (게이트가 KST 날짜로 판정한다는 것을 확인 - UTC로만 봤으면 걸렸을 케이스)
  4) 8월 24일 시작 주(시작일 이전 주) 배치 -> 건너뜀(빈 리스트, 로그만)
  5) 8월 31일 시작 주(시작일이 속한 주, 온전히 시작일 이후) 배치 -> 정상 집계

테스트로 만든 데이터는 스크립트 마지막에 전부 삭제한다.
"""
import sys
import io
import uuid
from datetime import datetime, date, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.mileage import PointEvent
from app.services import mileage_service as msvc
from app.services import mileage_batch_service as batch
from app.services.mileage_rules import MILEAGE_START_DATE

app = create_app('development')
failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


created_user_ids = []
created_student_ids = []
created_course_ids = []
created_session_ids = []


def make_student(name, teacher_id):
    student = Student(teacher_id=teacher_id, name=name, grade='초3',
                       birth_date=date(2016, 1, 1), status='active')
    db.session.add(student)
    db.session.flush()
    created_student_ids.append(student.student_id)
    return student.student_id


with app.app_context():
    print("=" * 70)
    print("마일리지 적립 시작일 게이트 확인 스크립트")
    print(f"MILEAGE_START_DATE = {MILEAGE_START_DATE}")
    print("=" * 70)

    teacher = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                   name='게이트확인강사', role='teacher', role_level=4, is_active=True)
    teacher.set_password('x')
    db.session.add(teacher)
    db.session.flush()
    created_user_ids.append(teacher.user_id)

    student_a = make_student('게이트확인학생A', teacher.user_id)
    student_b = make_student('게이트확인학생B', teacher.user_id)
    db.session.commit()

    print("\n[1] award_points() 게이트 - 8월 30일(KST) 활동")
    ev = msvc.award_points(
        student_a, 'RW01', 'essay', f'gate-0830-{uuid.uuid4().hex[:8]}',
        occurred_at=datetime(2026, 8, 30, 0, 0, 0),  # UTC 00:00 -> KST 09:00, 같은 날짜
    )
    check("반환값이 None (예외 없이 조용히 무시)", ev is None)
    check("실제로 point_events에 행이 생기지 않음",
          PointEvent.query.filter_by(student_id=student_a, activity_code='RW01').count() == 0)

    # "기존 라우트의 try/except를 거치더라도 조용히 넘어가야 한다" 확인 -
    # essays/momoai_service.py 등이 쓰는 것과 동일한 패턴으로 감싸본다.
    caught = False
    try:
        msvc.award_points(student_a, 'RW01', 'essay', f'gate-0830b-{uuid.uuid4().hex[:8]}',
                          occurred_at=datetime(2026, 8, 30, 12, 0, 0))
    except Exception:
        caught = True
    check("try/except로 감싸도 예외가 발생하지 않음", caught is False)

    print("\n[2] award_points() 게이트 - 8월 31일(KST) 활동")
    ev2 = msvc.award_points(
        student_a, 'RW01', 'essay', f'gate-0831-{uuid.uuid4().hex[:8]}',
        occurred_at=datetime(2026, 8, 31, 0, 0, 0),  # UTC 00:00 -> KST 09:00 08/31
    )
    check("정상 적립됨(PointEvent 반환)", ev2 is not None)
    check("점수가 그대로 지급됨(500점)", ev2 is not None and ev2.points == 500)

    print("\n[3] KST 환산 경계 - UTC로는 8/30이지만 KST로는 8/31인 시각")
    ev3 = msvc.award_points(
        student_a, 'QZ01', 'quiz_session', f'gate-boundary-{uuid.uuid4().hex[:8]}',
        occurred_at=datetime(2026, 8, 30, 23, 0, 0),  # UTC 23:00 -> KST 다음날 08:00
    )
    check("UTC 날짜가 아니라 KST 날짜로 판정해 정상 적립됨", ev3 is not None)

    db.session.commit()

    print("\n[4] 주간 출석(AT01) 배치 게이트 - 8월 24일 시작 주(시작일 이전 주)")
    # 정규 수업 세션을 8/24~8/30 주간(시작일 이전)에 하나 만들고 전부 출석
    # 처리 - 게이트가 없다면 정상 지급될 상황을 만들어서, 게이트가 실제로
    # 막는지 확인한다.
    course = Course(course_name='게이트확인반', course_code=f'GATE-{uuid.uuid4().hex[:8]}',
                    teacher_id=teacher.user_id, weekday=0,
                    start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                    course_type='정규반')
    db.session.add(course)
    db.session.flush()
    created_course_ids.append(course.course_id)

    session_0824 = CourseSession(course_id=course.course_id, session_number=1,
                                 session_date=date(2026, 8, 24), status='scheduled')
    db.session.add(session_0824)
    db.session.flush()
    created_session_ids.append(session_0824.session_id)

    enrollment = CourseEnrollment(student_id=student_b, course_id=course.course_id, status='active')
    db.session.add(enrollment)
    db.session.flush()

    attendance = Attendance(session_id=session_0824.session_id, student_id=student_b,
                            enrollment_id=enrollment.enrollment_id, status='present')
    db.session.add(attendance)
    db.session.commit()

    results_before_start = batch.run_weekly_attendance_batch(monday=date(2026, 8, 24), dry_run=True)
    check("8월 24일 시작 주는 아무 결과 없이 건너뜀(빈 리스트)", results_before_start == [])
    check("실제로 지급되지 않음(dry_run=False로도 재확인)",
          batch.run_weekly_attendance_batch(monday=date(2026, 8, 24), dry_run=False) == [])
    check("point_events에 AT01 행이 생기지 않음",
          PointEvent.query.filter_by(student_id=student_b, activity_code='AT01').count() == 0)

    print("\n[5] 주간 출석(AT01) 배치 - 8월 31일 시작 주(시작일이 속한 주)는 정상 집계")
    session_0831 = CourseSession(course_id=course.course_id, session_number=2,
                                 session_date=date(2026, 8, 31), status='scheduled')
    db.session.add(session_0831)
    db.session.flush()
    created_session_ids.append(session_0831.session_id)
    attendance2 = Attendance(session_id=session_0831.session_id, student_id=student_b,
                             enrollment_id=enrollment.enrollment_id, status='present')
    db.session.add(attendance2)
    db.session.commit()

    results_after_start = batch.run_weekly_attendance_batch(monday=date(2026, 8, 31), dry_run=True)
    entry_b = next((r for r in results_after_start if r['student_id'] == student_b), None)
    check("8월 31일 시작 주는 정상 집계됨(대상 학생 존재)", entry_b is not None)
    check("전부 출석 -> 지급 대상 판정", entry_b is not None and entry_b['action'] == 'would_award(100점)')

    # award_points()가 occurred_at 없이 호출되면 datetime.utcnow()(실제 현재
    # 시각)로 게이트를 검사한다. 이 스크립트를 실제로 돌리는 오늘 날짜(8/30)는
    # 아직 시작일(8/31) 이전이라 배치의 주간 게이트를 통과해도 award_points()
    # 자체 게이트에 다시 걸린다 - 이는 배치가 잘못된 게 아니라 "실제로 이
    # 배치가 8/31 이후에 돌아간다"는 전제를 오늘 이 스크립트 안에서 재현하려면
    # 현재 시각을 흉내내야 하기 때문이다. 배치의 주간 게이트(월요일 기준)는
    # 이미 위에서 dry_run으로 확인했으니, 여기서는 "그 날짜가 되면 실제로도
    # 지급된다"는 것만 datetime.utcnow()를 일시적으로 흉내내 확인한다.
    from unittest.mock import patch

    with patch('app.services.mileage_service.datetime') as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 9, 7)
        real_results = batch.run_weekly_attendance_batch(monday=date(2026, 8, 31), dry_run=False)
    db.session.commit()
    at01_event = PointEvent.query.filter_by(student_id=student_b, activity_code='AT01').first()
    check("시작일 이후 실행 시(시각 재현) AT01이 실제로 지급됨", at01_event is not None)

    print("\n정리: 테스트 데이터 삭제")
    PointEvent.query.filter(PointEvent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    Attendance.query.filter(Attendance.session_id.in_(created_session_ids)).delete(synchronize_session=False)
    CourseEnrollment.query.filter_by(course_id=course.course_id).delete(synchronize_session=False)
    CourseSession.query.filter(CourseSession.session_id.in_(created_session_ids)).delete(synchronize_session=False)
    Course.query.filter(Course.course_id.in_(created_course_ids)).delete(synchronize_session=False)
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
