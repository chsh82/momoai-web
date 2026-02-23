# -*- coding: utf-8 -*-
"""인증 라우트 (보안 강화 버전)"""
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app.auth import auth_bp
from app.auth.forms import LoginForm, SignupForm, ChangePasswordForm
from app.models import db, User
from app.extensions import limiter


def _log_login_attempt(email, success, failure_reason=None):
    """로그인 시도 DB 로깅 (실패 포함)"""
    try:
        from app.models.login_log import LoginAttemptLog
        log = LoginAttemptLog(
            email=email,
            ip_address=request.remote_addr or 'unknown',
            user_agent=request.headers.get('User-Agent', '')[:500],
            success=success,
            failure_reason=failure_reason
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    """로그인"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # 사용자 없음 (이메일 존재 여부 노출 방지를 위해 동일 메시지)
        if user is None:
            _log_login_attempt(form.email.data, False, 'user_not_found')
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('auth/login.html', form=form)

        # 잠금 해제 시간이 지났으면 자동 초기화
        if user.locked_until and user.locked_until <= datetime.utcnow():
            user.reset_failed_attempts()
            db.session.commit()

        # 계정 잠금 확인
        if user.is_locked:
            remaining = user.lock_remaining_minutes
            _log_login_attempt(form.email.data, False, 'account_locked')
            flash(f'로그인 시도 횟수 초과로 계정이 잠겼습니다. {remaining}분 후 다시 시도해주세요.', 'error')
            return render_template('auth/login.html', form=form)

        # 비밀번호 확인
        if not user.check_password(form.password.data):
            user.increment_failed_attempts()
            db.session.commit()
            _log_login_attempt(form.email.data, False, 'wrong_password')

            if user.is_locked:
                flash('비밀번호 5회 오류로 계정이 15분간 잠겼습니다.', 'error')
            else:
                remaining_attempts = max(0, 5 - (user.failed_login_attempts or 0))
                flash(f'이메일 또는 비밀번호가 올바르지 않습니다. (남은 시도: {remaining_attempts}회)', 'error')
            return render_template('auth/login.html', form=form)

        # 계정 비활성화 확인 (승인 대기 포함)
        if not user.is_active:
            # 로그인은 허용하되 승인 대기 페이지로 리다이렉트
            user.reset_failed_attempts()
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            _log_login_attempt(form.email.data, True, 'pending_approval')
            return redirect(url_for('auth.pending_approval'))

        # 이메일 인증 확인 (메일 서버가 설정된 경우만)
        if current_app.config.get('MAIL_SERVER') and not user.email_verified:
            _log_login_attempt(form.email.data, False, 'email_not_verified')
            flash('이메일 인증이 필요합니다. 받으신 인증 메일을 확인해주세요.', 'warning')
            return render_template('auth/login.html', form=form,
                                   show_resend=True, resend_email=user.email)

        # 로그인 성공
        user.reset_failed_attempts()
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()

        _log_login_attempt(form.email.data, True)

        # 첫 로그인 시 비밀번호 변경 필수
        if user.must_change_password:
            flash('초기 비밀번호를 변경해주세요.', 'warning')
            return redirect(url_for('auth.change_password'))

        # 다음 페이지 처리
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('index')

        flash(f'{user.name}님, 환영합니다!', 'success')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def signup():
    """회원가입 (학부모/학생만)"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = SignupForm()
    if form.validate_on_submit():
        role = form.role.data

        # 학생인 경우 필수 필드 검증
        if role == 'student':
            if not form.grade.data:
                flash('학생은 학년을 선택해야 합니다.', 'error')
                return render_template('auth/signup.html', form=form)
            if not form.school.data:
                flash('학생은 학교명을 입력해야 합니다.', 'error')
                return render_template('auth/signup.html', form=form)
            if not form.birth_date.data:
                flash('학생은 생년월일을 입력해야 합니다.', 'error')
                return render_template('auth/signup.html', form=form)

        mail_configured = bool(current_app.config.get('MAIL_SERVER'))

        # 메일 서버 미설정 시 자동 이메일 인증
        user = User(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data if form.phone.data else None,
            role=role,
            is_active=False,  # 관리자 승인 후 활성화
            email_verified=not mail_configured,
            role_level=5 if role == 'student' else 4
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.flush()

        # 학생인 경우 Student 테이블에도 추가
        if role == 'student':
            from app.models import Student
            default_teacher = User.query.filter(
                User.role.in_(['teacher', 'admin'])
            ).first()

            if default_teacher:
                student_record = Student(
                    teacher_id=default_teacher.user_id,
                    user_id=user.user_id,
                    name=user.name,
                    grade=form.grade.data,
                    school=form.school.data,
                    birth_date=form.birth_date.data,
                    email=user.email,
                    phone=user.phone
                )
                db.session.add(student_record)

        db.session.commit()

        # 관리자에게 신규 가입 알림
        try:
            from app.models.notification import Notification as _Notif
            admin_users = User.query.filter(
                User.role.in_(['admin']),
                User.is_active == True
            ).all()
            for admin in admin_users:
                _Notif.create_notification(
                    user_id=admin.user_id,
                    notification_type='new_user_pending',
                    title='새 회원가입 승인 대기',
                    message=f'{user.name} ({user.role}) 님이 회원가입했습니다. 승인이 필요합니다.',
                    link_url=url_for('admin.pending_users')
                )
        except Exception:
            pass

        # 이메일 인증 메일 발송 (설정된 경우)
        if mail_configured:
            from app.auth.email_utils import send_verification_email
            send_verification_email(user)
        db.session.commit()
        return redirect(url_for('auth.pending_approval'))

    return render_template('auth/signup.html', form=form)


@auth_bp.route('/verify-email-sent')
def verify_email_sent():
    """이메일 인증 발송 안내 페이지"""
    email = request.args.get('email', '')
    return render_template('auth/verify_email_sent.html', email=email)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """이메일 인증 처리"""
    from app.auth.email_utils import verify_email_token
    email = verify_email_token(token)

    if not email:
        flash('인증 링크가 만료되었거나 유효하지 않습니다.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'error')
        return redirect(url_for('auth.login'))

    if user.email_verified:
        flash('이미 인증된 이메일입니다.', 'info')
        return redirect(url_for('auth.login'))

    user.email_verified = True
    user.email_verification_token = None
    db.session.commit()

    flash('이메일 인증이 완료되었습니다! 로그인해주세요.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['POST'])
@limiter.limit("3 per hour", methods=["POST"])
def resend_verification():
    """인증 이메일 재발송"""
    email = request.form.get('email', '').strip()
    user = User.query.filter_by(email=email).first()

    if user and not user.email_verified:
        from app.auth.email_utils import send_verification_email
        send_verification_email(user)
        db.session.commit()

    # 보안상 사용자 존재 여부 노출 방지
    flash('인증 이메일을 재발송했습니다. 메일함을 확인해주세요.', 'info')
    return redirect(url_for('auth.verify_email_sent', email=email))


@auth_bp.route('/pending-approval')
def pending_approval():
    """승인 대기 페이지 (로그인 여부 무관)"""
    from flask_login import current_user
    # 이미 승인된 활성 유저는 대시보드로
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for('index'))

    # 거절 여부 확인 (account_rejected 알림 존재 여부)
    is_rejected = False
    if current_user.is_authenticated:
        from app.models.notification import Notification
        is_rejected = Notification.query.filter_by(
            user_id=current_user.user_id,
            notification_type='account_rejected'
        ).first() is not None

    return render_template('auth/pending_approval.html', is_rejected=is_rejected)


@auth_bp.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """비밀번호 변경"""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('현재 비밀번호가 올바르지 않습니다.', 'error')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(form.new_password.data)
        current_user.must_change_password = False
        db.session.commit()

        flash('비밀번호가 변경되었습니다.', 'success')
        return redirect(url_for('index'))

    return render_template('auth/change_password.html', form=form)
