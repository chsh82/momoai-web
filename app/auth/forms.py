# -*- coding: utf-8 -*-
"""인증 폼"""
import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField, SelectField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models import User


def validate_password_strength(form, field):
    """비밀번호 복잡도 검증 (소문자, 숫자, 특수문자 필수)"""
    password = field.data
    if not re.search(r'[a-z]', password):
        raise ValidationError('비밀번호에 영문 소문자를 포함해야 합니다.')
    if not re.search(r'\d', password):
        raise ValidationError('비밀번호에 숫자를 포함해야 합니다.')
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password):
        raise ValidationError('비밀번호에 특수문자(!@#$%^&* 등)를 포함해야 합니다.')


class LoginForm(FlaskForm):
    """로그인 폼"""
    email = StringField('이메일', validators=[
        DataRequired(message='이메일을 입력해주세요.'),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message='비밀번호를 입력해주세요.')
    ])
    remember_me = BooleanField('로그인 상태 유지')
    submit = SubmitField('로그인')


class SignupForm(FlaskForm):
    """회원가입 폼"""
    name = StringField('이름', validators=[
        DataRequired(message='이름을 입력해주세요.'),
        Length(min=2, max=100, message='이름은 2-100자 사이여야 합니다.')
    ])
    email = StringField('이메일', validators=[
        DataRequired(message='이메일을 입력해주세요.'),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message='비밀번호를 입력해주세요.'),
        Length(min=8, message='비밀번호는 최소 8자 이상이어야 합니다.'),
        validate_password_strength
    ])
    password_confirm = PasswordField('비밀번호 확인', validators=[
        DataRequired(message='비밀번호 확인을 입력해주세요.'),
        EqualTo('password', message='비밀번호가 일치하지 않습니다.')
    ])
    role = RadioField('계정 유형',
        choices=[('parent', '학부모'), ('student', '학생')],
        default='parent',
        validators=[DataRequired(message='계정 유형을 선택해주세요.')]
    )
    phone = StringField('전화번호 (선택)', validators=[
        Length(max=50, message='전화번호는 최대 50자까지 입력 가능합니다.')
    ])

    # 학생 전용 필드 (role='student'일 때만 필수)
    grade = SelectField('학년',
        choices=[
            ('', '-- 학년 선택 --'),
            ('초1', '초등 1학년'),
            ('초2', '초등 2학년'),
            ('초3', '초등 3학년'),
            ('초4', '초등 4학년'),
            ('초5', '초등 5학년'),
            ('초6', '초등 6학년'),
            ('중1', '중등 1학년'),
            ('중2', '중등 2학년'),
            ('중3', '중등 3학년'),
            ('고1', '고등 1학년'),
            ('고2', '고등 2학년'),
            ('고3', '고등 3학년'),
        ],
        validators=[Optional()]
    )
    school = StringField('학교명', validators=[
        Optional(),
        Length(max=200, message='학교명은 최대 200자까지 입력 가능합니다.')
    ])
    birth_date = DateField('생년월일', validators=[Optional()], format='%Y-%m-%d')

    submit = SubmitField('회원가입')

    def validate_email(self, field):
        """이메일 중복 체크"""
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('이미 사용 중인 이메일입니다.')


class ChangePasswordForm(FlaskForm):
    """비밀번호 변경 폼"""
    current_password = PasswordField('현재 비밀번호', validators=[
        DataRequired(message='현재 비밀번호를 입력해주세요.')
    ])
    new_password = PasswordField('새 비밀번호', validators=[
        DataRequired(message='새 비밀번호를 입력해주세요.'),
        Length(min=8, message='비밀번호는 최소 8자 이상이어야 합니다.'),
        validate_password_strength
    ])
    new_password_confirm = PasswordField('새 비밀번호 확인', validators=[
        DataRequired(message='새 비밀번호 확인을 입력해주세요.'),
        EqualTo('new_password', message='비밀번호가 일치하지 않습니다.')
    ])
    submit = SubmitField('비밀번호 변경')
