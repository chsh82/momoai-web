# -*- coding: utf-8 -*-
"""환불 요청 블루프린트.

학부모가 결제 건에 환불을 요청하면 관리자에게 알림만 가고, 자동으로
처리되지 않는다. 관리자가 검토 후 승인(Payment.status를 'refunded'로
변경)하거나 거절(사유 필수)한다.
"""
from flask import Blueprint

refund_request_bp = Blueprint('refund_request', __name__)

from app.refund_request import routes  # noqa: E402,F401
