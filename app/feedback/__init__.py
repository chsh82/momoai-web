# -*- coding: utf-8 -*-
"""수업 문자 자동 생성 Blueprint (강사용)"""
from flask import Blueprint

feedback_bp = Blueprint('feedback', __name__)

from app.feedback import routes  # noqa
