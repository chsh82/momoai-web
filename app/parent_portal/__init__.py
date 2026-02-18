# -*- coding: utf-8 -*-
"""Parent Portal Blueprint"""
from flask import Blueprint

parent_bp = Blueprint('parent', __name__)

from app.parent_portal import routes
