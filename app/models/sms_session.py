# -*- coding: utf-8 -*-
"""수업 문자 자동 생성기 - 저장된 회차/문자 (3단계, app/feedback/routes.py 참고).

SmsSession: 반 x 날짜 = 회차 하나. SmsMessage: 회차 안의 학생별 문자 한 건.
저장 대상은 AI 원본이 아니라 교사가 화면에서 최종 수정한 본문이다 -
학생 이름·문자 본문을 의도적으로 저장한다(학원 업무 기록), 다만 서버
콘솔 로그에는 절대 남기지 않는다.
"""
from datetime import datetime
import uuid
from app.models import db


class SmsSession(db.Model):
    """수업 문자 회차 (반 x 날짜, 같은 조합이면 재저장 시 덮어쓴다)"""
    __tablename__ = 'sms_sessions'

    sms_session_id = db.Column(db.String(36), primary_key=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    class_date = db.Column(db.Date, nullable=False, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                          nullable=True, index=True)
    class_type = db.Column(db.String(20), nullable=True)  # 생성 당시 확정값: 하크니스/그룹/1:1
    book = db.Column(db.String(200), nullable=True)
    week = db.Column(db.String(50), nullable=True)
    raw_summary = db.Column(db.Text, nullable=True)
    name_map = db.Column(db.JSON, nullable=True)  # [{"raw":"김지우","to":"김지후"}, ...]
    report_body = db.Column(db.Text, nullable=True)  # 반 전체 1건 수업 보고문 (4단계, 선택 저장)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship('Course', backref=db.backref('sms_sessions', cascade='all, delete-orphan'))
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    messages = db.relationship('SmsMessage', back_populates='session',
                               cascade='all, delete-orphan',
                               order_by='SmsMessage.student_name')

    __table_args__ = (
        db.UniqueConstraint('course_id', 'class_date', name='uq_sms_session_course_date'),
    )

    def __repr__(self):
        return f'<SmsSession course={self.course_id} date={self.class_date}>'

    def __init__(self, **kwargs):
        super(SmsSession, self).__init__(**kwargs)
        if not self.sms_session_id:
            self.sms_session_id = str(uuid.uuid4())


class SmsMessage(db.Model):
    """회차 안의 학생별 문자 한 건 - 교사가 최종 수정한 본문을 저장한다"""
    __tablename__ = 'sms_messages'

    sms_message_id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sms_sessions.sms_session_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'),
                          nullable=True, index=True)
    student_name = db.Column(db.String(100), nullable=False)  # 저장 시점 스냅샷(개명 대비)
    body = db.Column(db.Text, nullable=False)
    msg_type = db.Column(db.String(20), nullable=True)  # 토론형/강의형

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('SmsSession', back_populates='messages')
    student = db.relationship('Student')

    def __repr__(self):
        return f'<SmsMessage {self.student_name} session={self.session_id}>'

    def __init__(self, **kwargs):
        super(SmsMessage, self).__init__(**kwargs)
        if not self.sms_message_id:
            self.sms_message_id = str(uuid.uuid4())
