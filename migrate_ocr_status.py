# -*- coding: utf-8 -*-
"""ocr_history 테이블에 status 컬럼 추가"""
import sys
import os

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
        cols = [c['name'] for c in inspector.get_columns('ocr_history')]
        if 'status' in cols:
            print("INFO: status column already exists")
            sys.exit(0)

        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE ocr_history ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'completed'"))
            conn.commit()
        print("OK: status column added to ocr_history")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
