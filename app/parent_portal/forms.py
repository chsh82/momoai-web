# -*- coding: utf-8 -*-
"""학부모 포털 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SelectMultipleField, RadioField
from wtforms.validators import DataRequired, Optional
from datetime import date


class StudentRegistrationSurveyForm(FlaskForm):
    """신규 학생 등록 설문 폼"""

    # 1-7: 기본 정보
    student_name = StringField('1. 학생의 이름',
                              validators=[DataRequired(message='학생 이름을 입력하세요.')],
                              render_kw={'placeholder': '예: 홍길동'})

    student_gender = RadioField('2. 학생의 성별',
                               choices=[('남', '남'), ('여', '여')],
                               validators=[DataRequired(message='성별을 선택하세요.')])

    student_birthdate = DateField('3. 학생의 생년월일',
                                 validators=[DataRequired(message='생년월일을 입력하세요.')],
                                 format='%Y-%m-%d')

    address = TextAreaField('4. 주소 (신규 학생들에게는 원고지 1권과 가이드가 발송됩니다, 발송 시 우편물을 받으실 수 있도록 동,호수까지 적어주시면 감사하겠습니다. 해외학생들은 배송이 어려운 점 양해 부탁드립니다).',
                           validators=[DataRequired(message='주소를 입력하세요.')],
                           render_kw={'rows': 2, 'placeholder': '예: 서울시 강남구 테헤란로 123, 456호'})

    parent_contact = StringField('5. 학부모 연락처',
                                validators=[DataRequired(message='연락처를 입력하세요.')],
                                render_kw={'placeholder': '예: 010-1234-5678'})

    current_school = StringField('6. 재학 중인 학교 이름',
                                validators=[DataRequired(message='학교 이름을 입력하세요.')],
                                render_kw={'placeholder': '예: 서울초등학교'})

    grade = SelectField('7. <2026년>을 기준으로 학생은 몇 학년인가요?',
                       choices=[
                           ('', '-- 선택하세요 --'),
                           ('초1', '초등학교 1학년'),
                           ('초2', '초등학교 2학년'),
                           ('초3', '초등학교 3학년'),
                           ('초4', '초등학교 4학년'),
                           ('초5', '초등학교 5학년'),
                           ('초6', '초등학교 6학년'),
                           ('중1', '중학교 1학년'),
                           ('중2', '중학교 2학년'),
                           ('중3', '중학교 3학년'),
                       ],
                       validators=[DataRequired(message='학년을 선택하세요.')])

    # 8-12: 독서 경험 및 역량
    reading_experience = RadioField('8. 독서논술 수업 경험 및 기간',
                                   choices=[
                                       ('독서논술 수업 경험 없음', '독서논술 수업 경험 없음'),
                                       ('독서논술 경험 6개월 미만', '독서논술 경험 6개월 미만'),
                                       ('독서논술 경험 6개월~1년', '독서논술 경험 6개월~1년'),
                                       ('독서논술 경험 1년~2년', '독서논술 경험 1년~2년'),
                                       ('독서논술 경험 2년 이상', '독서논술 경험 2년 이상')
                                   ],
                                   validators=[DataRequired(message='독서논술 경험을 선택하세요.')])

    reading_competency = RadioField('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.',
                                   choices=[
                                       ('독서역량 매우 부족', '독서역량 매우 부족'),
                                       ('독서역량 부족', '독서역량 부족'),
                                       ('독서역량 보통', '독서역량 보통'),
                                       ('독서역량 우수', '독서역량 우수'),
                                       ('독서역량 매우 우수', '독서역량 매우 우수')
                                   ],
                                   validators=[DataRequired(message='독서역량을 선택하세요.')])

    weekly_reading_amount = SelectField('10. 학생의 한 주 평균 독서량을 체크해주세요.',
                                       choices=[
                                           ('', '-- 선택하세요 --'),
                                           ('독서평균 주 1권 미만', '독서평균 주 1권 미만'),
                                           ('독서평균 주 1~2권', '독서평균 주 1~2권'),
                                           ('독서평균 주 3~5권', '독서평균 주 3~5권'),
                                           ('독서평균 주 5권 이상', '독서평균 주 5권 이상'),
                                       ],
                                       validators=[DataRequired(message='주 평균 독서량을 선택하세요.')])

    preferred_genres = SelectMultipleField('11. 학생이 선호하는 독서 분야를 모두 선택해주세요 (중복 선택 가능)',
                                          choices=[
                                              ('고전', '고전'),
                                              ('사회', '사회'),
                                              ('과학', '과학'),
                                              ('인문철학', '인문철학'),
                                              ('경제', '경제'),
                                              ('한국문학', '한국문학'),
                                              ('세계문학', '세계문학'),
                                              ('역사', '역사')
                                          ],
                                          validators=[Optional()])

    personality_traits = SelectMultipleField('12. 학생의 성향을 모두 알려주세요 (중복 선택 가능)',
                                            choices=[
                                                ('낯가림이 있으며 소극적인 성격', '낯가림이 있으며 소극적인 성격'),
                                                ('활발하며 적극적인 성격', '활발하며 적극적인 성격'),
                                                ('집중력이 높음', '집중력이 높음'),
                                                ('사교적임', '사교적임')
                                            ],
                                            validators=[DataRequired(message='학생 성향을 선택하세요.')])

    # 13, 17-19: 수업 목표 및 요청사항
    main_improvement_goal = RadioField('13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)',
                                      choices=[
                                          ('읽기능력 향상 희망 - 정독 습관', '읽기능력 향상 희망 - 정독 습관'),
                                          ('읽기능력 향상 희망 - 다양한 분야의 독서', '읽기능력 향상 희망 - 다양한 분야의 독서'),
                                          ('쓰기능력 향상 희망 - 첨삭을 통한 글쓰기 실력 향상', '쓰기능력 향상 희망 - 첨삭을 통한 글쓰기 실력 향상'),
                                          ('쓰기능력 향상 희망 - 다양한 주제로 글쓰기', '쓰기능력 향상 희망 - 다양한 주제로 글쓰기'),
                                          ('말하기 능력 향상 희망 - 논리적 표현력 향상', '말하기 능력 향상 희망 - 논리적 표현력 향상'),
                                          ('말하기 능력 향상 희망 - 소통 능력', '말하기 능력 향상 희망 - 소통 능력')
                                      ],
                                      validators=[DataRequired(message='향상 희망 부분을 선택하세요.')])

    preferred_class_style = RadioField('17. 가장 선호하는 수업 목표를 선택해주세요 (1개만 선택 가능)',
                                      choices=[
                                          ('책을 전반적으로 살피는 수업 선호', '책을 전반적으로 살피는 수업 선호'),
                                          ('한 가지 질문이라도 깊이 있게 토론하는 수업 선호', '한 가지 질문이라도 깊이 있게 토론하는 수업 선호'),
                                          ('교재에 답을 자세하게 기록하는 수업 선호', '교재에 답을 자세하게 기록하는 수업 선호'),
                                          ('피드백이 꼼꼼한 수업 선호', '피드백이 꼼꼼한 수업 선호'),
                                          ('첨삭이 꼼꼼한 수업 선호', '첨삭이 꼼꼼한 수업 선호')
                                      ],
                                      validators=[DataRequired(message='선호 수업 목표를 선택하세요.')])

    teacher_request = TextAreaField('18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요 (학생 특이사항 또는 요청하고 싶은 부분이 있다면 구체적으로 작성 부탁드립니다)',
                                   validators=[Optional()],
                                   render_kw={'rows': 4, 'placeholder': '자녀의 수업에 대한 요청사항을 자유롭게 작성해주세요.'})

    referral_source = SelectField('19. 모모의 책장을 어떻게 알게 되셨나요?',
                                 choices=[
                                     ('', '-- 선택하세요 --'),
                                     ('인터넷 검색', '인터넷 검색'),
                                     ('지인 추천', '지인 추천'),
                                     ('재원생 형제', '재원생 형제'),
                                     ('네이버 카페', '네이버 카페'),
                                     ('네이버 블로그', '네이버 블로그'),
                                     ('인스타그램', '인스타그램'),
                                     ('유튜브 (최성호의 육하원칙)', '유튜브 (최성호의 육하원칙)'),
                                     ('그 외 유튜브 추천 영상', '그 외 유튜브 추천 영상'),
                                     ('기타', '기타')
                                 ],
                                 validators=[DataRequired(message='유입 경로를 선택하세요.')])

    # 20-22: 진로/진학 정보 (섹션 2 - 추가 정보)
    education_info_needs = SelectMultipleField('20. 필요한 교육&입시 정보가 있으신가요? (관심 있으신 부분에 모두 체크해주세요)',
                                              choices=[
                                                  ('대학입시 관련 정보', '대학입시 관련 정보'),
                                                  ('중고등 입시 관련 정보', '중고등 입시 관련 정보'),
                                                  ('학원가 정보', '학원가 정보'),
                                                  ('독서논술 관련 정보', '독서논술 관련 정보'),
                                                  ('국어 관련 정보', '국어 관련 정보'),
                                                  ('기타 특강 관련 정보', '기타 특강 관련 정보')
                                              ],
                                              validators=[DataRequired(message='필요한 교육 정보를 선택하세요.')])

    academic_goals = SelectMultipleField('21. 진학 목표가 있으신가요? (중복 선택 가능)',
                                        choices=[
                                            ('해외대학 진학 희망', '해외대학 진학 희망'),
                                            ('국내대학 진학 희망', '국내대학 진학 희망'),
                                            ('영재고/과학고 진학 희망', '영재고/과학고 진학 희망'),
                                            ('국제고/외고 진학 희망', '국제고/외고 진학 희망'),
                                            ('자사고 진학 희망', '자사고 진학 희망'),
                                            ('국제학교(초중고) 진학 희망', '국제학교(초중고) 진학 희망')
                                        ],
                                        validators=[Optional()])

    career_interests = SelectMultipleField('22. 관심 있는 학생의 진로 분야는 무엇입니까? (중복 선택 가능)',
                                          choices=[
                                              ('의학계열', '의학계열'),
                                              ('공학계열', '공학계열'),
                                              ('자연과학계열', '자연과학계열'),
                                              ('경영경제계열', '경영경제계열'),
                                              ('사회과학계열', '사회과학계열'),
                                              ('인문학계열', '인문학계열'),
                                              ('예체능계열', '예체능계열'),
                                              ('기타', '기타')
                                          ],
                                          validators=[Optional()])

    other_interests = TextAreaField('23. 기타 교육분야 관심사항이 있으시면 모두 적어주세요',
                                   validators=[Optional()],
                                   render_kw={'rows': 3, 'placeholder': '기타 관심사항을 자유롭게 작성해주세요.'})

    sibling_info = TextAreaField('형제/자매 정보를 입력해주세요 (이름/성별/학년(나이) 정보를 입력해주시면 특강 및 입시정보를 안내해드립니다)',
                                validators=[Optional()],
                                render_kw={'rows': 2, 'placeholder': 'ex. 김모모/남/중1, 박모모/여/10세'})
