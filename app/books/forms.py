# -*- coding: utf-8 -*-
"""도서 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class BookForm(FlaskForm):
    """도서 추가/수정 폼"""
    title = StringField('도서 제목',
                       validators=[DataRequired(message='도서 제목을 입력하세요.'),
                                 Length(max=500)])

    author = StringField('저자',
                        validators=[Optional(), Length(max=200)])

    publisher = StringField('출판사',
                           validators=[Optional(), Length(max=200)])

    isbn = StringField('ISBN',
                      validators=[Optional(), Length(max=20)])

    publication_year = IntegerField('출판년도',
                                   validators=[Optional(),
                                             NumberRange(min=1900, max=2100,
                                                       message='올바른 출판년도를 입력하세요.')])

    category = SelectField('카테고리',
                          choices=[
                              ('', '선택 안 함'),
                              ('literature', '문학'),
                              ('philosophy', '철학'),
                              ('history', '역사'),
                              ('science', '과학'),
                              ('social', '사회'),
                              ('art', '예술'),
                              ('language', '언어'),
                              ('other', '기타')
                          ],
                          validators=[Optional()])

    description = TextAreaField('설명',
                               validators=[Optional()])

    cover_image_url = StringField('표지 이미지 URL',
                                  validators=[Optional(), Length(max=500)])
