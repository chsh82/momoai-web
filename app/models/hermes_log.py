# -*- coding: utf-8 -*-
"""헤르메스(관리자 전용 자연어 명령 에이전트) 명령 로그 모델.

확인 게이트 없이 바로 실행하는 대신, 모든 명령(성공/실패/명확화 요청)을
이 테이블에 전부 남겨 사후 검증 가능하게 한다. 관리자 화면의 대화
transcript도 이 테이블을 그대로 읽어 렌더링한다(명령 1건 = 응답 1건이라
별도 Conversation/Message 쌍을 또 만들지 않음)."""
import uuid
from datetime import datetime
from app.models import db


class HermesCommandLog(db.Model):
    """헤르메스 명령 1턴(관리자 입력 1회 + 처리 결과 1회) 기록."""
    __tablename__ = 'hermes_command_logs'

    log_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 같은 대화 흐름(명확화 질문-답변 포함)을 묶는 식별자
    thread_id = db.Column(db.String(36), nullable=False, index=True)
    admin_user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                              nullable=True, index=True)

    # 입력/해석
    raw_text = db.Column(db.Text, nullable=False)
    parsed_action = db.Column(db.Text, nullable=True)  # LLM 응답 원문 JSON(문자열)
    action_type = db.Column(db.String(30), index=True)  # schedule_makeup, mark_absence, unrecognized
    resolved_params = db.Column(db.Text, nullable=True)  # 엔티티 해석 후 JSON(문자열)

    # 처리 결과
    status = db.Column(db.String(20), nullable=False, index=True)  # needs_clarification, success, failed
    clarification_question = db.Column(db.Text, nullable=True)
    result_summary = db.Column(db.Text, nullable=True)
    error_detail = db.Column(db.Text, nullable=True)

    # 실제로 변경된 대상(있는 경우)
    related_entity_type = db.Column(db.String(50), nullable=True)  # course, attendance, absence_notice
    related_entity_id = db.Column(db.String(36), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    admin_user = db.relationship('User', foreign_keys=[admin_user_id])
