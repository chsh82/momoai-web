# -*- coding: utf-8 -*-
"""커뮤니티 폼"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length


class PostForm(FlaskForm):
    """게시글 작성/수정 폼"""
    title = StringField('제목',
                       validators=[DataRequired(message='제목을 입력하세요.'),
                                 Length(max=500)])

    content = TextAreaField('내용',
                           validators=[DataRequired(message='내용을 입력하세요.')])

    category = SelectField('카테고리',
                          choices=[
                              ('notice', '📢 공지'),
                              ('question', '❓ 질문'),
                              ('free', '💬 자유'),
                              ('resource', '📚 자료')
                          ],
                          validators=[DataRequired(message='카테고리를 선택하세요.')])

    tags = StringField('태그',
                      validators=[Length(max=200)],
                      render_kw={'placeholder': '태그를 쉼표(,)로 구분하여 입력하세요 (예: 논술, 철학, 첨삭)'})

    files = MultipleFileField('파일 첨부',
                             validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip'],
                                                    '지원하지 않는 파일 형식입니다.')])


class CommentForm(FlaskForm):
    """댓글 작성 폼"""
    content = TextAreaField('댓글',
                           validators=[DataRequired(message='댓글 내용을 입력하세요.'),
                                     Length(max=1000)])
