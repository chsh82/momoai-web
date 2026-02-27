# -*- coding: utf-8 -*-
"""학생 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length


class StudentForm(FlaskForm):
    """학생 추가/수정 폼"""
    name = StringField('이름', validators=[
        DataRequired(message='학생 이름을 입력해주세요.'),
        Length(min=2, max=100, message='이름은 2-100자 사이여야 합니다.')
    ])

    grade = SelectField('학년',
        choices=[
            ('초1', '초등 1학년'), ('초2', '초등 2학년'), ('초3', '초등 3학년'),
            ('초4', '초등 4학년'), ('초5', '초등 5학년'), ('초6', '초등 6학년'),
            ('중1', '중학교 1학년'), ('중2', '중학교 2학년'), ('중3', '중학교 3학년'),
            ('고1', '고등학교 1학년'), ('고2', '고등학교 2학년'), ('고3', '고등학교 3학년'),
            ('기타', '기타'),
        ],
        validators=[DataRequired(message='학년을 선택해주세요.')]
    )

    email = StringField('이메일', validators=[
        Optional(),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])

    phone = StringField('전화번호', validators=[
        Optional(),
        Length(max=50, message='전화번호는 50자 이내여야 합니다.')
    ])

    country = StringField('거주 국가', validators=[Optional(), Length(max=100)])
    city = StringField('거주 도시', validators=[Optional(), Length(max=100)])

    notes = TextAreaField('메모', validators=[
        Optional()
    ])

    submit = SubmitField('저장')


class StudentSearchForm(FlaskForm):
    """학생 검색 폼"""
    search = StringField('학생 이름 검색', validators=[Optional()])
    grade_filter = SelectField('학년 필터',
        choices=[
            ('', '전체'),
            ('초등', '초등'),
            ('중등', '중등'),
            ('고등', '고등')
        ],
        validators=[Optional()]
    )
    submit = SubmitField('검색')
