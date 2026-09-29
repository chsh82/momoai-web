# -*- coding: utf-8 -*-
"""상담 신청 모델.

학부모가 관리자에게 접수하는 구조다(강사 직접 승인 없음). 관리자가 접수를
책임지고, 필요하면 강사와 내부 협의(기존 강사↔관리자 메신저 재사용)를
거친 뒤 학부모와의 일정을 확정한다. 강사 회신(내부 협의)과 일정 확정(학부모
응답)은 서로 다른 행동이라 상태 컬럼을 하나만 두고 internal_conversation_id로
내부 협의 스레드만 연결한다.

학부모용 대화도 같은 Conversation 모델을 재사용한다(parent_conversation_id) -
internal_conversation_id와 마찬가지로 신청 건 하나에 스레드 하나. 두 스레드는
서로 다른 participant 쌍(관리자↔강사 / 관리자↔학부모)이라 자연히 내용이
섞이지 않는다 - 학부모는 messages 블루프린트 자체에 접근 권한이 없으므로
오직 이 신청 상세 화면(consultation_request.detail)을 통해서만 자신의
parent_conversation을 읽고 답장할 수 있다.
"""
import uuid
from datetime import datetime

from app.models import db

CATEGORY_CHOICES = ['신규상담', '퇴원상담', '분기별상담', '진로진학상담', '기타']

# 개별(1:1) 보강 신청 - 시간표에 맞는 그룹 수업이 없을 때 위젯에서 이 카테고리로
# 접수된다(chat_widget.quick_makeup_individual). CATEGORY_CHOICES에는 넣지 않는다
# - 일반 상담 분류 드롭다운에 노출되면 안 되고 위젯 내부 로직에서만 이 값으로
# 생성된다.
MAKEUP_INDIVIDUAL_CATEGORY = '개별보강'

# pending(접수대기) -> scheduled(일정확정)/rejected(거절) -> completed(상담기록 연결)
STATUS_CHOICES = ['pending', 'scheduled', 'rejected', 'completed']


class ConsultationRequest(db.Model):
    """상담 신청 - 학부모 접수 -> 관리자 처리 -> 상담 기록 연결."""
    __tablename__ = 'consultation_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    requester_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                             nullable=True, index=True)  # 신청한 학부모

    category = db.Column(db.String(50), nullable=False)
    preferred_date = db.Column(db.Date, nullable=True)
    preferred_time = db.Column(db.Time, nullable=True)
    preferred_note = db.Column(db.String(200), nullable=True)
    reason = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default='pending', index=True)

    reject_reason = db.Column(db.Text, nullable=True)
    scheduled_date = db.Column(db.Date, nullable=True)
    scheduled_note = db.Column(db.String(200), nullable=True)

    # 강사 협의(개별보강 등) - MakeupClassRequest와 같은 패턴. admin_ask_date가
    # 있으면 관리자가 특정 날짜/시간을 지목해 물어본 것이고, 강사 화면에는
    # "이 시간 가능한가요?" 확인 버튼만 보여준다. 없으면 자유롭게 물어본
    # 것이라 강사가 직접 날짜/시간을 입력하는 폼을 보여준다.
    admin_ask_date = db.Column(db.Date, nullable=True)
    admin_ask_time = db.Column(db.Time, nullable=True)
    teacher_proposed_date = db.Column(db.Date, nullable=True)
    teacher_proposed_time = db.Column(db.Time, nullable=True)
    teacher_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    teacher_confirmed_at = db.Column(db.DateTime, nullable=True)

    responded_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    # 관리자<->강사 내부 협의 (기존 messages 모듈의 Conversation 재사용, 학부모는 접근 불가)
    internal_conversation_id = db.Column(db.Integer,
                                         db.ForeignKey('conversations.conversation_id', ondelete='SET NULL'),
                                         nullable=True)

    # 관리자<->학부모 대화 (위젯에서 노출되는 스레드)
    parent_conversation_id = db.Column(db.Integer,
                                       db.ForeignKey('conversations.conversation_id', ondelete='SET NULL'),
                                       nullable=True)

    # 완료 후 실제 상담 기록과 연결
    consultation_id = db.Column(db.Integer,
                                db.ForeignKey('consultation_records.consultation_id', ondelete='SET NULL'),
                                nullable=True, index=True)

    # category='개별보강'인 건이 일정 확정되면 실제로 생성된 1회 보강수업.
    # MakeupClassRequest.created_makeup_course_id와 같은 역할 - 이게 없어서
    # "일정 확정"을 눌러도 실제 수업이 개설되지 않는 문제가 있었다.
    created_makeup_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                                        nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', foreign_keys=[student_id])
    requester = db.relationship('User', foreign_keys=[requester_id])
    responder = db.relationship('User', foreign_keys=[responded_by])
    internal_conversation = db.relationship('Conversation', foreign_keys=[internal_conversation_id])
    parent_conversation = db.relationship('Conversation', foreign_keys=[parent_conversation_id])
    consultation_record = db.relationship('ConsultationRecord', foreign_keys=[consultation_id])
    created_makeup_course = db.relationship('Course', foreign_keys=[created_makeup_course_id])

    def __repr__(self):
        return f'<ConsultationRequest {self.request_id}: {self.status}>'
