# -*- coding: utf-8 -*-
"""학생 포털 Blueprint"""
from flask import Blueprint, redirect, url_for, flash, request
from flask_login import current_user

student_bp = Blueprint('student', __name__)


@student_bp.before_request
def check_student_status():
    """퇴원 학생은 퇴원 처리 후 7일 경과 시 대시보드 외 접근 제한 (휴원은 제한 없음)"""
    if not current_user.is_authenticated or current_user.role != 'student':
        return

    allowed_endpoints = {'student.index', 'static'}
    if request.endpoint in allowed_endpoints:
        return

    from app.models import Student
    from datetime import datetime, timedelta

    student = Student.query.filter_by(email=current_user.email).first()
    if not student or student.status != 'withdrawn':
        return

    # 퇴원 후 7일이 지난 경우에만 제한
    if student.status_changed_at:
        restriction_start = student.status_changed_at + timedelta(days=7)
        if datetime.utcnow() < restriction_start:
            remaining = (restriction_start - datetime.utcnow()).days + 1
            flash(f'퇴원 처리되었습니다. {remaining}일 후 포털 이용이 제한됩니다. 문의는 학원으로 연락해주세요.', 'warning')
            return
    # status_changed_at이 없거나 7일 경과 시 즉시 제한
    flash('퇴원 처리 후 이용 제한 기간이 지났습니다. 문의는 학원으로 연락해주세요.', 'warning')
    return redirect(url_for('student.index'))


from app.student_portal import routes
