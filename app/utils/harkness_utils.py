# -*- coding: utf-8 -*-
"""하크니스 게시판 유틸리티"""
from app.models import Course, CourseEnrollment, Student


def can_access_harkness_board(user, board):
    """하크니스 게시판 접근 권한 확인

    Args:
        user: 현재 사용자
        board: HarknessBoard 객체

    Returns:
        bool: 접근 가능 여부
    """
    # 관리자는 모든 게시판 접근 가능
    if user.is_admin:
        return True

    # 강사 권한 체크
    if user.role == 'teacher':
        # 하크니스 전체 게시판: 모든 강사 접근 가능
        if board.board_type == 'harkness_all':
            return True

        # 특정 수업 게시판: 본인 수업이거나 하크니스 수업을 담당하는 강사
        if board.course_id:
            if board.course.teacher_id == user.user_id:
                return True

            # 하크니스 수업을 하나라도 담당하고 있으면 접근 가능
            harkness_courses = Course.query.filter_by(
                teacher_id=user.user_id,
                course_type='harkness',
                status='active'
            ).count()
            return harkness_courses > 0

    # 학생 권한 체크
    if user.role == 'student':
        student = Student.query.filter_by(user_id=user.user_id).first()
        if not student:
            return False

        # 하크니스 전체 게시판: 하크니스 수업을 하나라도 듣고 있으면 접근 가능
        if board.board_type == 'harkness_all':
            harkness_enrollments = CourseEnrollment.query.join(Course).filter(
                CourseEnrollment.student_id == student.student_id,
                CourseEnrollment.status == 'active',
                Course.course_type == 'harkness'
            ).count()
            return harkness_enrollments > 0

        # 특정 수업 게시판: 해당 수업을 듣고 있어야 함
        if board.course_id:
            enrollment = CourseEnrollment.query.filter_by(
                student_id=student.student_id,
                course_id=board.course_id,
                status='active'
            ).first()
            return enrollment is not None

    return False


def get_accessible_harkness_boards(user):
    """사용자가 접근 가능한 하크니스 게시판 목록 반환

    Args:
        user: 현재 사용자

    Returns:
        list: HarknessBoard 객체 리스트
    """
    from app.models.harkness_board import HarknessBoard

    # 관리자는 모든 게시판
    if user.is_admin:
        return HarknessBoard.query.filter_by(is_active=True).order_by(
            HarknessBoard.board_type.asc(),
            HarknessBoard.created_at.desc()
        ).all()

    # 강사는 자신의 게시판 + 하크니스 전체
    if user.role == 'teacher':
        boards = HarknessBoard.query.filter(
            HarknessBoard.is_active == True,
            db.or_(
                HarknessBoard.board_type == 'harkness_all',
                HarknessBoard.created_by == user.user_id
            )
        ).order_by(
            HarknessBoard.board_type.asc(),
            HarknessBoard.created_at.desc()
        ).all()
        return boards

    # 학생은 자신이 수강하는 하크니스 수업 게시판만
    if user.role == 'student':
        student = Student.query.filter_by(user_id=user.user_id).first()
        if not student:
            return []

        # 학생이 수강 중인 하크니스 수업 ID 목록
        harkness_enrollments = CourseEnrollment.query.join(Course).filter(
            CourseEnrollment.student_id == student.student_id,
            CourseEnrollment.status == 'active',
            Course.course_type == 'harkness'
        ).all()

        course_ids = [e.course_id for e in harkness_enrollments]

        # 하크니스 전체 게시판 + 수강 중인 수업 게시판
        if course_ids:
            boards = HarknessBoard.query.filter(
                HarknessBoard.is_active == True,
                db.or_(
                    HarknessBoard.board_type == 'harkness_all',
                    HarknessBoard.course_id.in_(course_ids)
                )
            ).order_by(
                HarknessBoard.board_type.asc(),
                HarknessBoard.created_at.desc()
            ).all()
            return boards
        else:
            # 하크니스 수업을 듣지 않으면 빈 리스트
            return []

    return []


def can_create_harkness_board(user):
    """하크니스 게시판 생성 권한 확인

    Args:
        user: 현재 사용자

    Returns:
        bool: 생성 가능 여부
    """
    # 관리자 또는 강사만 생성 가능
    return user.is_admin or user.role == 'teacher'


def can_write_notice(user, board):
    """공지사항 작성 권한 확인

    Args:
        user: 현재 사용자
        board: HarknessBoard 객체

    Returns:
        bool: 공지사항 작성 가능 여부
    """
    # 관리자는 모든 게시판에 공지사항 작성 가능
    if user.is_admin:
        return True

    # 강사는 자신의 게시판에만 공지사항 작성 가능
    if user.role == 'teacher':
        if board.board_type == 'course' and board.course:
            return board.course.teacher_id == user.user_id
        # 하크니스 전체 게시판은 관리자만
        return False

    return False


# DB import는 함수 내부에서 필요시 import
from app.models import db
