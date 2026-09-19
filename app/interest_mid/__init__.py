# -*- coding: utf-8 -*-
"""중등 전공 나침반 블루프린트."""
from flask import Blueprint

interest_mid_bp = Blueprint('interest_mid', __name__)

from app.interest_mid import routes  # noqa: E402,F401
