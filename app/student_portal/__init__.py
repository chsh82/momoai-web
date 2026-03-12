# -*- coding: utf-8 -*-
"""학생 포털 Blueprint"""
from flask import Blueprint, redirect, url_for, flash, request
from flask_login import current_user

student_bp = Blueprint('student', __name__)


@student_bp.before_request
def check_student_status():
    """휴퇴원 학생은 대시보드 외 메뉴 접근 제한"""
    if not current_user.is_authenticated or current_user.role != 'student':
        return

    # 대시보드(index)는 허용 — 안내 메시지 표시
    allowed_endpoints = {'student.index', 'static'}
    if request.endpoint in allowed_endpoints:
        return

    from app.models import Student
    student = Student.query.filter_by(email=current_user.email).first()
    if student and student.status in ('leave', 'withdrawn'):
        status_label = '휴원' if student.status == 'leave' else '퇴원'
        flash(f'현재 {status_label} 상태로 기능 이용이 제한됩니다. 문의는 학원으로 연락해주세요.', 'warning')
        return redirect(url_for('student.index'))


from app.student_portal import routes
