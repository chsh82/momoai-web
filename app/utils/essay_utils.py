# -*- coding: utf-8 -*-
"""글쓰기-수업 세션 자동 배정 유틸리티"""
from datetime import date as date_type


def find_session_for_essay(course_id, essay_date):
    """
    글쓰기 제출 날짜 기준으로 해당 수업의 세션을 찾는다.
    규칙: 직전 세션 날짜 < essay_date <= 현재 세션 날짜 → 현재 세션 소속

    Args:
        course_id: Course ID
        essay_date: 글쓰기 제출 date 객체

    Returns:
        CourseSession 또는 None
    """
    from app.models import CourseSession

    sessions = CourseSession.query.filter_by(
        course_id=course_id
    ).order_by(CourseSession.session_date.asc()).all()

    if not sessions:
        return None

    for i, session in enumerate(sessions):
        prev_date = sessions[i - 1].session_date if i > 0 else date_type.min
        curr_date = session.session_date

        if prev_date < essay_date <= curr_date:
            return session

    # 마지막 세션 이후 제출 → None (다음 세션 생성 전)
    return None


def auto_assign_essay_session(essay):
    """
    Essay 제출 시 course_id와 session_id를 자동 설정한다.

    - 학생이 해당 강사의 수업을 1개만 수강 중이면 자동 배정
    - 여러 수업 수강 중이면 배정 불가 (강사가 수동 지정)

    Args:
        essay: Essay 객체 (student_id, user_id, created_at이 설정된 상태)
    """
    from app.models.course import CourseEnrollment, Course
    from datetime import datetime

    student_id = essay.student_id
    teacher_id = essay.user_id
    essay_date = essay.created_at.date() if essay.created_at else datetime.utcnow().date()

    # 이 학생이 이 강사의 활성 수업에 수강 중인 enrollment 조회
    enrollments = CourseEnrollment.query.join(Course).filter(
        CourseEnrollment.student_id == student_id,
        CourseEnrollment.status == 'active',
        Course.teacher_id == teacher_id,
        Course.course_type != '보강수업'
    ).all()

    if len(enrollments) == 1:
        course = enrollments[0].course
        essay.course_id = course.course_id
        essay.session_assigned_auto = True

        session = find_session_for_essay(course.course_id, essay_date)
        if session:
            essay.session_id = session.session_id

    else:
        # 0개(수업 없음) 또는 2개 이상(수동 지정 필요)
        essay.course_id = None
        essay.session_id = None
        essay.session_assigned_auto = False
