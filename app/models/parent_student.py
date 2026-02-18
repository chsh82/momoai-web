# -*- coding: utf-8 -*-
"""ParentStudent 관계 모델"""
from datetime import datetime
import uuid
from app.models import db


class ParentStudent(db.Model):
    """학부모-학생 연결 모델"""
    __tablename__ = 'parent_student'

    relation_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 관계 타입
    relation_type = db.Column(db.String(20), default='parent')  # parent, guardian, etc

    # 권한 레벨
    permission_level = db.Column(db.String(20), default='full')  # full, view_only

    # 활성화 여부
    is_active = db.Column(db.Boolean, default=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))

    # Relationships
    parent = db.relationship('User', foreign_keys=[parent_id], backref='parent_relations')
    student = db.relationship('Student', backref='parent_relations')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<ParentStudent {self.parent_id} -> {self.student_id}>'

    def __init__(self, **kwargs):
        super(ParentStudent, self).__init__(**kwargs)
        if not self.relation_id:
            self.relation_id = str(uuid.uuid4())

    # Unique constraint: 한 학부모-학생 쌍은 하나만
    __table_args__ = (
        db.UniqueConstraint('parent_id', 'student_id', name='unique_parent_student'),
    )
