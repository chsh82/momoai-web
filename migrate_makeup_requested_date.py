# -*- coding: utf-8 -*-
"""MakeupClassRequest 테이블에 requested_date 컬럼 추가"""
import sys
import os

# .env.production 또는 .env 로드 (GCP 환경 대응)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for env_file in ['.env.production', '.env']:
    env_path = os.path.join(BASE_DIR, env_file)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        break

sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db
from sqlalchemy import text, inspect

app = create_app('production')

with app.app_context():
    try:
        inspector = inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('makeup_class_requests')]
        if 'requested_date' in cols:
            print("INFO: requested_date column already exists")
            sys.exit(0)

        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE makeup_class_requests ADD COLUMN requested_date DATE"))
            conn.commit()
        print("OK: requested_date column added")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
