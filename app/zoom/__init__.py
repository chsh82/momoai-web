# -*- coding: utf-8 -*-
"""Zoom Blueprint"""
from flask import Blueprint

zoom_bp = Blueprint('zoom', __name__)

from app.zoom import routes
