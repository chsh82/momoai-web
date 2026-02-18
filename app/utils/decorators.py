# -*- coding: utf-8 -*-
"""권한 확인 데코레이터"""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


def requires_role(*roles):
    """
    특정 역할이 필요한 라우트를 보호하는 데코레이터

    사용 예:
        @requires_role('admin', 'manager')
        def admin_only_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'error')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                flash('접근 권한이 없습니다.', 'error')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_permission_level(level):
    """
    특정 권한 레벨이 필요한 라우트를 보호하는 데코레이터

    Args:
        level: 필요한 권한 레벨 (1=master, 2=manager, 3=staff, 4=teacher, 5=parent, 6=student)

    사용 예:
        @requires_permission_level(2)  # 매니저 이상만 접근 가능
        def manager_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'error')
                return redirect(url_for('auth.login'))

            if not current_user.has_permission_level(level):
                flash('접근 권한이 없습니다.', 'error')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_tier(*tiers):
    """
    특정 티어의 학생만 접근 가능한 라우트를 보호하는 데코레이터

    Args:
        tiers: 허용할 티어 목록 (예: 'A', 'B', 'VIP')

    사용 예:
        @requires_tier('A', 'VIP')
        def premium_content():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'error')
                return redirect(url_for('auth.login'))

            # 학생이 아닌 경우 관리자/강사는 통과
            if current_user.role in ['admin', 'teacher']:
                return f(*args, **kwargs)

            # 학생인 경우 티어 확인
            if current_user.role == 'student':
                from app.models import Student
                student = Student.query.filter_by(user_id=current_user.user_id).first()

                if not student or not student.has_tier_access(list(tiers)):
                    flash('이 콘텐츠에 접근할 권한이 없습니다.', 'error')
                    abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_or_owner_required(get_owner_id):
    """
    관리자 또는 리소스 소유자만 접근 가능하도록 하는 데코레이터

    Args:
        get_owner_id: 리소스 소유자 ID를 반환하는 함수

    사용 예:
        @admin_or_owner_required(lambda: post.user_id)
        def edit_post(post_id):
            post = Post.query.get_or_404(post_id)
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'error')
                return redirect(url_for('auth.login'))

            # 관리자는 무조건 통과
            if current_user.is_admin or current_user.is_master_admin or current_user.is_manager:
                return f(*args, **kwargs)

            # 소유자 확인
            owner_id = get_owner_id()
            if current_user.user_id != owner_id:
                flash('접근 권한이 없습니다.', 'error')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def master_admin_only(f):
    """
    마스터 관리자만 접근 가능한 라우트를 보호하는 데코레이터

    사용 예:
        @master_admin_only
        def delete_all_data():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('로그인이 필요합니다.', 'error')
            return redirect(url_for('auth.login'))

        if not current_user.is_master_admin:
            flash('마스터 관리자만 접근할 수 있습니다.', 'error')
            abort(403)

        return f(*args, **kwargs)
    return decorated_function
