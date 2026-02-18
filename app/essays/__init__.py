# -*- coding: utf-8 -*-
"""첨삭 관리 블루프린트"""
from flask import Blueprint

essays_bp = Blueprint('essays', __name__)

from app.essays import routes
