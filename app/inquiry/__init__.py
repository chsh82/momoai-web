# -*- coding: utf-8 -*-
"""문의 게시판 블루프린트"""
from flask import Blueprint

inquiry_bp = Blueprint('inquiry', __name__, url_prefix='/inquiry')

from app.inquiry import routes  # noqa
