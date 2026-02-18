# -*- coding: utf-8 -*-
"""커뮤니티 블루프린트"""
from flask import Blueprint

community_bp = Blueprint('community', __name__)

from app.community import routes
