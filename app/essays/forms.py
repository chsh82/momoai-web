# -*- coding: utf-8 -*-
"""첨삭 관리 폼"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import SelectField, SelectMultipleField, TextAreaField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class NewEssayForm(FlaskForm):
    """새 첨삭 시작 폼"""
    student_id = SelectField('학생 선택',
        validators=[DataRequired(message='학생을 선택해주세요.')],
        coerce=str
    )

    title = StringField('제목 (선택사항)', validators=[
        Optional(),
        Length(max=255, message='제목은 255자 이내여야 합니다.')
    ])

    essay_text = TextAreaField('논술문',
        validators=[
            DataRequired(message='논술문을 입력해주세요.'),
            Length(min=50, message='논술문은 최소 50자 이상이어야 합니다.')
        ],
        render_kw={'rows': 15, 'placeholder': '학생이 작성한 논술문을 입력하세요...'}
    )

    notes = TextAreaField('주의사항 (선택사항)',
        validators=[Optional()],
        render_kw={'rows': 3, 'placeholder': '첨삭 시 참고할 주의사항이나 특이사항을 입력하세요...'}
    )

    attachment = FileField('첨부 파일 (이미지, 워드 등)',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'pdf', 'doc', 'docx', 'hwp', 'txt'],
                       '이미지(JPG, PNG, GIF), PDF, 워드(DOC, DOCX), 한글(HWP), 텍스트 파일만 업로드 가능합니다.')
        ]
    )

    book_ids = SelectMultipleField('참고 도서 (선택사항)',
        validators=[Optional()],
        coerce=str,
        render_kw={'size': 5}
    )

    submit = SubmitField('첨삭 시작')


class RevisionRequestForm(FlaskForm):
    """수정 요청 폼"""
    revision_note = TextAreaField('수정 요청 내용',
        validators=[
            DataRequired(message='수정할 내용을 입력해주세요.'),
            Length(min=10, message='수정 요청 내용은 최소 10자 이상이어야 합니다.')
        ],
        render_kw={'rows': 5, 'placeholder': '어떤 부분을 수정하거나 보완해야 할지 구체적으로 작성해주세요...'}
    )

    submit = SubmitField('재생성 요청')
