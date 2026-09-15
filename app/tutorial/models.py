# -*- coding: utf-8 -*-
"""튜토리얼 진도·정답·코스완료보상 모델 (1단계).

이 리포의 기존 모델(User/Course 등) 관례를 따라 UUID 문자열 PK를 쓴다
(mapped_column/Integer 자동증가가 아니라 db.Column 1.x 선언형 + __init__에서
uuid.uuid4() 생성).
"""
import uuid
from datetime import datetime

from app.models import db


class TutorialProgress(db.Model):
    """레슨 단위 진도 - 로그인 계정(User) 기준. 명부(Student) 레코드가 없어도 쌓인다."""
    __tablename__ = 'tutorial_progress'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       index=True, nullable=False)
    track = db.Column(db.String(16), nullable=False)  # 'elem'
    course = db.Column(db.String(16), nullable=False)  # 'course1'
    lesson_id = db.Column(db.String(32), nullable=False)  # 'elem-c1-l1'
    status = db.Column(db.String(16), nullable=False, default='in_progress')  # in_progress|done
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    done_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'lesson_id', name='uq_prog_user_lesson'),
    )

    def __repr__(self):
        return f'<TutorialProgress user={self.user_id} lesson={self.lesson_id} status={self.status}>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4())


class TutorialAttempt(db.Model):
    """문항 단위 응답 기록 - 로그인 계정(User) 기준."""
    __tablename__ = 'tutorial_attempt'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       index=True, nullable=False)
    lesson_id = db.Column(db.String(32), nullable=False)
    question_id = db.Column(db.String(48), nullable=False)
    rule_no = db.Column(db.String(8))
    correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TutorialAttempt user={self.user_id} q={self.question_id} correct={self.correct}>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4())


class TutorialCourseReward(db.Model):
    """코스 완료 보상(마일리지) 지급 기록 - 중복 지급 방지용.

    Student.student_id 기준이다(User.user_id가 아님) - 적립 주체가 award_points()의
    student_id와 같아야, 이 테이블의 유니크 제약이 실제 중복 지급을 막는 방어선이 된다.
    """
    __tablename__ = 'tutorial_course_reward'

    id = db.Column(db.String(36), primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          index=True, nullable=False)
    track = db.Column(db.String(16), nullable=False)  # 'elem'
    course = db.Column(db.String(16), nullable=False)  # 'course1'
    points = db.Column(db.Integer, default=100)
    rewarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'track', 'course', name='uq_reward_student_course'),
    )

    def __repr__(self):
        return f'<TutorialCourseReward student={self.student_id} {self.track}/{self.course}>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4())
