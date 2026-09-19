# -*- coding: utf-8 -*-
"""초등 공부력 테스트 블루프린트 (구버전 폼 임시 적용 - study_mid 참고)."""
from flask import Blueprint

study_elem_bp = Blueprint('study_elem', __name__)

from app.study_elem import routes  # noqa: E402,F401
