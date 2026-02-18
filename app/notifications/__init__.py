# -*- coding: utf-8 -*-
"""알림 블루프린트"""
from flask import Blueprint

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

from app.notifications import routes
