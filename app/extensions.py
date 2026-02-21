# -*- coding: utf-8 -*-
"""Flask 확장 모듈 (순환 참조 방지용)"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[]
)

mail = Mail()
