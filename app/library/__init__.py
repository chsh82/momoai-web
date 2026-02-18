# -*- coding: utf-8 -*-
"""도서 자료실 Blueprint"""
from flask import Blueprint

library_bp = Blueprint('library', __name__)

from app.library import routes
