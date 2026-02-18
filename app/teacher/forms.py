# -*- coding: utf-8 -*-
"""강사 폼"""
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, StringField, DateField
from wtforms.validators import DataRequired, Length, Optional
from datetime import date


class TeacherFeedbackForm(FlaskForm):
    """강사 피드백 폼"""
    student_id = SelectField('학생',
                            validators=[DataRequired(message='학생을 선택하세요.')],
                            coerce=str)

    parent_id = SelectField('학부모',
                           validators=[DataRequired(message='학부모를 선택하세요.')],
                           coerce=str)

    feedback_type = SelectField('피드백 유형',
                               choices=[
                                   ('general', '일반'),
                                   ('progress', '학습 진도'),
                                   ('behavior', '수업 태도'),
                                   ('attendance', '출석 관련')
                               ],
                               default='general')

    priority = SelectField('중요도',
                          choices=[
                              ('normal', '보통'),
                              ('high', '중요'),
                              ('low', '낮음')
                          ],
                          default='normal')

    title = StringField('제목',
                       validators=[DataRequired(message='제목을 입력하세요.'),
                                 Length(max=200)])

    content = TextAreaField('내용',
                           validators=[DataRequired(message='내용을 입력하세요.')],
                           render_kw={'rows': 10})


class SessionNoteForm(FlaskForm):
    """수업 메모 폼"""
    topic = StringField('수업 주제',
                       validators=[Optional(), Length(max=200)])

    description = TextAreaField('수업 내용',
                               validators=[Optional()],
                               render_kw={'rows': 5})


class ConsultationRecordForm(FlaskForm):
    """상담 기록 폼"""
    consultation_date = DateField('상담일',
                                 validators=[DataRequired(message='상담일을 선택하세요.')],
                                 default=date.today)

    counselor_id = SelectField('상담자',
                              validators=[Optional()],
                              coerce=str)

    student_id = SelectField('학생',
                            validators=[DataRequired(message='학생을 선택하세요.')],
                            coerce=str)

    major_category = SelectField('대분류',
                                choices=[
                                    ('신규상담', '신규상담'),
                                    ('퇴원상담', '퇴원상담'),
                                    ('분기별상담', '분기별상담'),
                                    ('진로진학상담', '진로진학상담'),
                                    ('기타', '기타')
                                ],
                                validators=[DataRequired(message='대분류를 선택하세요.')])

    sub_category = SelectField('소분류 (선택)',
                              choices=[('', '-- 선택하세요 --')],
                              validators=[Optional()])

    content = TextAreaField('상담 내용',
                           validators=[DataRequired(message='상담 내용을 입력하세요.')],
                           render_kw={'rows': 10})
