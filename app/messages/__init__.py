# -*- coding: utf-8 -*-
"""강사↔관리자 1:1 내부 메시지 블루프린트"""
from flask import Blueprint

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')

from app.messages import routes  # noqa: E402, F401
