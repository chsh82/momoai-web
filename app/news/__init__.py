# -*- coding: utf-8 -*-
"""모모 소식 블루프린트"""
from flask import Blueprint

news_bp = Blueprint('news', __name__, url_prefix='/news')

from app.news import routes  # noqa
