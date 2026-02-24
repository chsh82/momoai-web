# -*- coding: utf-8 -*-
"""프로필 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional


class ProfileEditForm(FlaskForm):
    """프로필 수정 폼"""
    name = StringField('이름',
                      validators=[DataRequired(message='이름을 입력하세요.'),
                                Length(max=100)])

    email = StringField('이메일',
                       validators=[DataRequired(message='이메일을 입력하세요.'),
                                 Email(message='올바른 이메일 형식이 아닙니다.'),
                                 Length(max=100)])

    phone = StringField('전화번호',
                       validators=[Optional(),
                                 Length(max=50)])

    # 학생 전용 필드
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

    school = StringField('학교명',
                        validators=[Optional(),
                                  Length(max=200)])

    birth_date = DateField('생년월일',
                          validators=[Optional()],
                          format='%Y-%m-%d')

    country = StringField('거주 국가',
                         validators=[Optional(), Length(max=100)],
                         render_kw={'placeholder': '예: 대한민국, 미국, 캐나다'})

    city = StringField('거주 도시',
                       validators=[Optional(), Length(max=100)],
                       render_kw={'placeholder': '예: 서울, 부산, 뉴욕'})

    submit = SubmitField('프로필 수정')


class PasswordChangeForm(FlaskForm):
    """비밀번호 변경 폼"""
    current_password = PasswordField('현재 비밀번호',
                                    validators=[DataRequired(message='현재 비밀번호를 입력하세요.')])

    new_password = PasswordField('새 비밀번호',
                                validators=[
                                    DataRequired(message='새 비밀번호를 입력하세요.'),
                                    Length(min=6, message='비밀번호는 최소 6자 이상이어야 합니다.')
                                ])

    confirm_password = PasswordField('비밀번호 확인',
                                    validators=[
                                        DataRequired(message='비밀번호 확인을 입력하세요.'),
                                        EqualTo('new_password', message='비밀번호가 일치하지 않습니다.')
                                    ])

    submit = SubmitField('비밀번호 변경')
