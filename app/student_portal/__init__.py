# -*- coding: utf-8 -*-
"""학생 포털 Blueprint"""
from flask import Blueprint

student_bp = Blueprint('student', __name__)

from app.student_portal import routes
