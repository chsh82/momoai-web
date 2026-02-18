# -*- coding: utf-8 -*-
"""인증 블루프린트"""
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from app.auth import routes
