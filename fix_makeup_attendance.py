"""
과거 날짜로 개설된 보강수업의 누락된 출결 레코드를 수동 생성
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.course import Course, CourseSession, CourseEnrollment
from app.models.attendance import Attendance
from datetime import date

app = create_app()

with app.app_context():
    today = date.today()

    # 보강수업 중 출결 레코드가 누락된 케이스 찾기
    # - 과거 날짜 세션이 있고
    # - 수강생은 있지만
    # - 출결 레코드가 없는 경우

    makeup_courses = Course.query.filter_by(course_type='보강수업').all()
    print(f"보강수업 총 {len(makeup_courses)}개 확인")

    fixed = 0
    for course in makeup_courses:
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.course_id, status='active'
        ).all()
        sessions = CourseSession.query.filter_by(course_id=course.course_id).all()

        for enrollment in enrollments:
            for session in sessions:
                existing = Attendance.query.filter_by(
                    session_id=session.session_id,
                    student_id=enrollment.student_id,
                    enrollment_id=enrollment.enrollment_id
                ).first()

                if not existing:
                    att = Attendance(
                        session_id=session.session_id,
                        student_id=enrollment.student_id,
                        enrollment_id=enrollment.enrollment_id,
                        status='present',
                        checkin_method='manual'
                    )
                    db.session.add(att)
                    print(f"  [생성] {course.course_name} | 세션 {session.session_date} | student_id={enrollment.student_id}")
                    fixed += 1

    if fixed > 0:
        db.session.commit()
        print(f"\n완료: 출결 레코드 {fixed}개 생성")
    else:
        print("\n누락된 출결 레코드 없음")
