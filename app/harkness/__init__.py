# -*- coding: utf-8 -*-
"""Harkness Blueprint"""
from flask import Blueprint

harkness_bp = Blueprint('harkness', __name__)

from app.harkness import routes
