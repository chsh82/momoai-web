# -*- coding: utf-8 -*-
"""essays 테이블에 error_message 컬럼 추가."""
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
        cols = {c['name'] for c in inspector.get_columns('essays')}

        if 'error_message' in cols:
            print("INFO: error_message 컬럼이 이미 존재합니다.")
            sys.exit(0)

        dialect = db.engine.dialect.name
        with db.engine.connect() as conn:
            if dialect == 'postgresql':
                conn.execute(text("ALTER TABLE essays ADD COLUMN error_message TEXT"))
            else:
                conn.execute(text("ALTER TABLE essays ADD COLUMN error_message TEXT"))
            conn.commit()

        print("OK: essays.error_message 컬럼 추가 완료")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
