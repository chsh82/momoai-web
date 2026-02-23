# -*- coding: utf-8 -*-
"""Student 모델"""
from datetime import datetime
from app.models import db


class Student(db.Model):
    """학생 모델"""
    __tablename__ = 'students'

    student_id = db.Column(db.String(36), primary_key=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                       nullable=True)  # Phase 4에서 사용 (학생 계정 연결)
    name = db.Column(db.String(100), nullable=False, index=True)
    grade = db.Column(db.String(20), nullable=False)  # 초1~고3 (구체적 학년)
    school = db.Column(db.String(200), nullable=True)  # 학교명
    birth_date = db.Column(db.Date, nullable=True)  # 생년월일
    tier = db.Column(db.String(20), nullable=True, index=True)  # A, B, C, VIP 등 등급
    tier_updated_at = db.Column(db.DateTime, nullable=True)  # 등급 변경 일시
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_temp = db.Column(db.Boolean, default=False, nullable=False)  # 임시 학생 여부
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    teacher = db.relationship('User', back_populates='students',
                             foreign_keys=[teacher_id])
    essays = db.relationship('Essay', back_populates='student',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Student {self.name} ({self.grade})>'

    def __init__(self, **kwargs):
        super(Student, self).__init__(**kwargs)
        if not self.student_id:
            import uuid
            self.student_id = str(uuid.uuid4())

    @property
    def essay_count(self):
        """첨삭 수"""
        return len(self.essays)

    @property
    def completed_essay_count(self):
        """완료된 첨삭 수"""
        return len([e for e in self.essays if e.is_finalized])

    def update_tier(self, new_tier):
        """등급 업데이트"""
        self.tier = new_tier
        self.tier_updated_at = datetime.utcnow()

    def has_tier_access(self, required_tiers):
        """특정 티어에 대한 접근 권한 확인

        Args:
            required_tiers: 문자열 또는 리스트 (예: 'A' 또는 ['A', 'B'])
        """
        if not required_tiers:
            return True

        if isinstance(required_tiers, str):
            required_tiers = [required_tiers]

        return self.tier in required_tiers
