# -*- coding: utf-8 -*-
"""수강 관련 유틸리티"""


def get_active_student_ids_for_teacher(teacher_id):
    """강사의 현재 수강 중(active) 학생 ID 목록 반환"""
    from app.models import db, CourseEnrollment
    from app.models.course import Course
    rows = db.session.query(CourseEnrollment.student_id).join(
        Course, CourseEnrollment.course_id == Course.course_id
    ).filter(
        Course.teacher_id == teacher_id,
        CourseEnrollment.status == 'active'
    ).distinct().all()
    return [r[0] for r in rows]


def get_active_student_ids_subquery(teacher_id):
    """강사의 현재 수강 중(active) 학생 ID 서브쿼리 반환 (SQLAlchemy subquery용)"""
    from app.models import db, CourseEnrollment
    from app.models.course import Course
    return db.session.query(CourseEnrollment.student_id).join(
        Course, CourseEnrollment.course_id == Course.course_id
    ).filter(
        Course.teacher_id == teacher_id,
        CourseEnrollment.status == 'active'
    ).subquery()
