# -*- coding: utf-8 -*-
"""검색 블루프린트"""
from flask import Blueprint

search_bp = Blueprint('search', __name__)

from app.search import routes
