# -*- coding: utf-8 -*-
"""보강수업 신청 모델"""
from datetime import datetime
import uuid
from app.models import db


class MakeupClassRequest(db.Model):
    """보강수업 신청 모델"""
    __tablename__ = 'makeup_class_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    requested_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                                   nullable=False, index=True)
    original_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                                  nullable=True)  # 원래 수강 중인 수업 (선택사항)

    # 신청 사유
    reason = db.Column(db.Text, nullable=True)

    # 학생이 원하는 보강 날짜
    requested_date = db.Column(db.Date, nullable=True)

    # 상태
    status = db.Column(db.String(20), default='pending', index=True)  # pending, approved, rejected

    # 신청 정보
    request_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    requested_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))  # 신청자 (학생 또는 학부모)

    # 관리자 응답
    admin_response_date = db.Column(db.DateTime, nullable=True)
    admin_response_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))
    admin_notes = db.Column(db.Text, nullable=True)  # 관리자 메모/거절 사유

    # 승인 시 생성된 보강 수업 정보
    created_makeup_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                                        nullable=True)

    # 관리자<->강사 내부 협의 (기존 messages 모듈의 Conversation 재사용, 학부모는 접근 불가).
    # 강사 스케줄이 매번 달라 사전 등록 풀 대신 요청 건마다 즉석으로 물어보는 방식으로 결정함.
    internal_conversation_id = db.Column(db.Integer,
                                         db.ForeignKey('conversations.conversation_id', ondelete='SET NULL'),
                                         nullable=True)

    # 관리자<->학부모 대화 (위젯에서 노출되는 스레드, consultation_request와 동일 패턴)
    parent_conversation_id = db.Column(db.Integer,
                                       db.ForeignKey('conversations.conversation_id', ondelete='SET NULL'),
                                       nullable=True)

    # 관리자가 강사에게 물어볼 때 특정 날짜/시간을 지목했는지 - 지목했다면
    # 강사 확인 화면에 "이 시간 가능한가요?" 확인 버튼을, 지목하지 않았다면
    # (자유롭게 물어본 경우) 강사가 직접 날짜/시간을 입력하는 폼을 보여준다.
    admin_ask_date = db.Column(db.Date, nullable=True)
    admin_ask_time = db.Column(db.Time, nullable=True)

    # 강사 최종 컨펌 - 담당 강사 본인이 직접 확인해야 승인 가능하다(approve_makeup_request
    # 에서 이 값을 강제로 확인함). 관리자가 대신 체크하는 게 아니라 강사 전용 화면
    # (teacher.makeup_confirm)에서 강사 계정으로만 True가 될 수 있다.
    teacher_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    teacher_confirmed_at = db.Column(db.DateTime, nullable=True)

    # 강사가 컨펌하면서 직접 지정한 날짜/시간(자유 채팅이 아니라 버튼+입력으로
    # 확정 - LLM이 대화 내용에서 날짜를 추론해 자동으로 채우지 않는다). 이 값이
    # 있으면 학부모 확인 요청과 최종 보강수업 개설에 그대로 쓰인다.
    teacher_proposed_date = db.Column(db.Date, nullable=True)
    teacher_proposed_time = db.Column(db.Time, nullable=True)

    # 학부모가 강사 제안 일정에 위젯 버튼으로 명시적으로 동의한 시각. 이 값이
    # 찍히면(=강사 제안 + 학부모 동의 둘 다 구조화된 확정) 관리자의 별도 승인
    # 클릭 없이 자동으로 보강수업이 개설된다(finalize_makeup_request 재사용).
    parent_confirmed_at = db.Column(db.DateTime, nullable=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='makeup_requests')
    requested_course = db.relationship('Course', foreign_keys=[requested_course_id])
    original_course = db.relationship('Course', foreign_keys=[original_course_id])
    created_makeup_course = db.relationship('Course', foreign_keys=[created_makeup_course_id])
    requester = db.relationship('User', foreign_keys=[requested_by])
    admin_responder = db.relationship('User', foreign_keys=[admin_response_by])
    internal_conversation = db.relationship('Conversation', foreign_keys=[internal_conversation_id])
    parent_conversation = db.relationship('Conversation', foreign_keys=[parent_conversation_id])

    def __repr__(self):
        return f'<MakeupClassRequest {self.request_id}: {self.student_id} -> {self.requested_course_id}>'

    def __init__(self, **kwargs):
        super(MakeupClassRequest, self).__init__(**kwargs)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
