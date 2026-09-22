# -*- coding: utf-8 -*-
"""상담 신청 블루프린트.

학부모가 관리자에게 접수하는 구조 - 강사 직접 승인은 없다. 관리자가 접수를
책임지고 필요하면 강사에게 내부 협의를 요청한다(기존 강사<->관리자 메신저
재사용). 강사 회신(내부 협의)과 학부모 일정 확정은 서로 다른 관리자 행동으로
분리돼 있다.
"""
from flask import Blueprint

consultation_request_bp = Blueprint('consultation_request', __name__)

from app.consultation_request import routes  # noqa: E402,F401
