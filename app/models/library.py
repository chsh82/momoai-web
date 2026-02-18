# -*- coding: utf-8 -*-
"""도서 자료실 모델"""
from datetime import datetime
import uuid
from app.models import db


class HallOfFame(db.Model):
    """명예의 전당 - 우수 답안 및 수상작"""
    __tablename__ = 'hall_of_fame'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 분류
    category = db.Column(db.String(50), nullable=False, index=True)  # 'excellent_answer', 'mock_exam_award', 'essay_award', 'other'

    # 학생 정보 (선택)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'), nullable=True)
    student_name = db.Column(db.String(100), nullable=True)  # 익명 처리용
    grade = db.Column(db.String(20), nullable=True)  # 학년

    # 수상 정보
    award_name = db.Column(db.String(200), nullable=True)  # 수상명
    award_date = db.Column(db.Date, nullable=True)  # 수상일

    # 파일 첨부
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 공개 여부
    is_published = db.Column(db.Boolean, default=True, index=True)

    # 메타 정보
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='hall_of_fame_posts')
    creator = db.relationship('User', backref='hall_of_fame_posts')

    def __repr__(self):
        return f'<HallOfFame {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(HallOfFame, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())


class AdmissionInfo(db.Model):
    """입시정보 게시판"""
    __tablename__ = 'admission_info'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 분류
    category = db.Column(db.String(50), nullable=False, index=True)  # 'university', 'high_school', 'policy', 'schedule', 'tips', 'other'

    # 대상 학년
    target_grades = db.Column(db.Text, nullable=True)  # JSON: ['초등', '중등', '고등']

    # 외부 링크
    external_url = db.Column(db.String(500), nullable=True)

    # 파일 첨부
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 중요 공지 여부
    is_important = db.Column(db.Boolean, default=False, index=True)

    # 공개 기간
    publish_date = db.Column(db.Date, nullable=True, index=True)
    expire_date = db.Column(db.Date, nullable=True, index=True)

    # 메타 정보
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='admission_info_posts')

    def __repr__(self):
        return f'<AdmissionInfo {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(AdmissionInfo, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())

    def is_active(self):
        """현재 공개 기간인지 확인"""
        if not self.publish_date:
            return True
        today = datetime.now().date()
        if self.expire_date:
            return self.publish_date <= today <= self.expire_date
        return self.publish_date <= today
