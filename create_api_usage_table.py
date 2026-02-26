#!/usr/bin/env python3
"""api_usage_logs 테이블 생성 스크립트"""
from app import create_app
from app.models import db
from app.models.api_usage_log import ApiUsageLog

app = create_app()
with app.app_context():
    db.create_all()
    print("✅ api_usage_logs 테이블 생성 완료")
