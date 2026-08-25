# -*- coding: utf-8 -*-
"""모모의 책장 커리큘럼 관리 블루프린트"""
from flask import Blueprint

curriculum_bp = Blueprint('curriculum', __name__)

from app.curriculum import routes
