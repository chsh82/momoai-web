# -*- coding: utf-8 -*-
"""TeacherFeedback 모델"""
from datetime import datetime
import uuid
from app.models import db


class TeacherFeedback(db.Model):
    """강사-학부모 피드백 모델 (학생에게는 비공개)"""
    __tablename__ = 'teacher_feedback'

    feedback_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    parent_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 피드백 유형
    feedback_type = db.Column(db.String(20), default='general')  # general, progress, behavior, attendance

    # 제목 및 내용
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 관련 정보
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.String(36), db.ForeignKey('course_sessions.session_id', ondelete='SET NULL'), nullable=True)

    # 중요도
    priority = db.Column(db.String(20), default='normal')  # high, normal, low

    # 읽음 여부
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # 학생 열람 금지 (항상 True)
    hidden_from_student = db.Column(db.Boolean, default=True, nullable=False)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='teacher_feedbacks')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='sent_feedbacks')
    parent = db.relationship('User', foreign_keys=[parent_id], backref='received_feedbacks')
    course = db.relationship('Course', backref='feedbacks')
    session = db.relationship('CourseSession', backref='feedbacks')

    def __repr__(self):
        return f'<TeacherFeedback {self.feedback_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(TeacherFeedback, self).__init__(**kwargs)
        if not self.feedback_id:
            self.feedback_id = str(uuid.uuid4())
        # 학생에게는 항상 숨김
        self.hidden_from_student = True

    @property
    def is_urgent(self):
        """긴급 피드백 여부"""
        return self.priority == 'high'

    def mark_as_read(self):
        """읽음 처리"""
        self.is_read = True
        self.read_at = datetime.utcnow()
