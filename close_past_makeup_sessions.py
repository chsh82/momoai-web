# -*- coding: utf-8 -*-
"""
과거 완료된 보강수업 세션 상태를 cancelled로 일괄 변경
실행: python close_past_makeup_sessions.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app import create_app
from app.models import db
from app.models.course import CourseSession, Course

app = create_app()

with app.app_context():
    today = date.today()

    # 보강수업 course_id 목록
    makeup_course_ids = [
        c.course_id for c in Course.query.filter_by(course_type='보강수업').all()
    ]

    if not makeup_course_ids:
        print("보강수업 수업이 없습니다.")
    else:
        # 오늘 이전의 보강수업 세션 (cancelled 아닌 것만)
        sessions = CourseSession.query.filter(
            CourseSession.course_id.in_(makeup_course_ids),
            CourseSession.session_date < today,
            CourseSession.status != 'cancelled'
        ).all()

        print(f"대상 세션 수: {len(sessions)}개")
        for s in sessions:
            print(f"  [{s.session_date}] {s.course.course_name} #{s.session_number} ({s.status}) → cancelled")
            s.status = 'cancelled'

        db.session.commit()
        print(f"\n완료: {len(sessions)}개 세션 상태를 cancelled로 변경했습니다.")
