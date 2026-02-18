# -*- coding: utf-8 -*-
"""줌 온라인 강의실 라우트"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import datetime

from app.zoom import zoom_bp
from app.models import db, User, Student, Course, CourseSession, CourseEnrollment
from app.utils.zoom_utils import (
    decrypt_zoom_link,
    can_access_zoom,
    get_current_or_upcoming_session,
    log_zoom_access
)


@zoom_bp.route('/join/<string:token>')
@login_required
def join(token):
    """
    줌 토큰으로 강의실 입장
    학생만 접근 가능, 수업 10분 전부터 입장 가능
    """
    # 학생만 접근 가능
    if current_user.role != 'student':
        flash('학생만 온라인 강의실에 접속할 수 있습니다.', 'danger')
        return redirect(url_for('student.index'))

    # 학생 정보 조회
    student = Student.query.filter_by(user_id=current_user.user_id).first()
    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('student.index'))

    # 토큰으로 강사 찾기
    teacher = User.query.filter_by(zoom_token=token, role='teacher', is_active=True).first()
    if not teacher:
        flash('유효하지 않은 강의실 링크입니다.', 'danger')
        return redirect(url_for('student_portal.courses'))

    # 줌 링크가 없는 경우
    if not teacher.zoom_link:
        flash('강사님의 온라인 강의실이 아직 준비되지 않았습니다.', 'warning')
        return redirect(url_for('student_portal.courses'))

    # 해당 강사의 수업에 등록되어 있는지 확인
    enrollment = db.session.query(CourseEnrollment).join(Course).filter(
        Course.teacher_id == teacher.user_id,
        CourseEnrollment.student_id == student.student_id,
        CourseEnrollment.status == 'active'
    ).first()

    if not enrollment:
        flash('해당 강사님의 수업에 등록되어 있지 않습니다.', 'danger')
        return redirect(url_for('student_portal.courses'))

    # 현재 또는 다가오는 수업 세션 찾기
    session = get_current_or_upcoming_session(student.student_id)

    # 수업이 없어도 강사의 줌 링크로 접속은 허용하되, 시간 체크만 수행
    if session:
        # 수업 시작 시간 확인 (10분 전부터 접속 가능)
        can_access, message = can_access_zoom(session.session_date)

        if not can_access:
            # 10분 전이 아니면 대기 페이지 표시
            return render_template('zoom/waiting.html',
                                 teacher=teacher,
                                 session=session,
                                 message=message,
                                 token=token)

    # 접속 로그 기록
    log_zoom_access(
        student_id=student.student_id,
        teacher_id=teacher.user_id,
        course_id=session.course_id if session else None,
        session_id=session.session_id if session else None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )

    # 줌 링크 복호화 및 리다이렉트
    zoom_url = decrypt_zoom_link(teacher.zoom_link)
    if not zoom_url:
        flash('강의실 링크를 불러올 수 없습니다. 관리자에게 문의하세요.', 'danger')
        return redirect(url_for('student_portal.courses'))

    # 실제 줌 링크로 리다이렉트
    return redirect(zoom_url)


@zoom_bp.route('/preview/<string:token>')
@login_required
def preview(token):
    """
    줌 강의실 정보 미리보기 (학생용)
    실제 링크는 표시하지 않고, 입장 가능 여부만 확인
    """
    # 학생만 접근 가능
    if current_user.role != 'student':
        flash('학생만 접근할 수 있습니다.', 'danger')
        return redirect(url_for('student.index'))

    # 학생 정보 조회
    student = Student.query.filter_by(user_id=current_user.user_id).first()
    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('student.index'))

    # 토큰으로 강사 찾기
    teacher = User.query.filter_by(zoom_token=token, role='teacher', is_active=True).first()
    if not teacher:
        abort(404)

    # 현재 또는 다가오는 수업 세션 찾기
    session = get_current_or_upcoming_session(student.student_id)

    can_access = False
    message = "현재 예정된 수업이 없습니다."

    if session:
        can_access, message = can_access_zoom(session.session_date)

    return render_template('zoom/preview.html',
                         teacher=teacher,
                         session=session,
                         can_access=can_access,
                         message=message,
                         token=token)
