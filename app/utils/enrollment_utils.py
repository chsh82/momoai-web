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


def get_essay_student_ids(student):
    """학생의 모든 student_id 반환 (서버 이전 등으로 생긴 중복 레코드 방어).

    user_id가 연결된 경우 같은 user_id를 가진 모든 student_id를 반환하여
    essay 조회 시 중복 레코드에 묶인 글도 함께 보이도록 한다.
    """
    from app.models import db
    from app.models.student import Student
    if not student.user_id:
        return [student.student_id]
    ids = [s.student_id for s in Student.query.filter_by(user_id=student.user_id).all()]
    return ids if ids else [student.student_id]
