# -*- coding: utf-8 -*-
"""대시보드 블루프린트"""
from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

from app.dashboard import routes
