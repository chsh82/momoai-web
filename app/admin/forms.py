# -*- coding: utf-8 -*-
"""관리자 폼"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DateField, TimeField, DecimalField, BooleanField, DateTimeField, SelectMultipleField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, URL, Email, ValidationError
from datetime import date, time, datetime


class CourseForm(FlaskForm):
    """수업 생성/수정 폼 (새 버전)"""
    # 1. 학년 선택
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
                       validators=[DataRequired(message='학년을 선택하세요.')])

    # 2. 수업 타입 선택
    course_type = SelectField('수업 타입',
                             choices=[
                                 ('', '-- 수업 타입 선택 --'),
                                 ('베이직', '베이직'),
                                 ('프리미엄', '프리미엄'),
                                 ('정규반', '정규반'),
                                 ('하크니스', '하크니스'),
                                 ('체험단', '체험단'),
                                 ('보강수업', '보강수업'),
                                 ('기타', '기타')
                             ],
                             validators=[DataRequired(message='수업 타입을 선택하세요.')])

    # 3. 교사 선택
    teacher_id = SelectField('담당 강사',
                            validators=[DataRequired(message='담당 강사를 선택하세요.')],
                            coerce=str)

    # 4. 종료 여부 선택
    is_terminated = SelectField('종료 여부',
                               choices=[
                                   ('N', 'N (진행중)'),
                                   ('Y', 'Y (종료)')
                               ],
                               validators=[DataRequired()],
                               default='N')

    # 5. 시작일 선택
    start_date = DateField('수업 시작일',
                          validators=[DataRequired(message='시작일을 입력하세요.')],
                          format='%Y-%m-%d')

    # 6. 요일 선택 (날짜 연동, 수동 변경 가능)
    weekday = SelectField('요일',
                         choices=[
                             ('0', '월요일'),
                             ('1', '화요일'),
                             ('2', '수요일'),
                             ('3', '목요일'),
                             ('4', '금요일'),
                             ('5', '토요일'),
                             ('6', '일요일')
                         ],
                         validators=[Optional()],  # 필수 아님, 시작일 기준으로 자동 설정
                         coerce=int)

    # 7. 시작 시간
    start_time = TimeField('시작 시간',
                          validators=[DataRequired(message='시작 시간을 입력하세요.')],
                          format='%H:%M')

    # 8. 종료 시간 (기본 60분 후)
    end_time = TimeField('종료 시간',
                        validators=[DataRequired(message='종료 시간을 입력하세요.')],
                        format='%H:%M')

    # 9. 사용 여부
    availability_status = SelectField('사용 여부',
                                     choices=[
                                         ('available', '사용'),
                                         ('waiting', '대기'),
                                         ('unavailable', '불가')
                                     ],
                                     validators=[DataRequired()],
                                     default='available')

    # 10. 보강신청 가능여부
    makeup_class_allowed = BooleanField('보강신청 가능', default=True)

    # 종료일 (시작일 바로 밑에 위치, 시작일과 동일하게 초기값 설정)
    end_date = DateField('수업 종료일',
                        validators=[DataRequired(message='종료일을 입력하세요.')],
                        format='%Y-%m-%d')

    # 기존 필드들 (숨김 또는 자동 생성)
    course_name = StringField('수업명', validators=[Optional()])  # 자동 생성
    course_code = StringField('수업 코드', validators=[Optional()])  # 자동 생성
    tier = StringField('등급', validators=[Optional()])
    max_students = IntegerField('최대 정원', default=15)
    schedule_type = StringField('스케줄 유형', default='weekly')
    duration_minutes = IntegerField('수업 시간 (분)', default=60)
    price_per_session = IntegerField('회당 수업료 (원)', default=0)
    status = StringField('상태', default='active')
    description = TextAreaField('수업 설명', validators=[Optional()])


class EnrollmentForm(FlaskForm):
    """수강 신청 폼"""
    student_id = SelectField('학생',
                            validators=[DataRequired(message='학생을 선택하세요.')],
                            coerce=str)

    status = SelectField('상태',
                        choices=[
                            ('active', '수강 중'),
                            ('completed', '완료'),
                            ('dropped', '중도 포기')
                        ],
                        default='active')


class PaymentForm(FlaskForm):
    """결제 등록 폼"""
    enrollment_id = SelectField('수강 신청',
                               validators=[DataRequired(message='수강 신청을 선택하세요.')],
                               coerce=str)

    amount = IntegerField('결제 금액 (원)',
                         validators=[DataRequired(message='결제 금액을 입력하세요.'),
                                   NumberRange(min=0)])

    payment_type = SelectField('결제 유형',
                              choices=[
                                  ('tuition', '수업료'),
                                  ('registration', '등록비'),
                                  ('material', '교재비')
                              ],
                              default='tuition')

    sessions_covered = IntegerField('결제 회차 수',
                                   validators=[Optional(), NumberRange(min=0)],
                                   default=0)

    payment_method = SelectField('결제 방법',
                                choices=[
                                    ('', '-- 선택 --'),
                                    ('card', '카드'),
                                    ('cash', '현금'),
                                    ('transfer', '계좌이체')
                                ],
                                validators=[Optional()])

    notes = TextAreaField('메모',
                         validators=[Optional()],
                         render_kw={'rows': 3})


class AnnouncementForm(FlaskForm):
    """공지사항 작성/수정 폼"""
    title = StringField('제목',
                       validators=[DataRequired(message='제목을 입력하세요.'),
                                 Length(max=200)],
                       render_kw={'placeholder': '공지사항 제목을 입력하세요.'})

    content = TextAreaField('내용',
                           validators=[DataRequired(message='내용을 입력하세요.')],
                           render_kw={'rows': 10, 'placeholder': '공지사항 내용을 입력하세요.'})

    announcement_type = SelectField('공지 유형',
                                   choices=[
                                       ('general', '일반'),
                                       ('urgent', '긴급'),
                                       ('event', '행사'),
                                       ('system', '시스템')
                                   ],
                                   default='general')

    target_roles = SelectMultipleField('공지 대상',
                                      choices=[
                                          ('all', '전체'),
                                          ('student', '학생'),
                                          ('parent', '학부모'),
                                          ('teacher', '강사')
                                      ],
                                      default=['all'])

    target_tiers = SelectMultipleField('대상 등급 (학생만 해당)',
                                      choices=[
                                          ('A', 'A등급'),
                                          ('B', 'B등급'),
                                          ('C', 'C등급'),
                                          ('VIP', 'VIP')
                                      ],
                                      validators=[Optional()])

    is_pinned = BooleanField('상단 고정')
    is_popup = BooleanField('로그인 시 팝업 표시')

    publish_start = DateTimeField('게시 시작일시',
                                 validators=[Optional()],
                                 format='%Y-%m-%dT%H:%M',
                                 render_kw={'type': 'datetime-local'})

    publish_end = DateTimeField('게시 종료일시',
                               validators=[Optional()],
                               format='%Y-%m-%dT%H:%M',
                               render_kw={'type': 'datetime-local'})


class TeachingMaterialForm(FlaskForm):
    """교재 등록/수정 폼"""
    title = StringField('제목',
                       validators=[DataRequired(message='제목을 입력하세요.'),
                                  Length(max=200, message='제목은 200자 이내로 입력하세요.')])

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
                       validators=[DataRequired(message='학년을 선택하세요.')])

    file_upload = FileField('파일 업로드',
                           validators=[
                               FileAllowed(['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'hwp', 'zip'],
                                         '허용된 파일: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, HWP, ZIP')
                           ])

    publish_date = DateField('게시 시작일',
                            validators=[DataRequired(message='게시 시작일을 선택하세요.')],
                            default=date.today)

    end_date = DateField('게시 종료일',
                        validators=[DataRequired(message='게시 종료일을 선택하세요.')])

    is_public = BooleanField('공개', default=True)

    target_type = SelectField('대상 선택 방식',
                             choices=[
                                 ('grade', '학년별'),
                                 ('course', '수업별')
                             ],
                             default='grade',
                             validators=[DataRequired()])

    target_grades = SelectMultipleField('대상 학년',
                                       choices=[
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
                                       validators=[Optional()])

    target_course_ids = HiddenField('대상 수업 IDs')


class VideoForm(FlaskForm):
    """동영상 등록/수정 폼"""
    title = StringField('제목',
                       validators=[DataRequired(message='제목을 입력하세요.'),
                                  Length(max=200, message='제목은 200자 이내로 입력하세요.')])

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
                       validators=[DataRequired(message='학년을 선택하세요.')])

    youtube_url = StringField('YouTube URL',
                             validators=[
                                 DataRequired(message='YouTube URL을 입력하세요.'),
                                 Length(max=500, message='URL은 500자 이내로 입력하세요.')
                             ])

    publish_date = DateField('게시 시작일',
                            validators=[DataRequired(message='게시 시작일을 선택하세요.')],
                            default=date.today)

    end_date = DateField('게시 종료일',
                        validators=[DataRequired(message='게시 종료일을 선택하세요.')])

    is_public = BooleanField('공개', default=True)

    target_type = SelectField('대상 선택 방식',
                             choices=[
                                 ('grade', '학년별'),
                                 ('course', '수업별')
                             ],
                             default='grade',
                             validators=[DataRequired()])

    target_grades = SelectMultipleField('대상 학년',
                                       choices=[
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
                                       validators=[Optional()])

    target_course_ids = HiddenField('대상 수업 IDs')


class CreatePaymentForm(FlaskForm):
    """결제 생성 폼"""
    grade_filter = SelectField('학년 필터',
                              choices=[
                                  ('', '전체 학년'),
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
                              validators=[Optional()])

    student_id = HiddenField('학생 ID',
                            validators=[DataRequired(message='학생을 선택하세요.')])

    course_id = SelectField('수업',
                           validators=[DataRequired(message='수업을 선택하세요.')],
                           coerce=str)

    payment_period = SelectField('결제 주기',
                                choices=[
                                    ('monthly', '월별 결제 (4회)'),
                                    ('quarterly', '분기별 결제 (12회)')
                                ],
                                default='monthly',
                                validators=[DataRequired(message='결제 주기를 선택하세요.')])

    carryover_option = SelectField('이월결석',
                                  choices=[
                                      ('0', '0회 (없음)'),
                                      ('1', '1회'),
                                      ('2', '2회'),
                                      ('3', '3회'),
                                      ('4', '4회'),
                                      ('custom', '직접 입력')
                                  ],
                                  default='0')

    carryover_absences = IntegerField('이월결석 횟수',
                                     validators=[Optional(), NumberRange(min=0, max=12)],
                                     default=0)

    price_option = SelectField('수업료 선택',
                              choices=[
                                  ('65000', '65,000원 (프리미엄)'),
                                  ('60000', '60,000원 (정규반할인)'),
                                  ('70000', '70,000원 (하크니스)'),
                                  ('75000', '75,000원 (프런티어반)'),
                                  ('custom', '직접 입력')
                              ],
                              default='65000')

    price_per_session = IntegerField('회당 수업료 (원)',
                                    validators=[Optional(), NumberRange(min=0)],
                                    default=65000)

    discount_type = SelectField('할인 유형',
                               choices=[
                                   ('none', '할인 없음'),
                                   ('acquaintance', '지인 할인 (20%)'),
                                   ('sibling', '형제 할인 (10%)'),
                                   ('quarterly', '분기별 결제 할인 (5%)')
                               ],
                               default='none')

    payment_method = SelectField('결제 방법',
                                choices=[
                                    ('', '-- 선택 --'),
                                    ('card', '카드'),
                                    ('cash', '현금'),
                                    ('transfer', '계좌이체')
                                ],
                                default='card',
                                validators=[Optional()])

    due_date = DateField('납부 기한',
                        validators=[Optional()],
                        format='%Y-%m-%d')

    notes = TextAreaField('메모',
                         validators=[Optional()],
                         render_kw={'rows': 3})

    submit = SubmitField('결제 생성')


class CreateStaffForm(FlaskForm):
    """직원 계정 생성 폼 (강사/관리자)"""
    name = StringField('이름', validators=[
        DataRequired(message='이름을 입력해주세요.'),
        Length(min=2, max=100, message='이름은 2-100자 사이여야 합니다.')
    ])
    email = StringField('이메일', validators=[
        DataRequired(message='이메일을 입력해주세요.'),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])
    phone = StringField('전화번호', validators=[
        Length(max=50, message='전화번호는 최대 50자까지 입력 가능합니다.')
    ])
    role = SelectField('역할',
        choices=[('teacher', '강사'), ('admin', '관리자')],
        validators=[DataRequired(message='역할을 선택해주세요.')]
    )
    submit = SubmitField('계정 생성')

    def validate_email(self, field):
        """이메일 중복 체크"""
        from app.models import User
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('이미 사용 중인 이메일입니다.')


class ZoomLinkForm(FlaskForm):
    """줌 링크 관리 폼"""
    zoom_link = StringField('줌 링크 URL', validators=[
        DataRequired(message='줌 링크를 입력해주세요.'),
        URL(message='올바른 URL 형식이 아닙니다.'),
        Length(max=500, message='URL은 최대 500자까지 입력 가능합니다.')
    ])
    submit = SubmitField('저장')

    def validate_zoom_link(self, field):
        """줌 링크 URL 유효성 검사"""
        if not field.data.startswith('https://'):
            raise ValidationError('HTTPS로 시작하는 URL을 입력해주세요.')
        if 'zoom.us' not in field.data and 'zoom.com' not in field.data:
            raise ValidationError('올바른 줌 링크가 아닙니다.')


class StudentProfileForm(FlaskForm):
    """학생 기초 조사 프로필 폼"""
    # 학생 선택
    student_id = SelectField('학생', validators=[DataRequired()], coerce=str)

    # 기본 정보
    survey_date = DateField('설문 작성일', default=date.today, validators=[Optional()])
    address = TextAreaField('주소', validators=[Optional()])
    parent_contact = StringField('학부모 연락처', validators=[Optional(), Length(max=50)])
    current_school = StringField('재학 중인 학교', validators=[Optional(), Length(max=100)])

    # 독서 경험 및 역량
    reading_experience = SelectField('독서논술 수업 경험',
                                    choices=[
                                        ('', '-- 선택하세요 --'),
                                        ('없음', '없음'),
                                        ('6개월 미만', '6개월 미만'),
                                        ('6개월~1년', '6개월~1년'),
                                        ('1년~2년', '1년~2년'),
                                        ('2년 이상', '2년 이상')
                                    ],
                                    validators=[Optional()])

    reading_competency = SelectField('독서 역량',
                                    choices=[
                                        ('', '-- 선택하세요 --'),
                                        ('1', '1 - 매우 낮음'),
                                        ('2', '2 - 낮음'),
                                        ('3', '3 - 보통'),
                                        ('4', '4 - 높음'),
                                        ('5', '5 - 매우 높음')
                                    ],
                                    validators=[Optional()])

    weekly_reading_amount = SelectField('주 평균 독서량',
                                       choices=[
                                           ('', '-- 선택하세요 --'),
                                           ('주 1권 미만', '주 1권 미만'),
                                           ('주 1-2권', '주 1-2권'),
                                           ('주 3-4권', '주 3-4권'),
                                           ('주 5권 이상', '주 5권 이상')
                                       ],
                                       validators=[Optional()])

    # 선호 독서 분야 (다중 선택)
    preferred_genres = SelectMultipleField('선호 독서 분야',
                                          choices=[
                                              ('한국문학', '한국문학'),
                                              ('세계문학', '세계문학'),
                                              ('역사', '역사'),
                                              ('사회', '사회'),
                                              ('과학', '과학'),
                                              ('예술', '예술'),
                                              ('철학', '철학'),
                                              ('기타', '기타')
                                          ],
                                          validators=[Optional()])

    # 학생 성향 (다중 선택)
    personality_traits = SelectMultipleField('학생 성향',
                                            choices=[
                                                ('사교적임', '사교적임'),
                                                ('낯가림이 있음', '낯가림이 있음'),
                                                ('소극적인 성격', '소극적인 성격'),
                                                ('적극적인 성격', '적극적인 성격'),
                                                ('집중력이 높음', '집중력이 높음'),
                                                ('산만한 편', '산만한 편'),
                                                ('꼼꼼함', '꼼꼼함'),
                                                ('창의적임', '창의적임')
                                            ],
                                            validators=[Optional()])

    # 수업 목표
    main_improvement_goal = TextAreaField('주요 향상 목표', validators=[Optional()])
    preferred_class_style = TextAreaField('선호 수업 스타일', validators=[Optional()])
    teacher_request = TextAreaField('강사 요청사항', validators=[Optional()])

    # 유입 경로
    referral_source = SelectField('유입 경로',
                                 choices=[
                                     ('', '-- 선택하세요 --'),
                                     ('인터넷 검색', '인터넷 검색'),
                                     ('지인 추천', '지인 추천'),
                                     ('SNS', 'SNS'),
                                     ('기타', '기타')
                                 ],
                                 validators=[Optional()])

    # 진로/진학 정보
    education_info_needs = SelectMultipleField('필요한 교육 정보',
                                              choices=[
                                                  ('대학입시 관련 정보', '대학입시 관련 정보'),
                                                  ('중고등 입시 관련 정보', '중고등 입시 관련 정보'),
                                                  ('독서논술 관련 정보', '독서논술 관련 정보'),
                                                  ('진로 관련 정보', '진로 관련 정보')
                                              ],
                                              validators=[Optional()])

    academic_goals = SelectMultipleField('진학 목표',
                                        choices=[
                                            ('국내대학 진학 희망', '국내대학 진학 희망'),
                                            ('해외대학 진학 희망', '해외대학 진학 희망'),
                                            ('영재고/과학고 진학 희망', '영재고/과학고 진학 희망'),
                                            ('국제고/외고 진학 희망', '국제고/외고 진학 희망'),
                                            ('자사고 진학 희망', '자사고 진학 희망'),
                                            ('예체능 특기자 진학', '예체능 특기자 진학')
                                        ],
                                        validators=[Optional()])

    career_interests = SelectMultipleField('진로 관심 분야',
                                          choices=[
                                              ('의학계열', '의학계열'),
                                              ('공학계열', '공학계열'),
                                              ('인문학계열', '인문학계열'),
                                              ('사회과학계열', '사회과학계열'),
                                              ('자연과학계열', '자연과학계열'),
                                              ('예체능계열', '예체능계열'),
                                              ('교육계열', '교육계열'),
                                              ('기타', '기타')
                                          ],
                                          validators=[Optional()])

    other_interests = TextAreaField('기타 관심사항', validators=[Optional()])
    sibling_info = TextAreaField('형제자매 정보', validators=[Optional()],
                                description='예: 초5 남, 중2 여')

    submit = SubmitField('저장')
