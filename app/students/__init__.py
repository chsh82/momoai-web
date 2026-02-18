# -*- coding: utf-8 -*-
"""학생 관리 블루프린트"""
from flask import Blueprint

students_bp = Blueprint('students', __name__)

from app.students import routes
