# -*- coding: utf-8 -*-
"""MakeupClassRequest 테이블에 requested_date 컬럼 추가"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE makeup_class_requests ADD COLUMN requested_date DATE"))
            conn.commit()
        print("✅ requested_date 컬럼 추가 완료")
    except Exception as e:
        err = str(e)
        if 'duplicate column' in err.lower() or 'already exists' in err.lower():
            print("ℹ️  requested_date 컬럼이 이미 존재합니다 (정상)")
        else:
            print(f"❌ 오류 발생: {e}")
            sys.exit(1)
