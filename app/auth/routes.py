# -*- coding: utf-8 -*-
"""인증 라우트"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app.auth import auth_bp
from app.auth.forms import LoginForm, SignupForm, ChangePasswordForm
from app.models import db, User


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('비활성화된 계정입니다. 관리자에게 문의하세요.', 'error')
            return redirect(url_for('auth.login'))

        # 로그인 처리
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()

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

        # 학부모와 학생은 즉시 활성화
        user = User(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data if form.phone.data else None,
            role=role,
            is_active=True,
            role_level=5 if role == 'student' else 4  # student=5, parent=4
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.flush()  # user_id 생성

        # 학생인 경우 Student 테이블에도 추가 (부모-자녀 연결을 위해)
        if role == 'student':
            from app.models import Student

            # 기본 담당 강사 찾기 (시스템 관리자 또는 첫 번째 강사)
            default_teacher = User.query.filter(
                User.role.in_(['teacher', 'admin'])
            ).first()

            if default_teacher:
                student_record = Student(
                    teacher_id=default_teacher.user_id,
                    user_id=user.user_id,
                    name=user.name,
                    grade=form.grade.data,  # 폼에서 입력받은 정확한 학년
                    school=form.school.data,  # 학교명
                    birth_date=form.birth_date.data,  # 생년월일
                    email=user.email,
                    phone=user.phone
                )
                db.session.add(student_record)

        db.session.commit()

        flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/signup.html', form=form)


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
        current_user.must_change_password = False  # 비밀번호 변경 완료
        db.session.commit()

        flash('비밀번호가 변경되었습니다.', 'success')
        return redirect(url_for('index'))

    return render_template('auth/change_password.html', form=form)
