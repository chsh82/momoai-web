# -*- coding: utf-8 -*-
"""
보강/custom(1회성) 수업 수강생 중 출결 레코드가 누락된 건을 백필.

배경: create_attendance_records_for_enrollment()에 "미래 세션은 레코드
생성 안 함" 로직이 추가되면서(커밋 1d632b6), 보강수업처럼 미래 날짜에
잡히는 단일 세션 수업도 함께 걸려 등록 시점에 출결 레코드가 생성되지
않는 문제가 있었음(이후 course_utils.py에서 skip_date_filter 대상은
예외 처리하도록 수정됨). 그 버그가 있던 기간에 등록된 보강/custom
수강생들의 누락 레코드를 채운다.

기본은 dry-run(출력만). 실제로 DB에 반영하려면 --apply 옵션을 준다.
    python backfill_makeup_attendance.py          # dry-run
    python backfill_makeup_attendance.py --apply  # 실제 반영
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.course import CourseEnrollment
from app.models.attendance import Attendance
from app.models.student import Student

# 주의: 배포된 app.utils.course_utils.create_attendance_records_for_enrollment()가
# 아직 이번 수정(보강/custom 예외 처리) 전 버전일 수 있으므로, 그 함수에 의존하지
# 않고 이 스크립트 자체에서 직접 누락 여부를 판단하고 생성한다.
APPLY = '--apply' in sys.argv

app = create_app()
with app.app_context():
    active_enrollments = CourseEnrollment.query.filter_by(status='active').all()

    targets = [
        e for e in active_enrollments
        if e.course and (
            (e.course.course_type or '').startswith('보강') or
            e.course.schedule_type == 'custom'
        )
    ]

    print(f"대상 수강 건수: {len(targets)}")
    print("=" * 60)

    total_created = 0
    for enrollment in targets:
        course = enrollment.course
        student = Student.query.get(enrollment.student_id)

        for session in course.sessions:
            existing = Attendance.query.filter_by(
                session_id=session.session_id,
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id
            ).first()
            if existing:
                continue

            attendance = Attendance(
                session_id=session.session_id,
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id,
                status='present',
                checkin_method='manual'
            )
            db.session.add(attendance)

            print(f"  + [{course.course_code}] {course.course_name} | "
                  f"{student.name if student else '?'} | session_date={session.session_date} "
                  f"status=present")
            total_created += 1

    print("=" * 60)
    print(f"생성 대상 레코드: {total_created}건")

    if APPLY and total_created:
        db.session.commit()
        print("커밋 완료.")
    elif total_created:
        db.session.rollback()
        print("dry-run — 실제로 반영하려면 --apply 옵션을 주고 다시 실행하세요.")
    else:
        print("누락된 레코드가 없습니다.")
