# -*- coding: utf-8 -*-
"""프로필 블루프린트"""
from flask import Blueprint

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

from app.profile import routes
