# -*- coding: utf-8 -*-
from flask import Blueprint

payment_bp = Blueprint('payment', __name__)

from app.payment import routes  # noqa
