# -*- coding: utf-8 -*-
"""도서 관리 블루프린트"""
from flask import Blueprint

books_bp = Blueprint('books', __name__)

from app.books import routes
