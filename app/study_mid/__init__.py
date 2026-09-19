# -*- coding: utf-8 -*-
"""중등 공부력 테스트 블루프린트."""
from flask import Blueprint

study_mid_bp = Blueprint('study_mid', __name__)

from app.study_mid import routes  # noqa: E402,F401
