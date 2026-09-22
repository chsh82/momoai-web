# -*- coding: utf-8 -*-
"""학부모용 대화 위젯 (우측 하단 플로팅 버튼) JSON API.

상담 신청·보강 신청·환불 요청 각각의 신청서 자체는 기존 블루프린트
(consultation_request/refund_request, 보강은 parent_portal)가 그대로
처리한다 - 이 블루프린트는 그 위에 얹히는 "한 곳에서 보는 대화창" 조회·
답장 API만 담당한다. 신청서 작성(학과/결제 등 선택이 필요한 복잡한 폼)은
위젯에서 대신하지 않고 기존 페이지로 링크한다 - 상담 신청만 학생 선택 +
분류 + 사유뿐이라 위젯 안에서 바로 작성 가능하게 예외로 둔다.
"""
from flask import Blueprint

chat_widget_bp = Blueprint('chat_widget', __name__)

from app.chat_widget import routes  # noqa: E402,F401
