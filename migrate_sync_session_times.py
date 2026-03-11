"""
Course.start_time / end_time 과 CourseSession.start_time / end_time 불일치 동기화
- 오늘 이후 scheduled 세션 중 Course 시간과 다른 것을 일괄 수정
"""
import os, sys
os.environ.setdefault('DATABASE_URL', 'sqlite:///momoai.db')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app import create_app
from app.models import db, Course, CourseSession

app = create_app()
with app.app_context():
    today = date.today()
    courses = Course.query.filter(
        Course.start_time != None
    ).all()

    updated = 0
    for course in courses:
        sessions = CourseSession.query.filter(
            CourseSession.course_id == course.course_id,
            CourseSession.status == 'scheduled',
            CourseSession.session_date >= today
        ).all()
        for s in sessions:
            if s.start_time != course.start_time or s.end_time != course.end_time:
                print(f"  [{course.course_name}] {s.session_date}: "
                      f"{s.start_time}→{course.start_time}, {s.end_time}→{course.end_time}")
                s.start_time = course.start_time
                s.end_time = course.end_time
                updated += 1

    db.session.commit()
    print(f"\n총 {updated}개 세션 시간 동기화 완료")
